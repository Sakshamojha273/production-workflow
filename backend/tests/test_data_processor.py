import pytest
import pandas as pd
import io
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import date

from app.services.data_processor import DataProcessor, CSV_NA_VALUES
from app.models.maintenance import MaintenanceStatus, MaintenanceType
from app.models.data_quality_report import DataQualityReport, DataQualityStatus


class TestDataProcessor:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def processor(self, mock_db):
        return DataProcessor(mock_db)

    @pytest.fixture
    def valid_csv(self):
        return b"""Order_ID,Date,Product_ID,Product_Name,Category,Demand,Production_Quantity,Machine_ID,Machine_Name,Machine_Type,Machine_Capacity,Machine_Availability,Maintenance_Status,Worker_ID,Worker_Name,Department,Shift,Worker_Availability,Production_Time_Minutes,Overtime_Hours,Production_Cost,Machine_Vibration,Machine_Temperature_C,Machine_Risk_Score,Next_Day_Demand,Priority,Due_Date,Status,Inventory_Level,Safety_Stock
ORD-001,2024-01-01,PRD-001,Widget A,Electronics,150,145,MACH-001,CNC Mill A,CNC,200,1,Operational,WRK-001,John Smith,Machining,Day,1,45,2,1250.00,0.12,45.2,0.15,155,High,2024-01-02,Completed,500,100
ORD-002,2024-01-01,PRD-002,Gadget B,Electronics,200,195,MACH-002,Lathe B,Lathe,180,1,Operational,WRK-002,Jane Doe,Assembly,Day,1,50,1,1500.00,0.15,48.5,0.22,210,Medium,2024-01-03,Completed,300,80"""

    @pytest.fixture
    def invalid_csv(self):
        return b"""Order_ID,Date,Product_ID
ORD-001,2024-01-01,PRD-001
ORD-002,invalid-date,PRD-002"""

    @pytest.mark.asyncio
    async def test_process_valid_csv(self, processor, valid_csv, mock_db):
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        
        with patch.object(processor, '_ingest_data') as mock_ingest:
            mock_ingest.return_value = None
            report = await processor.process_csv(valid_csv, "test.csv")
        
        assert isinstance(report, DataQualityReport)
        assert report.total_rows == 2
        assert report.total_columns == 30
        assert report.quality_score > 90
        assert report.status == DataQualityStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_invalid_csv(self, processor, invalid_csv, mock_db):
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        
        report = await processor.process_csv(invalid_csv, "invalid.csv")
        
        assert report.status == DataQualityStatus.FAILED
        assert "Failed to parse CSV" in report.error_message

    def test_analyze_data_quality(self, processor, valid_csv):
        df = pd.read_csv(io.BytesIO(valid_csv))
        report = processor._analyze_data_quality(df, "test.csv")
        
        assert report.total_rows == 2
        assert report.total_columns == 30
        assert report.missing_values == 0
        assert report.duplicate_rows == 0
        assert 0 <= report.quality_score <= 100

    def test_analyze_data_quality_with_missing(self, processor):
        df = pd.DataFrame({
            'A': [1, 2, None],
            'B': [4, None, 6],
            'C': [7, 8, 9]
        })
        report = processor._analyze_data_quality(df, "test.csv")
        
        assert report.missing_values == 2
        assert report.missing_by_column['A'] == 1
        assert report.missing_by_column['B'] == 1

    def test_analyze_data_quality_with_duplicates(self, processor):
        df = pd.DataFrame({
            'A': [1, 2, 2],
            'B': [4, 5, 5]
        })
        report = processor._analyze_data_quality(df, "test.csv")
        
        assert report.duplicate_rows == 1

    def test_analyze_data_quality_without_numeric_columns(self, processor):
        df = pd.DataFrame({
            'A': ['first', 'second'],
            'B': ['alpha', 'beta']
        })
        report = processor._analyze_data_quality(df, "test.csv")

        assert report.quality_score == 100
        assert report.outliers == 0

    def test_normalize_supplied_dataset_columns(self, processor):
        df = pd.DataFrame({
            'Order_ID': ['O1', 'O2', 'O3'],
            'Date': ['2026-01-01'] * 3,
            'Product_ID': ['P1'] * 3,
            'Product_Name': ['Part'] * 3,
            'Process_Type': ['Machining'] * 3,
            'Demand_Qty': [100, 100, 100],
            'Planned_Production_Qty': [100, 80, 90],
            'Late_Units': [0, 0, 2],
            'Machine_ID': ['M1'] * 3,
            'Machine_Capacity_Per_Hour': [80] * 3,
            'Machine_Availability': [0.8, 0.4, 0],
            'Worker_ID': ['W1'] * 3,
            'Worker_Department': ['Machining'] * 3,
            'Worker_Availability': [0.95, 0.8, 0],
            'Production_Time_Min': [15] * 3,
            'Maintenance_Status': [None, 'Scheduled', 'Emergency'],
        })

        normalized = processor._normalize_dataset_columns(df)

        assert normalized['Category'].tolist() == ['Machining'] * 3
        assert normalized['Machine_Type'].tolist() == ['Machining'] * 3
        assert normalized['Demand'].tolist() == [100] * 3
        assert normalized['Production_Quantity'].tolist() == [100, 80, 90]
        # Fractional availability is preserved (it used to be collapsed to 0/1).
        assert normalized['Machine_Availability'].tolist() == [0.8, 0.4, 0]
        assert normalized['Worker_Availability'].tolist() == [0.95, 0.8, 0]
        assert normalized['Production_Time_Minutes'].tolist() == [15] * 3
        assert normalized['Status'].tolist() == ['Completed', 'In Progress', 'Delayed']
        assert normalized['Maintenance_Status'].tolist() == ['Operational', 'Scheduled', 'Emergency']
        assert normalized['Safety_Stock'].tolist() == [0] * 3

    def test_clean_data(self, processor):
        df = pd.DataFrame({
            'A': [1, 2, None, 4],
            'B': [1.1, None, 3.3, 4.4],
            'C': ['x', 'y', None, 'z']
        })
        cleaned = processor._clean_data(df)
        
        assert cleaned['A'].isnull().sum() == 0
        assert cleaned['B'].isnull().sum() == 0
        assert cleaned['C'].isnull().sum() == 0

    @pytest.mark.asyncio
    async def test_daily_demand_history_aggregates_duplicate_product_dates(self, processor, mock_db):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)
        mock_db.add = MagicMock()
        frame = pd.DataFrame({
            'Product_ID': ['P1', 'P1', 'P1'],
            'Date': pd.to_datetime(['2026-01-01', '2026-01-01', '2026-01-02']),
            'Demand': [100, 50, 25],
            'Production_Quantity': [90, 45, 20],
        })

        await processor._update_demand_history(frame)

        history = [call.args[0] for call in mock_db.add.call_args_list]
        assert [(item.product_id, item.demand, item.production_quantity) for item in history] == [
            ('P1', 150, 135),
            ('P1', 25, 20),
        ]

    def test_demand_validation_rejects_missing_and_negative_demand(self, processor):
        frame = pd.DataFrame({
            'Product_ID': ['P1', 'P1'],
            'Date': ['2026-01-01', '2026-01-02'],
            'Demand': [10, -1],
        })

        with pytest.raises(ValueError, match='must not be negative'):
            processor._validate_demand_fields(frame)

class TestDatasetImportRules:
    @pytest.fixture
    def processor(self):
        return DataProcessor(AsyncMock(spec=AsyncSession))

    def _frame(self):
        return pd.DataFrame({
            'Order_ID': ['O1', 'O2', 'O3', 'O4'],
            'Date': ['2026-02-20', '2026-02-25', '2026-02-27', '2026-03-03'],
            'Due_Date': ['2026-02-25', '2026-02-28', '2026-03-01', '2026-03-10'],
            'Product_ID': ['P1'] * 4,
            'Machine_ID': ['M1', 'M1', 'M2', 'M1'],
            'Demand_Qty': [100, 100, 100, 100],
            'Planned_Production_Qty': [100, 80, 90, 70],
            'Late_Units': [0, 5, 3, 9],
            'Maintenance_Status': ['None', 'Scheduled', 'Emergency', 'Scheduled'],
        })

    def test_orders_due_on_or_after_reference_date_are_open(self, processor):
        normalized = processor._normalize_dataset_columns(self._frame(), reference_date=date(2026, 3, 1))
        # Past due: Completed / Delayed (late units); due >= reference: Pending, regardless of source late units.
        assert normalized['Status'].tolist() == ['Completed', 'Delayed', 'Pending', 'Pending']

    def test_literal_none_maintenance_status_is_not_missing(self, processor):
        csv = self._frame().to_csv(index=False).encode()
        frame = pd.read_csv(io.BytesIO(csv), keep_default_na=False, na_values=CSV_NA_VALUES)
        report = processor._analyze_data_quality(frame, 'x.csv')
        assert report.missing_values == 0
        assert report.missing_by_column['Maintenance_Status'] == 0

    def test_missing_values_are_counted_before_filling(self, processor):
        frame = self._frame()
        frame.loc[0, 'Maintenance_Status'] = None
        raw = frame.copy()
        normalized = processor._normalize_dataset_columns(frame, reference_date=date(2026, 3, 1))
        assert normalized['Maintenance_Status'].isnull().sum() == 0  # filled during normalisation
        report = processor._analyze_data_quality(raw, 'x.csv', normalized=normalized)
        assert report.missing_values == 1

    def test_maintenance_events_from_status_flags(self, processor):
        normalized = processor._normalize_dataset_columns(self._frame(), reference_date=date(2026, 3, 1))
        rows = processor._maintenance_rows(normalized, reference_date=date(2026, 3, 1))
        by_id = {r['maintenance_id']: r for r in rows}
        assert set(by_id) == {'MNT-M1-20260225-SCH', 'MNT-M2-20260227-EME', 'MNT-M1-20260303-SCH'}
        assert by_id['MNT-M2-20260227-EME']['type'] == MaintenanceType.EMERGENCY
        assert by_id['MNT-M1-20260225-SCH']['status'] == MaintenanceStatus.COMPLETED
        assert by_id['MNT-M1-20260303-SCH']['status'] == MaintenanceStatus.SCHEDULED
        assert by_id['MNT-M1-20260303-SCH']['type'] == MaintenanceType.PREVENTIVE
