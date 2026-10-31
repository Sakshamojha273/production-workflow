import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from datetime import date, datetime
from typing import Optional
import json
import io
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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
from app.core.config import settings


# "None" is a real category in the source data (Maintenance_Status = no
# maintenance), so it must not be parsed as a missing value.  Everything else in
# pandas' default NA list is still treated as missing.
CSV_NA_VALUES = [
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND",
    "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "n/a", "nan", "null",
]
NO_MAINTENANCE_VALUES = {"None", "none", "Operational", "", "Unknown"}
_BULK_CHUNK = 1000


def planning_reference_date() -> date:
    return settings.PLANNING_REFERENCE_DATE or date.today()


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
            status = df['Maintenance_Status'].fillna('Operational').astype(str).str.strip()
            df['Maintenance_Status'] = status.where(~status.isin(NO_MAINTENANCE_VALUES), 'Operational')
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
        if not rows:
            return
        await self.db.flush()
        update_columns = [c for c in rows[0] if c not in ('id', 'maintenance_id', 'created_at')]
        for i in range(0, len(rows), _BULK_CHUNK):
            stmt = pg_insert(Maintenance.__table__).values(rows[i:i + _BULK_CHUNK])
            stmt = stmt.on_conflict_do_update(
                index_elements=['maintenance_id'],
                set_={c: stmt.excluded[c] for c in update_columns},
            )
            await self.db.execute(stmt)

        # Keep machine maintenance dates in sync with the events.
        reference = planning_reference_date()
        by_machine: Dict[str, List[date]] = {}
        for r in rows:
            by_machine.setdefault(r['machine_id'], []).append(r['start_date'])
        for machine_id, days in by_machine.items():
            machine = (await self.db.execute(
                select(Machine).where(Machine.machine_id == machine_id)
            )).scalar_one_or_none()
            if not machine:
                continue
            past = [d for d in days if d < reference]
            future = [d for d in days if d >= reference]
            machine.last_maintenance = datetime.combine(max(past), datetime.min.time()) if past else None
            machine.next_maintenance = datetime.combine(min(future), datetime.min.time()) if future else None

    async def _update_inventory(self, df: pd.DataFrame):
        """Update inventory levels from dataframe"""
        inventory_df = df[['Product_ID', 'Inventory_Level', 'Safety_Stock']].drop_duplicates()
        
        for _, row in inventory_df.iterrows():
            stmt = select(Inventory).where(Inventory.product_id == row['Product_ID'])
            result = await self.db.execute(stmt)
            inventory = result.scalar_one_or_none()
            
            if not inventory:
                inventory = Inventory(
                    product_id=row['Product_ID'],
                    current_level=int(row['Inventory_Level']),
                    safety_stock=int(row['Safety_Stock']),
                    reorder_point=int(row['Safety_Stock'] * 1.5),
                    max_stock=int(row['Inventory_Level'] * 2)
                )
                self.db.add(inventory)
            else:
                inventory.current_level = int(row['Inventory_Level'])
                inventory.safety_stock = int(row['Safety_Stock'])
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