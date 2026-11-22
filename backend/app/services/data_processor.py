import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from datetime import date, datetime
from typing import Optional
import json
import io
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
import uuid

from app.models.order import Order, OrderPriority, OrderStatus
from app.models.product import Product
from app.models.machine import Machine
from app.models.worker import Worker
from app.models.worker import WorkerSkill
from app.models.inventory import Inventory
from app.models.demand_history import DemandHistory
from app.models.maintenance import Maintenance, MaintenanceStatus, MaintenanceType
from app.models.data_quality_report import DataQualityReport, DataQualityStatus
from app.core.config import settings, reference_date

logger = logging.getLogger(__name__)


# "None" is a real category in the source data (Maintenance_Status = no
# maintenance), so it must not be parsed as a missing value.  Everything else in
# pandas' default NA list is still treated as missing.
CSV_NA_VALUES = [
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND",
    "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "n/a", "nan", "null",
]
NO_MAINTENANCE_VALUES = {"None", "none", "Operational", "", "Unknown"}

# Maintenance_Status comes in two shapes:
#   * text labels ("None" / "Scheduled" / "Emergency"), as in the bundled 10K dataset;
#   * a numeric 0/1 flag, as in electronics_production_orders_8k.csv
#     (0.0 = 6,208 rows, 1.0 = 994 rows, blank = 798 rows).
# In the 0/1 data the flag is uncorrelated with Machine_Risk_Score, vibration
# and temperature (mean risk 0.324 vs 0.325), i.e. it marks routine planned
# maintenance rather than breakdowns.  Mapping:
#   0 / 0.0 / false / no  -> "Operational"  (no maintenance event)
#   1 / 1.0 / true / yes  -> "Scheduled"    (one Preventive event that day)
#   blank / missing       -> "Operational"  (nothing recorded; no event)
# Other text labels are kept as-is ("Emergency" -> Emergency, unknown labels
# -> Corrective, see _maintenance_rows).
_MAINTENANCE_FLAG_TEXT = {
    "0": "Operational", "false": "Operational", "no": "Operational", "n": "Operational",
    "1": "Scheduled", "true": "Scheduled", "yes": "Scheduled", "y": "Scheduled",
}


def normalize_maintenance_status(values: pd.Series) -> pd.Series:
    """Map raw Maintenance_Status values (labels or 0/1 flags) to labels."""
    def one(value: Any) -> str:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "Operational"
        if isinstance(value, (bool, np.bool_)):
            return "Scheduled" if value else "Operational"
        if isinstance(value, (int, float, np.integer, np.floating)):
            return "Scheduled" if float(value) > 0 else "Operational"
        text = str(value).strip()
        try:
            number = float(text)
        except ValueError:
            number = None
        if number is not None and not np.isnan(number):
            return "Scheduled" if number > 0 else "Operational"
        mapped = _MAINTENANCE_FLAG_TEXT.get(text.lower())
        if mapped:
            return mapped
        return "Operational" if text in NO_MAINTENANCE_VALUES else text
    return values.map(one)
_BULK_CHUNK = 1000


def planning_reference_date() -> date:
    return reference_date()


class DataProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def process_csv(self, file_content: bytes, filename: str) -> DataQualityReport:
        """Process uploaded CSV file and return quality report"""
        try:
            df = pd.read_csv(io.BytesIO(file_content), keep_default_na=False, na_values=CSV_NA_VALUES)
        except Exception as e:
            report = DataQualityReport(
                report_id=str(uuid.uuid4())[:8],
                filename=filename,
                total_rows=0,
                total_columns=0,
                quality_score=0.0,
                status=DataQualityStatus.FAILED,
                error_message=f"Failed to parse CSV: {str(e)}"
            )
            self.db.add(report)
            await self.db.commit()
            return report

        # Profile the file as uploaded, before any normalisation fills values.
        raw_df = df.copy()
        df = self._normalize_dataset_columns(df)
        required_columns = {'Order_ID', 'Date', 'Product_ID', 'Demand', 'Machine_ID', 'Worker_ID'}
        missing_columns = sorted(required_columns.difference(df.columns))
        if missing_columns or df.empty:
            reason = (
                f"missing required columns: {', '.join(missing_columns)}"
                if missing_columns
                else "CSV contains no data rows"
            )
            report = DataQualityReport(
                report_id=str(uuid.uuid4())[:8],
                filename=filename,
                total_rows=len(df),
                total_columns=len(df.columns),
                quality_score=0.0,
                status=DataQualityStatus.FAILED,
                error_message=f"Failed to parse CSV: {reason}",
            )
            self.db.add(report)
            await self.db.commit()
            return report

        try:
            self._validate_demand_fields(df)
        except ValueError as exc:
            report = DataQualityReport(
                report_id=str(uuid.uuid4())[:8],
                filename=filename,
                total_rows=len(df),
                total_columns=len(df.columns),
                quality_score=0.0,
                status=DataQualityStatus.FAILED,
                error_message=str(exc),
            )
            self.db.add(report)
            await self.db.commit()
            return report

        quality_report = self._analyze_data_quality(raw_df, filename, normalized=df)
        self.db.add(quality_report)
        await self.db.commit()
        
        if quality_report.quality_score >= 50:  # Only process if quality is acceptable
            await self._ingest_data(df)
            quality_report.status = DataQualityStatus.COMPLETED
            quality_report.completed_at = datetime.utcnow()
        else:
            quality_report.status = DataQualityStatus.FAILED
            quality_report.error_message = "Data quality score too low for ingestion"
        
        await self.db.commit()
        return quality_report
    
    def _analyze_data_quality(
        self, df: pd.DataFrame, filename: str, normalized: Optional[pd.DataFrame] = None
    ) -> DataQualityReport:
        """Analyze data quality of the dataframe as uploaded (before any filling).

        ``normalized`` (the column-mapped frame) is only used to find the
        required fields under their canonical names.
        """
        canonical = normalized if normalized is not None else df
        total_rows = len(df)
        total_columns = len(df.columns)
        
        # Missing values
        missing_values = int(df.isnull().sum().sum())
        missing_by_column = df.isnull().sum().to_dict()
        
        # Duplicate rows
        duplicate_rows = int(df.duplicated().sum())
        
        # Invalid records (rows with critical missing fields)
        required_columns = ['Order_ID', 'Date', 'Product_ID', 'Demand', 'Machine_ID', 'Worker_ID']
        invalid_records = 0
        for col in required_columns:
            if col in canonical.columns:
                invalid_records += int(canonical[col].isnull().sum())
        
        # Outliers detection (simple IQR method for numeric columns)
        outliers = 0
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            if IQR > 0:
                outliers += int(((df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))).sum())
        
        # Quality score (0-100)
        quality_score = 100.0
        if total_rows > 0:
            quality_score -= (missing_values / (total_rows * total_columns)) * 30
            quality_score -= (duplicate_rows / total_rows) * 20
            quality_score -= (invalid_records / total_rows) * 30
            if len(numeric_cols) > 0:
                quality_score -= min((outliers / (total_rows * len(numeric_cols))) * 20, 20)
        quality_score = max(0, min(100, quality_score))
        
        # Column types
        column_types = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        report = DataQualityReport(
            report_id=str(uuid.uuid4())[:8],
            filename=filename,
            total_rows=total_rows,
            total_columns=total_columns,
            missing_values=missing_values,
            duplicate_rows=duplicate_rows,
            invalid_records=invalid_records,
            outliers=outliers,
            quality_score=round(quality_score, 2),
            missing_by_column={column: int(count) for column, count in missing_by_column.items()},
            column_types=column_types,
            sample_data=json.loads(df.head(20).to_json(orient='records', date_format='iso')),
            status=DataQualityStatus.PROCESSING
        )
        
        return report

    @staticmethod
    def _normalize_dataset_columns(df: pd.DataFrame, reference_date: Optional[date] = None) -> pd.DataFrame:
        """Map the supplied planning dataset's field names to the ingestion schema."""
        # Our dataset already has the correct column names, just ensure they exist
        # Map alternative column names if present
        column_mapping = {
            'Demand': ['Demand_Qty', 'Demand'],
            'Production_Quantity': ['Planned_Production_Qty', 'Production_Quantity'],
            'Machine_Type': ['Process_Type', 'Machine_Type'],
            'Machine_Capacity': ['Machine_Capacity_Per_Hour', 'Machine_Capacity'],
            'Category': ['Process_Type', 'Category'],
            'Department': ['Worker_Department', 'Department'],
            'Production_Time_Minutes': ['Production_Time_Min', 'Production_Time_Minutes'],
        }
        
        for target, sources in column_mapping.items():
            if target not in df.columns:
                for source in sources:
                    if source in df.columns:
                        df[target] = df[source]
                        break

        if 'Status' not in df.columns and {'Demand', 'Production_Quantity'}.issubset(df.columns):
            late_units = pd.to_numeric(
                df.get('Late_Units', pd.Series(0, index=df.index)),
                errors='coerce',
            )
            is_late = late_units.fillna(0) > 0
            is_complete = pd.to_numeric(df['Production_Quantity'], errors='coerce').fillna(0) >= pd.to_numeric(
                df['Demand'], errors='coerce'
            ).fillna(0)
            # Orders due on/after the planning reference date (upload day unless
            # PLANNING_REFERENCE_DATE is set) are the open order book: their
            # planned quantity / late units are plans, not actuals, so they are
            # imported as "Pending" and are what the optimiser plans.  Orders
            # already past due keep the historical rule.
            if 'Due_Date' in df.columns:
                reference = pd.Timestamp(reference_date or planning_reference_date())
                due = pd.to_datetime(df['Due_Date'], errors='coerce')
                is_open = due.notna() & (due >= reference)
            else:
                is_open = pd.Series(False, index=df.index)
            df['Status'] = np.select(
                [is_open, is_late, is_complete],
                ['Pending', 'Delayed', 'Completed'],
                default='In Progress',
            )

        if 'Safety_Stock' not in df.columns:
            df['Safety_Stock'] = 0
        if 'Maintenance_Status' in df.columns:
            df['Maintenance_Status'] = normalize_maintenance_status(df['Maintenance_Status'])
        for availability_column in ('Machine_Availability', 'Worker_Availability'):
            if availability_column in df.columns:
                # Keep the fractional availability (0-1); values > 1 are treated as percentages.
                values = pd.to_numeric(df[availability_column], errors='coerce')
                values = values.where(values <= 1, values / 100.0)
                df[availability_column] = values.clip(lower=0, upper=1)

        return df

    async def _ingest_data(self, df: pd.DataFrame):
        """Ingest cleaned data into database"""
        self._validate_demand_fields(df)

        # Clean data
        df = self._clean_data(df)
        
        # Upsert products
        await self._upsert_products(df)
        
        # Upsert machines
        await self._upsert_machines(df)
        
        # Upsert workers
        await self._upsert_workers(df)
        
        # Upsert worker skills
        await self._upsert_worker_skills(df)
        
        # Upsert orders
        await self._upsert_orders(df)
        
        # Update inventory
        await self._update_inventory(df)
        
        # Maintenance events derived from Maintenance_Status
        await self._upsert_maintenance(df)

        # Update demand history
        await self._update_demand_history(df)
        
        await self.db.commit()

        # Machine vibration / temperature / risk are derived from the order
        # sensor readings. Compute them now so the Machines page shows real
        # values straight after an upload instead of the 0.0 column defaults
        # (previously they were only filled once Machine Health was opened).
        from app.ml.machine_risk import MachineRiskAnalyzer  # local: avoids import cycle / sklearn at import time
        try:
            await MachineRiskAnalyzer(self.db).analyze_machine_risk()
        except Exception:  # sensor refresh must never fail an otherwise good import
            logger.exception("Machine risk refresh after upload failed")
            await self.db.rollback()
    
    @staticmethod
    def _validate_demand_fields(df: pd.DataFrame):
        required_demand = df[['Product_ID', 'Date', 'Demand']].copy()
        required_demand['Date'] = pd.to_datetime(required_demand['Date'], errors='coerce')
        required_demand['Demand'] = pd.to_numeric(required_demand['Demand'], errors='coerce')
        if required_demand.isnull().any().any():
            raise ValueError("Demand data must include valid dates, product IDs, and numeric quantities")
        if required_demand['Product_ID'].astype(str).str.strip().eq('').any():
            raise ValueError("Demand data must include non-empty product IDs")
        if required_demand['Demand'].lt(0).any():
            raise ValueError("Demand quantities must not be negative")
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean the dataframe"""
        # Remove duplicates
        df = df.drop_duplicates()
        
        # Handle missing values
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].fillna(df[numeric_columns].median())
        
        categorical_columns = df.select_dtypes(include=['object']).columns
        df[categorical_columns] = df[categorical_columns].fillna('Unknown')
        
        # Parse dates
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        if 'Due_Date' in df.columns:
            df['Due_Date'] = pd.to_datetime(df['Due_Date'], errors='coerce')
        
        return df
    
    async def _upsert_products(self, df: pd.DataFrame):
        """Upsert products from dataframe"""
        products_df = df[['Product_ID', 'Product_Name', 'Category']].drop_duplicates()
        
        for _, row in products_df.iterrows():
            stmt = select(Product).where(Product.product_id == row['Product_ID'])
            result = await self.db.execute(stmt)
            product = result.scalar_one_or_none()
            
            if not product:
                product = Product(
                    product_id=row['Product_ID'],
                    name=row['Product_Name'],
                    category=row['Category'],
                    base_demand=int(df[df['Product_ID'] == row['Product_ID']]['Demand'].median()),
                    base_cost=float(df[df['Product_ID'] == row['Product_ID']]['Production_Cost'].median())
                )
                self.db.add(product)
    
    async def _upsert_machines(self, df: pd.DataFrame):
        """Upsert machines from dataframe.

        ``availability_factor`` is the mean fractional availability observed for
        the machine; ``availability`` stays a 0/1 in-service flag.
        """
        machines_df = df[['Machine_ID', 'Machine_Name', 'Machine_Type', 'Machine_Capacity']].drop_duplicates('Machine_ID', keep='last')
        if 'Machine_Availability' in df.columns:
            factors = pd.to_numeric(df['Machine_Availability'], errors='coerce').groupby(df['Machine_ID']).mean()
        else:
            factors = pd.Series(dtype=float)

        for _, row in machines_df.iterrows():
            factor = factors.get(row['Machine_ID'])
            factor = 1.0 if factor is None or pd.isna(factor) else float(min(max(factor, 0.0), 1.0))
            stmt = select(Machine).where(Machine.machine_id == row['Machine_ID'])
            result = await self.db.execute(stmt)
            machine = result.scalar_one_or_none()

            if not machine:
                machine = Machine(
                    machine_id=row['Machine_ID'],
                    name=row['Machine_Name'],
                    type=row['Machine_Type'],
                    capacity=int(row['Machine_Capacity']),
                    availability=1 if factor > 0 else 0,
                    availability_factor=factor,
                )
                self.db.add(machine)
            else:
                machine.name = row['Machine_Name']
                machine.type = row['Machine_Type']
                machine.capacity = int(row['Machine_Capacity'])
                machine.availability = 1 if factor > 0 else 0
                machine.availability_factor = factor

    async def _upsert_workers(self, df: pd.DataFrame):
        """Upsert workers from dataframe (with mean fractional availability)."""
        from app.models.worker import WorkerAvailability

        workers_df = df[['Worker_ID', 'Worker_Name', 'Department', 'Shift']].drop_duplicates('Worker_ID', keep='last')
        if 'Worker_Availability' in df.columns:
            factors = pd.to_numeric(df['Worker_Availability'], errors='coerce').groupby(df['Worker_ID']).mean()
        else:
            factors = pd.Series(dtype=float)
        # A worker's home shift is the shift they appear on most often.
        home_shift = df.groupby('Worker_ID')['Shift'].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[-1])

        for _, row in workers_df.iterrows():
            factor = factors.get(row['Worker_ID'])
            factor = 1.0 if factor is None or pd.isna(factor) else float(min(max(factor, 0.0), 1.0))
            availability = WorkerAvailability.AVAILABLE if factor > 0 else WorkerAvailability.UNAVAILABLE
            shift = home_shift.get(row['Worker_ID'], row['Shift'])
            stmt = select(Worker).where(Worker.worker_id == row['Worker_ID'])
            result = await self.db.execute(stmt)
            worker = result.scalar_one_or_none()

            if not worker:
                worker = Worker(
                    worker_id=row['Worker_ID'],
                    name=row['Worker_Name'],
                    department=row['Department'],
                    shift=shift,
                    availability=availability,
                    availability_factor=factor,
                )
                self.db.add(worker)
            else:
                worker.name = row['Worker_Name']
                worker.department = row['Department']
                worker.shift = shift
                worker.availability = availability
                worker.availability_factor = factor

    async def _upsert_worker_skills(self, df: pd.DataFrame):
        """Upsert worker skills from dataframe"""
        # Create skills based on machine types workers have operated
        worker_machine = df[['Worker_ID', 'Machine_Type']].drop_duplicates()
        
        for _, row in worker_machine.iterrows():
            stmt = select(WorkerSkill).where(
                WorkerSkill.worker_id == row['Worker_ID'],
                WorkerSkill.machine_type == row['Machine_Type']
            )
            result = await self.db.execute(stmt)
            skill = result.scalar_one_or_none()
            
            if not skill:
                skill = WorkerSkill(
                    worker_id=row['Worker_ID'],
                    machine_type=row['Machine_Type'],
                    proficiency=1.0,
                    certified=1
                )
                self.db.add(skill)
    
    @staticmethod
    def _order_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
        today = datetime.utcnow().date()
        now = datetime.utcnow()
        rows = []
        for row in df.to_dict('records'):
            try:
                priority = OrderPriority(str(row['Priority']))
            except ValueError:
                priority = OrderPriority.MEDIUM
            try:
                status = OrderStatus(str(row['Status']))
            except ValueError:
                status = OrderStatus.PENDING
            rows.append({
                'id': uuid.uuid4(),
                'order_id': row['Order_ID'],
                'date': row['Date'].date() if pd.notna(row['Date']) else today,
                'product_id': row['Product_ID'],
                'demand': int(row['Demand']),
                'production_quantity': int(row['Production_Quantity']),
                'machine_id': row['Machine_ID'],
                'machine_availability': float(row['Machine_Availability']),
                'maintenance_status': row['Maintenance_Status'],
                'worker_id': row['Worker_ID'],
                'shift': row['Shift'],
                'worker_availability': float(row['Worker_Availability']),
                'production_time_minutes': int(row['Production_Time_Minutes']),
                'overtime_hours': int(round(float(row['Overtime_Hours']))),
                'production_cost': float(row['Production_Cost']),
                'machine_vibration': float(row['Machine_Vibration']),
                'machine_temperature_c': float(row['Machine_Temperature_C']),
                'machine_risk_score': float(row['Machine_Risk_Score']),
                'next_day_demand': int(row['Next_Day_Demand']),
                'priority': priority,
                'due_date': row['Due_Date'].date() if pd.notna(row['Due_Date']) else today,
                'status': status,
                'inventory_level': int(row['Inventory_Level']),
                'safety_stock': int(row['Safety_Stock']),
                'created_at': now,
                'updated_at': now,
            })
        return rows

    async def _upsert_orders(self, df: pd.DataFrame):
        """Bulk upsert orders (INSERT ... ON CONFLICT (order_id) DO UPDATE).

        Re-uploading a file now refreshes existing orders (status, fractional
        availability, ...) instead of silently keeping the old rows.
        """
        rows = self._order_rows(df)
        if not rows:
            return
        await self.db.flush()  # products/machines/workers must exist for the FKs
        update_columns = [c for c in rows[0] if c not in ('id', 'order_id', 'created_at')]
        for i in range(0, len(rows), _BULK_CHUNK):
            stmt = pg_insert(Order.__table__).values(rows[i:i + _BULK_CHUNK])
            stmt = stmt.on_conflict_do_update(
                index_elements=['order_id'],
                set_={c: stmt.excluded[c] for c in update_columns},
            )
            await self.db.execute(stmt)

    @staticmethod
    def _maintenance_rows(df: pd.DataFrame, reference_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """One maintenance event per (machine, date, type) flagged in Maintenance_Status.

        The source only gives a per-order flag ("Scheduled"/"Emergency"), so each
        event is a single day.  Events before the reference date are recorded as
        Completed, the rest as Scheduled.
        """
        if 'Maintenance_Status' not in df.columns:
            return []
        flagged = df[~df['Maintenance_Status'].astype(str).isin(NO_MAINTENANCE_VALUES)]
        if flagged.empty:
            return []
        reference = reference_date or planning_reference_date()
        now = datetime.utcnow()
        type_map = {'Scheduled': MaintenanceType.PREVENTIVE, 'Emergency': MaintenanceType.EMERGENCY}
        events = flagged.assign(_day=pd.to_datetime(flagged['Date'], errors='coerce').dt.date)
        events = events.dropna(subset=['_day']).drop_duplicates(['Machine_ID', '_day', 'Maintenance_Status'])
        rows = []
        for row in events.to_dict('records'):
            label = str(row['Maintenance_Status'])
            mtype = type_map.get(label, MaintenanceType.CORRECTIVE)
            day = row['_day']
            rows.append({
                'id': uuid.uuid4(),
                'maintenance_id': f"MNT-{row['Machine_ID']}-{day:%Y%m%d}-{label[:3].upper()}",
                'machine_id': row['Machine_ID'],
                'type': mtype,
                'status': MaintenanceStatus.COMPLETED if day < reference else MaintenanceStatus.SCHEDULED,
                'start_date': day,
                'end_date': day,
                'description': f"{label} maintenance flagged in uploaded data",
                'reason': f"Maintenance_Status={label} on order {row['Order_ID']}",
                'cost': 0.0,
                'completed_at': now if day < reference else None,
                'created_at': now,
                'updated_at': now,
            })
        return rows

    async def _upsert_maintenance(self, df: pd.DataFrame):
        rows = self._maintenance_rows(df)
        await self.db.flush()
        # Re-importing must replace (not accumulate) the events this file
        # derives: drop earlier data-derived events for the same machines and
        # date window, e.g. ones created by an older Maintenance_Status mapping.
        machine_ids = [str(m) for m in df['Machine_ID'].dropna().unique()] if 'Machine_ID' in df.columns else []
        days = pd.to_datetime(df['Date'], errors='coerce').dropna() if 'Date' in df.columns else pd.Series(dtype='datetime64[ns]')
        if machine_ids and not days.empty:
            await self.db.execute(
                delete(Maintenance).where(
                    Maintenance.machine_id.in_(machine_ids),
                    Maintenance.start_date >= days.min().date(),
                    Maintenance.start_date <= days.max().date(),
                    Maintenance.reason.like('Maintenance_Status=%'),
                )
            )
        update_columns = [c for c in rows[0] if c not in ('id', 'maintenance_id', 'created_at')] if rows else []
        for i in range(0, len(rows), _BULK_CHUNK):
            stmt = pg_insert(Maintenance.__table__).values(rows[i:i + _BULK_CHUNK])
            stmt = stmt.on_conflict_do_update(
                index_elements=['maintenance_id'],
                set_={c: stmt.excluded[c] for c in update_columns},
            )
            await self.db.execute(stmt)

        # Keep machine maintenance dates in sync with all stored events:
        # last = latest event before the reference date, next = first event on
        # or after it (never a date before the reference date).
        await self.db.flush()
        reference = planning_reference_date()
        for machine_id in machine_ids:
            machine = (await self.db.execute(
                select(Machine).where(Machine.machine_id == machine_id)
            )).scalar_one_or_none()
            if not machine:
                continue
            last_day = (await self.db.execute(
                select(func.max(Maintenance.start_date)).where(
                    Maintenance.machine_id == machine_id, Maintenance.start_date < reference
                )
            )).scalar()
            next_day = (await self.db.execute(
                select(func.min(Maintenance.start_date)).where(
                    Maintenance.machine_id == machine_id,
                    Maintenance.start_date >= reference,
                    Maintenance.status != MaintenanceStatus.CANCELLED,
                )
            )).scalar()
            machine.last_maintenance = datetime.combine(last_day, datetime.min.time()) if last_day else None
            machine.next_maintenance = datetime.combine(next_day, datetime.min.time()) if next_day else None

    # Service level for computed safety stock (z for 95% cycle service level).
    SAFETY_STOCK_Z = 1.65

    @classmethod
    def _inventory_rows(cls, df: pd.DataFrame, reference_date: Optional[date] = None) -> Dict[str, Dict[str, Any]]:
        """Per-product inventory figures derived from the order rows.

        - current_level: Inventory_Level on the latest order dated on/before the
          reference date (latest row overall if none), i.e. stock "as of now".
        - unit_cost: sum(Production_Cost) / sum(Production_Quantity) - the dataset's
          Production_Cost is the cost of the whole order.
        - safety_stock: the file's Safety_Stock when it has non-zero values,
          otherwise z * sigma(daily demand) * sqrt(lead time), where lead time is
          the mean Due_Date - Date in days (>= 1).
        - reorder_point: mean daily demand * lead time + safety stock.
        """
        reference = pd.Timestamp(reference_date or planning_reference_date())
        frame = df.copy()
        frame['_date'] = pd.to_datetime(frame['Date'], errors='coerce')
        frame['_demand'] = pd.to_numeric(frame['Demand'], errors='coerce').fillna(0)
        frame['_level'] = pd.to_numeric(frame.get('Inventory_Level', 0), errors='coerce').fillna(0)
        frame['_cost'] = pd.to_numeric(frame.get('Production_Cost', 0), errors='coerce').fillna(0)
        frame['_qty'] = pd.to_numeric(frame.get('Production_Quantity', 0), errors='coerce').fillna(0)
        frame['_ss'] = pd.to_numeric(frame.get('Safety_Stock', 0), errors='coerce').fillna(0)
        if 'Due_Date' in frame.columns:
            frame['_lead'] = (pd.to_datetime(frame['Due_Date'], errors='coerce') - frame['_date']).dt.days
        else:
            frame['_lead'] = np.nan
        frame = frame.dropna(subset=['_date'])

        rows: Dict[str, Dict[str, Any]] = {}
        for product_id, g in frame.groupby('Product_ID'):
            sort_cols = ['_date', 'Order_ID'] if 'Order_ID' in g.columns else ['_date']
            g = g.sort_values(sort_cols)
            as_of = g[g['_date'] <= reference]
            latest = (as_of if not as_of.empty else g).iloc[-1]
            daily = g.groupby('_date')['_demand'].sum()
            daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max()), fill_value=0)
            sigma = float(daily.std(ddof=1)) if len(daily) > 1 else 0.0
            mean_daily = float(daily.mean()) if len(daily) else 0.0
            lead = g['_lead'].dropna()
            lead_days = max(1.0, float(lead.mean())) if not lead.empty else 1.0
            file_ss = float(g['_ss'].max())
            safety = file_ss if file_ss > 0 else cls.SAFETY_STOCK_Z * sigma * float(np.sqrt(lead_days))
            qty = float(g['_qty'].sum())
            rows[str(product_id)] = {
                'current_level': int(round(float(latest['_level']))),
                'safety_stock': int(round(safety)),
                'reorder_point': int(round(mean_daily * lead_days + safety)),
                'unit_cost': round(float(g['_cost'].sum()) / qty, 2) if qty > 0 else 0.0,
            }
        return rows

    async def _update_inventory(self, df: pd.DataFrame):
        """Update inventory levels from dataframe (see _inventory_rows)."""
        for product_id, values in self._inventory_rows(df).items():
            stmt = select(Inventory).where(Inventory.product_id == product_id)
            result = await self.db.execute(stmt)
            inventory = result.scalar_one_or_none()

            if not inventory:
                inventory = Inventory(
                    product_id=product_id,
                    max_stock=int(values['current_level'] * 2),
                    **values,
                )
                self.db.add(inventory)
            else:
                for key, value in values.items():
                    setattr(inventory, key, value)
                inventory.max_stock = max(inventory.max_stock or 0, values['current_level'])
                inventory.last_updated = datetime.utcnow()

    async def _update_demand_history(self, df: pd.DataFrame):
        """Upsert daily product demand after aggregating duplicate order rows."""
        demand_data = df[['Product_ID', 'Date', 'Demand', 'Production_Quantity']].copy()
        demand_data['Date'] = pd.to_datetime(demand_data['Date'], errors='coerce')
        demand_data['Demand'] = pd.to_numeric(demand_data['Demand'], errors='coerce')
        demand_data['Production_Quantity'] = pd.to_numeric(
            demand_data['Production_Quantity'], errors='coerce'
        )
        if demand_data[['Product_ID', 'Date', 'Demand']].isnull().any().any():
            raise ValueError("Demand history contains missing or invalid date, product, or demand values")
        if demand_data['Demand'].lt(0).any():
            raise ValueError("Demand quantities must not be negative")
        demand_data['Date'] = demand_data['Date'].dt.date
        daily_demand = demand_data.groupby(
            ['Product_ID', 'Date'], as_index=False
        ).agg(
            Demand=('Demand', 'sum'),
            Production_Quantity=('Production_Quantity', 'sum'),
        )

        for _, row in daily_demand.iterrows():
            stmt = select(DemandHistory).where(
                DemandHistory.product_id == row['Product_ID'],
                DemandHistory.date == row['Date']
            )
            result = await self.db.execute(stmt)
            demand_hist = result.scalar_one_or_none()
            
            if not demand_hist:
                demand_hist = DemandHistory(
                    product_id=row['Product_ID'],
                    date=row['Date'],
                    demand=int(row['Demand']),
                    production_quantity=int(row['Production_Quantity'])
                )
                self.db.add(demand_hist)
            else:
                demand_hist.demand = int(row['Demand'])
                demand_hist.production_quantity = int(row['Production_Quantity'])