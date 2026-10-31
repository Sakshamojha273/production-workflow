import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os

from app.models.order import Order
from app.models.machine import Machine
from app.core.config import settings


class MachineRiskAnalyzer:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.model_path = settings.ML_MODEL_PATH
        os.makedirs(self.model_path, exist_ok=True)
    
    async def analyze_machine_risk(self, machine_ids: Optional[List[str]] = None) -> List[Dict]:
        """Analyze risk for machines based on sensor data"""
        
        # Get recent order data with machine sensor readings
        machine_data = await self._get_machine_sensor_data(machine_ids)
        
        if machine_data.empty:
            return []
        
        results = []
        
        for machine_id in machine_data['machine_id'].unique():
            m_data = machine_data[machine_data['machine_id'] == machine_id].copy()
            m_data = m_data.sort_values('date')
            
            risk_analysis = self._calculate_risk_score(m_data)
            
            # Update machine record
            stmt = select(Machine).where(Machine.machine_id == machine_id)
            result = await self.db.execute(stmt)
            machine = result.scalar_one_or_none()
            
            if machine:
                machine.vibration = risk_analysis['current_vibration']
                machine.temperature_c = risk_analysis['current_temperature']
                machine.risk_score = risk_analysis['risk_score']
                machine.updated_at = datetime.utcnow()
            
            results.append({
                'machine_id': machine_id,
                'machine_name': m_data['machine_name'].iloc[-1],
                'machine_type': m_data['machine_type'].iloc[-1],
                'capacity': int(m_data['machine_capacity'].iloc[-1]),
                'availability': int(m_data['machine_availability'].iloc[-1]),
                'current_vibration': risk_analysis['current_vibration'],
                'current_temperature': risk_analysis['current_temperature'],
                'risk_score': risk_analysis['risk_score'],
                'risk_category': risk_analysis['risk_category'],
                'trend': risk_analysis['trend'],
                'anomaly_detected': risk_analysis['anomaly_detected'],
                'maintenance_recommended': risk_analysis['maintenance_recommended']
            })
        
        await self.db.commit()
        return results
    
    async def _get_machine_sensor_data(self, machine_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """Get machine sensor readings from the most recent 30 days of order data.

        Machine attributes come from the ``machines`` table (orders only carry
        the machine ID).  The window ends at today or at the latest recorded
        order date, whichever is earlier, so future-dated rows are never used
        as the "current" reading.
        """
        latest_stmt = select(func.max(Order.date)).where(Order.date <= date.today())
        if machine_ids:
            latest_stmt = latest_stmt.where(Order.machine_id.in_(machine_ids))
        window_end = (await self.db.execute(latest_stmt)).scalar()
        if window_end is None:
            return pd.DataFrame()
        window_start = window_end - timedelta(days=30)

        stmt = select(Order, Machine).join(Machine, Order.machine_id == Machine.machine_id).where(
            Order.date >= window_start,
            Order.date <= window_end,
        )
        if machine_ids:
            stmt = stmt.where(Order.machine_id.in_(machine_ids))
        stmt = stmt.order_by(Order.machine_id, Order.date)

        result = await self.db.execute(stmt)
        records = result.all()

        if not records:
            return pd.DataFrame()

        hours_per_day = len(settings.PLANNING_SHIFTS) * settings.PLANNING_SHIFT_HOURS
        data = [{
            'machine_id': order.machine_id,
            'machine_name': machine.name,
            'machine_type': machine.type,
            'machine_capacity': machine.capacity,
            'machine_availability': machine.availability,
            'maintenance_status': order.maintenance_status,
            'date': order.date,
            'vibration': order.machine_vibration,
            'temperature': order.machine_temperature_c,
            'risk_score': order.machine_risk_score,
            'production_qty': order.production_quantity,
            # capacity is units/hour; utilisation is relative to a full production day
            'utilization': (
                order.production_quantity / (machine.capacity * hours_per_day)
                if machine.capacity and machine.capacity > 0 else 0
            ),
        } for order, machine in records]

        return pd.DataFrame(data)

    def _calculate_risk_score(self, data: pd.DataFrame) -> Dict:
        """Calculate machine risk score based on sensor data"""
        if data.empty:
            return {
                'current_vibration': 0.1,
                'current_temperature': 40.0,
                'risk_score': 0.0,
                'risk_category': 'Low',
                'trend': 'stable',
                'anomaly_detected': False,
                'maintenance_recommended': False
            }
        
        # Current values
        current_vibration = float(data['vibration'].iloc[-1])
        current_temperature = float(data['temperature'].iloc[-1])
        current_risk = float(data['risk_score'].iloc[-1]) if 'risk_score' in data.columns else 0.0
        
        # Trends
        vibration_trend = self._calculate_trend(data['vibration'].values)
        temperature_trend = self._calculate_trend(data['temperature'].values)
        
        # Anomaly detection using Isolation Forest
        anomaly_detected = False
        if len(data) >= 10:
            features = data[['vibration', 'temperature', 'utilization']].fillna(0)
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            anomalies = iso_forest.fit_predict(features_scaled)
            anomaly_detected = bool(anomalies[-1] == -1)  # plain bool for JSON
        
        # Risk score calculation (0-1)
        # Based on vibration, temperature, and their trends
        vib_norm = min(current_vibration / 0.5, 1.0)  # Normalize to max 0.5
        temp_norm = min(max((current_temperature - 35) / 35, 0), 1.0)  # Normalize 35-70C
        
        trend_factor = 0
        if vibration_trend > 0.01:
            trend_factor += 0.1
        if temperature_trend > 0.5:
            trend_factor += 0.1
        
        anomaly_factor = 0.2 if anomaly_detected else 0
        
        # Maintenance status factor
        maint_factor = 0
        if 'maintenance_status' in data.columns:
            recent_maint = data['maintenance_status'].iloc[-1]
            if recent_maint == 'Maintenance':
                maint_factor = 0.3
            elif recent_maint == 'Offline':
                maint_factor = 0.5
        
        risk_score = min(1.0, (vib_norm * 0.3 + temp_norm * 0.3 + trend_factor + anomaly_factor + maint_factor + current_risk * 0.2))
        
        # Risk category
        if risk_score < 0.3:
            risk_category = 'Low'
        elif risk_score < 0.6:
            risk_category = 'Medium'
        else:
            risk_category = 'High'
        
        # Overall trend
        if vibration_trend > 0.01 and temperature_trend > 0.5:
            trend = 'increasing'
        elif vibration_trend < -0.01 and temperature_trend < -0.5:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        # Maintenance recommendation
        maintenance_recommended = bool(risk_score > 0.5 or anomaly_detected or maint_factor > 0)
        
        return {
            'current_vibration': current_vibration,
            'current_temperature': current_temperature,
            'risk_score': round(float(risk_score), 3),
            'risk_category': risk_category,
            'trend': trend,
            'anomaly_detected': anomaly_detected,
            'maintenance_recommended': maintenance_recommended
        }
    
    def _calculate_trend(self, values: np.ndarray) -> float:
        """Calculate linear trend slope"""
        if len(values) < 2:
            return 0.0
        x = np.arange(len(values))
        y = values
        slope = np.polyfit(x, y, 1)[0]
        return float(slope)
    
    async def get_risk_distribution(self) -> Dict:
        """Get distribution of risk categories across all machines"""
        stmt = select(Machine)
        result = await self.db.execute(stmt)
        machines = result.scalars().all()
        
        distribution = {'Low': 0, 'Medium': 0, 'High': 0}
        for m in machines:
            if m.risk_score < 0.3:
                distribution['Low'] += 1
            elif m.risk_score < 0.6:
                distribution['Medium'] += 1
            else:
                distribution['High'] += 1
        
        return distribution
    
    async def get_maintenance_timeline(self, days: int = 30) -> List[Dict]:
        """Get upcoming maintenance timeline"""
        from app.models.maintenance import Maintenance, MaintenanceStatus
        
        stmt = select(Maintenance).where(
            Maintenance.start_date >= date.today(),
            Maintenance.start_date <= date.today() + timedelta(days=days),
            Maintenance.status.in_([MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS])
        ).order_by(Maintenance.start_date)
        
        result = await self.db.execute(stmt)
        maintenance = result.scalars().all()
        
        return [{
            'maintenance_id': m.maintenance_id,
            'machine_id': m.machine_id,
            'type': m.type.value,
            'status': m.status.value,
            'start_date': m.start_date.isoformat(),
            'end_date': m.end_date.isoformat(),
            'description': m.description,
            'reason': m.reason
        } for m in maintenance]