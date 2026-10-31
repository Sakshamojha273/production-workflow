import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from collections import defaultdict

from app.models.order import Order, OrderPriority, OrderStatus
from app.models.product import Product
from app.models.machine import Machine
from app.models.worker import Worker
from app.models.inventory import Inventory
from app.models.demand_history import DemandHistory
from app.models.forecast import Forecast
from app.models.production_plan import ProductionPlan
from app.models.optimization_run import OptimizationRun
from app.models.maintenance import Maintenance


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_dashboard_kpis(self) -> Dict[str, Any]:
        """Get all KPI cards for dashboard"""
        
        # Total orders
        stmt = select(func.count(Order.id)).where(
            Order.date >= date.today() - timedelta(days=30)
        )
        result = await self.db.execute(stmt)
        total_orders = result.scalar() or 0
        
        # Production planned (last 30 days)
        stmt = select(func.sum(Order.production_quantity)).where(
            Order.date >= date.today() - timedelta(days=30)
        )
        result = await self.db.execute(stmt)
        production_planned = result.scalar() or 0
        
        # Use the most recently generated forecast for each product.
        latest_product_forecasts = (
            select(
                Forecast.product_id,
                func.max(Forecast.created_at).label("latest_created_at"),
            )
            .group_by(Forecast.product_id)
            .subquery()
        )
        stmt = select(func.sum(Forecast.predicted_demand)).join(
            latest_product_forecasts,
            and_(
                Forecast.product_id == latest_product_forecasts.c.product_id,
                Forecast.created_at == latest_product_forecasts.c.latest_created_at,
            ),
        ).where(Forecast.forecast_horizon_days <= 7)
        result = await self.db.execute(stmt)
        demand_forecast = result.scalar() or 0

        latest_demand_date_result = await self.db.execute(
            select(func.max(DemandHistory.date))
        )
        latest_demand_date = latest_demand_date_result.scalar()
        current_demand = 0
        historical_daily_average = 0.0
        if latest_demand_date:
            current_demand_result = await self.db.execute(
                select(func.sum(DemandHistory.demand)).where(
                    DemandHistory.date == latest_demand_date
                )
            )
            current_demand = current_demand_result.scalar() or 0
            history_window_result = await self.db.execute(
                select(
                    func.sum(DemandHistory.demand),
                    func.count(func.distinct(DemandHistory.date)),
                ).where(
                    DemandHistory.date > latest_demand_date - timedelta(days=30),
                    DemandHistory.date <= latest_demand_date,
                )
            )
            history_total, observed_days = history_window_result.one()
            if observed_days:
                historical_daily_average = float(history_total or 0) / observed_days
        forecast_daily_average = demand_forecast / 7
        forecast_growth = (
            (forecast_daily_average - historical_daily_average)
            / historical_daily_average * 100
            if historical_daily_average
            else 0.0
        )
        
        # Machine utilization
        stmt = select(func.avg(Machine.utilization)).where(Machine.availability == 1)
        result = await self.db.execute(stmt)
        machine_util = result.scalar() or 0
        
        # Workforce utilization (from recent plans)
        stmt = select(func.avg(ProductionPlan.workforce_utilization)).where(
            ProductionPlan.created_at >= date.today() - timedelta(days=30)
        )
        result = await self.db.execute(stmt)
        workforce_util = result.scalar() or 0
        
        # Inventory level
        stmt = select(func.sum(Inventory.current_level))
        result = await self.db.execute(stmt)
        inventory_level = result.scalar() or 0
        
        # Overtime hours (last 30 days)
        stmt = select(func.sum(Order.overtime_hours)).where(
            Order.date >= date.today() - timedelta(days=30)
        )
        result = await self.db.execute(stmt)
        overtime_hours = result.scalar() or 0
        
        # Late orders
        stmt = select(func.count(Order.id)).where(
            Order.status == OrderStatus.DELAYED,
            Order.date >= date.today() - timedelta(days=30)
        )
        result = await self.db.execute(stmt)
        late_orders = result.scalar() or 0
        
        # Calculate trends (compare with previous period)
        prev_start = date.today() - timedelta(days=60)
        prev_end = date.today() - timedelta(days=30)
        
        trends = await self._calculate_trends(prev_start, prev_end, date.today() - timedelta(days=30), date.today())
        trends["demand_forecast"] = forecast_growth
        
        return {
            "total_orders": {
                "title": "Total Orders",
                "value": f"{total_orders:,}",
                "trend": trends.get("total_orders", 0),
                "trend_direction": "up" if trends.get("total_orders", 0) > 0 else "down" if trends.get("total_orders", 0) < 0 else "neutral",
                "description": "Last 30 days",
                "status": "Healthy"
            },
            "production_planned": {
                "title": "Production Planned",
                "value": f"{production_planned:,}",
                "trend": trends.get("production_planned", 0),
                "trend_direction": "up" if trends.get("production_planned", 0) > 0 else "down" if trends.get("production_planned", 0) < 0 else "neutral",
                "description": "Last 30 days",
                "status": "Healthy"
            },
            "current_demand": {
                "title": "Current Demand",
                "value": f"{current_demand:,}",
                "trend": None,
                "trend_direction": "neutral",
                "description": f"Most recent recorded day ({latest_demand_date})" if latest_demand_date else "No historical demand",
                "status": "Healthy"
            },
            "demand_forecast": {
                "title": "Demand Forecast",
                "value": f"{demand_forecast:,}",
                "trend": trends.get("demand_forecast", 0),
                "trend_direction": "up" if trends.get("demand_forecast", 0) > 0 else "down" if trends.get("demand_forecast", 0) < 0 else "neutral",
                "description": "Next 7 days",
                "status": "Healthy"
            },
            "demand_growth": {
                "title": "Expected Demand Growth",
                "value": f"{forecast_growth:+.1f}%",
                "trend": forecast_growth,
                "trend_direction": "up" if forecast_growth > 0 else "down" if forecast_growth < 0 else "neutral",
                "description": "Forecast vs. recent daily average; estimate",
                "status": "Healthy"
            },
            "machine_utilization": {
                "title": "Machine Utilization",
                "value": f"{machine_util:.1f}%",
                "trend": trends.get("machine_utilization", 0),
                "trend_direction": "up" if trends.get("machine_utilization", 0) > 0 else "down" if trends.get("machine_utilization", 0) < 0 else "neutral",
                "description": "Current average",
                "status": "Healthy" if machine_util > 70 else "Warning" if machine_util > 50 else "Critical"
            },
            "workforce_utilization": {
                "title": "Workforce Utilization",
                "value": f"{workforce_util:.1f}%",
                "trend": trends.get("workforce_utilization", 0),
                "trend_direction": "up" if trends.get("workforce_utilization", 0) > 0 else "down" if trends.get("workforce_utilization", 0) < 0 else "neutral",
                "description": "Recent plans average",
                "status": "Healthy" if workforce_util > 70 else "Warning" if workforce_util > 50 else "Critical"
            },
            "inventory_level": {
                "title": "Inventory Level",
                "value": f"{inventory_level:,}",
                "trend": trends.get("inventory_level", 0),
                "trend_direction": "up" if trends.get("inventory_level", 0) > 0 else "down" if trends.get("inventory_level", 0) < 0 else "neutral",
                "description": "Current total",
                "status": "Healthy"
            },
            "overtime_hours": {
                "title": "Overtime Hours",
                "value": f"{overtime_hours:,}",
                "trend": trends.get("overtime_hours", 0),
                "trend_direction": "down" if trends.get("overtime_hours", 0) > 0 else "up" if trends.get("overtime_hours", 0) < 0 else "neutral",
                "description": "Last 30 days (lower is better)",
                "status": "Healthy" if overtime_hours < 100 else "Warning" if overtime_hours < 200 else "Critical"
            },
            "late_orders": {
                "title": "Late Orders",
                "value": f"{late_orders:,}",
                "trend": trends.get("late_orders", 0),
                "trend_direction": "down" if trends.get("late_orders", 0) > 0 else "up" if trends.get("late_orders", 0) < 0 else "neutral",
                "description": "Last 30 days (lower is better)",
                "status": "Healthy" if late_orders < 5 else "Warning" if late_orders < 15 else "Critical"
            }
        }
    
    async def _calculate_trends(
        self,
        prev_start: date,
        prev_end: date,
        curr_start: date,
        curr_end: date
    ) -> Dict[str, float]:
        """Calculate percentage trends between two periods"""
        trends = {}
        
        # Total orders
        curr_orders = await self._count_orders(curr_start, curr_end)
        prev_orders = await self._count_orders(prev_start, prev_end)
        trends["total_orders"] = ((curr_orders - prev_orders) / max(1, prev_orders)) * 100
        
        # Production planned
        curr_prod = await self._sum_production(curr_start, curr_end)
        prev_prod = await self._sum_production(prev_start, prev_end)
        trends["production_planned"] = ((curr_prod - prev_prod) / max(1, prev_prod)) * 100
        
        # Machine utilization (average over period)
        curr_machine_util = await self._avg_machine_util(curr_start, curr_end)
        prev_machine_util = await self._avg_machine_util(prev_start, prev_end)
        trends["machine_utilization"] = curr_machine_util - prev_machine_util
        
        # Workforce utilization
        curr_workforce_util = await self._avg_workforce_util(curr_start, curr_end)
        prev_workforce_util = await self._avg_workforce_util(prev_start, prev_end)
        trends["workforce_utilization"] = curr_workforce_util - prev_workforce_util
        
        # Inventory level (current vs previous)
        curr_inv = await self._current_inventory()
        prev_inv = await self._inventory_at_date(prev_end)
        trends["inventory_level"] = ((curr_inv - prev_inv) / max(1, prev_inv)) * 100
        
        # Overtime
        curr_ot = await self._sum_overtime(curr_start, curr_end)
        prev_ot = await self._sum_overtime(prev_start, prev_end)
        trends["overtime_hours"] = ((curr_ot - prev_ot) / max(1, prev_ot)) * 100
        
        # Late orders
        curr_late = await self._count_late_orders(curr_start, curr_end)
        prev_late = await self._count_late_orders(prev_start, prev_end)
        trends["late_orders"] = ((curr_late - prev_late) / max(1, prev_late)) * 100
        
        # Demand forecast (next 7 vs previous 7)
        curr_forecast = await self._sum_forecast(date.today(), date.today() + timedelta(days=7))
        prev_forecast = await self._sum_forecast(date.today() - timedelta(days=7), date.today())
        trends["demand_forecast"] = ((curr_forecast - prev_forecast) / max(1, prev_forecast)) * 100
        
        return trends
    
    async def _count_orders(self, start: date, end: date) -> int:
        stmt = select(func.count(Order.id)).where(
            Order.date >= start,
            Order.date <= end
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def _sum_production(self, start: date, end: date) -> int:
        stmt = select(func.sum(Order.production_quantity)).where(
            Order.date >= start,
            Order.date <= end
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def _avg_machine_util(self, start: date, end: date) -> float:
        # Simplified - would calculate from production data
        stmt = select(func.avg(Machine.utilization))
        result = await self.db.execute(stmt)
        return float(result.scalar() or 0)
    
    async def _avg_workforce_util(self, start: date, end: date) -> float:
        stmt = select(func.avg(ProductionPlan.workforce_utilization)).where(
            ProductionPlan.created_at >= start,
            ProductionPlan.created_at <= end
        )
        result = await self.db.execute(stmt)
        return float(result.scalar() or 0)
    
    async def _current_inventory(self) -> int:
        stmt = select(func.sum(Inventory.current_level))
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def _inventory_at_date(self, d: date) -> int:
        # Simplified
        return await self._current_inventory()
    
    async def _sum_overtime(self, start: date, end: date) -> int:
        stmt = select(func.sum(Order.overtime_hours)).where(
            Order.date >= start,
            Order.date <= end
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def _count_late_orders(self, start: date, end: date) -> int:
        stmt = select(func.count(Order.id)).where(
            Order.status == OrderStatus.DELAYED,
            Order.date >= start,
            Order.date <= end
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def _sum_forecast(self, start: date, end: date) -> int:
        stmt = select(func.sum(Forecast.predicted_demand)).where(
            Forecast.forecast_date >= start,
            Forecast.forecast_date <= end
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def get_chart_data(self) -> Dict[str, Any]:
        """Get all chart data for dashboard"""
        
        charts = {}
        
        # 1. Demand vs Production (last 30 days)
        charts["demand_vs_production"] = await self._get_demand_vs_production_chart()
        
        # 2. Production by Product
        charts["production_by_product"] = await self._get_production_by_product_chart()
        
        # 3. Machine Utilization
        charts["machine_utilization"] = await self._get_machine_utilization_chart()
        
        # 4. Workforce Utilization
        charts["workforce_utilization"] = await self._get_workforce_utilization_chart()
        
        # 5. Production Cost Trend
        charts["production_cost_trend"] = await self._get_production_cost_trend_chart()
        
        # 6. Overtime Trend
        charts["overtime_trend"] = await self._get_overtime_trend_chart()
        
        # 7. Machine Risk Distribution
        charts["machine_risk_distribution"] = await self._get_machine_risk_distribution_chart()
        
        # 8. Orders by Priority
        charts["orders_by_priority"] = await self._get_orders_by_priority_chart()
        
        # 9. Inventory Status
        charts["inventory_status"] = await self._get_inventory_status_chart()
        
        # 10. Upcoming Maintenance
        charts["upcoming_maintenance"] = await self._get_upcoming_maintenance_chart()
        
        return charts
    
    async def _get_demand_vs_production_chart(self) -> Dict:
        """Get demand vs production line chart data"""
        stmt = select(
            Order.date,
            func.sum(Order.demand).label('total_demand'),
            func.sum(Order.production_quantity).label('total_production')
        ).where(
            Order.date >= date.today() - timedelta(days=30)
        ).group_by(Order.date).order_by(Order.date)
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        return {
            "type": "line",
            "data": {
                "labels": [str(row.date) for row in data],
                "datasets": [
                    {"label": "Demand", "data": [row.total_demand for row in data], "borderColor": "#3b82f6"},
                    {"label": "Production", "data": [row.total_production for row in data], "borderColor": "#22c55e"}
                ]
            }
        }
    
    async def _get_production_by_product_chart(self) -> Dict:
        """Get production by product bar chart"""
        stmt = select(
            Order.product_id,
            func.sum(Order.production_quantity).label('total_production')
        ).where(
            Order.date >= date.today() - timedelta(days=30)
        ).group_by(Order.product_id).order_by(func.sum(Order.production_quantity).desc())
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        # Get product names
        product_ids = [row.product_id for row in data]
        stmt = select(Product).where(Product.product_id.in_(product_ids))
        result = await self.db.execute(stmt)
        products = {p.product_id: p.name for p in result.scalars().all()}
        
        return {
            "type": "bar",
            "data": {
                "labels": [products.get(row.product_id, row.product_id) for row in data],
                "datasets": [{
                    "label": "Production Quantity",
                    "data": [row.total_production for row in data],
                    "backgroundColor": "#3b82f6"
                }]
            }
        }
    
    async def _get_machine_utilization_chart(self) -> Dict:
        """Get machine utilization chart"""
        stmt = select(Machine.machine_id, Machine.name, Machine.utilization).where(
            Machine.availability == 1
        ).order_by(Machine.utilization.desc())
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        return {
            "type": "bar",
            "data": {
                "labels": [row.name for row in data],
                "datasets": [{
                    "label": "Utilization %",
                    "data": [round(row.utilization, 1) for row in data],
                    "backgroundColor": ["#22c55e" if u >= 80 else "#f59e0b" if u >= 60 else "#ef4444" for u in [row.utilization for row in data]]
                }]
            }
        }
    
    async def _get_workforce_utilization_chart(self) -> Dict:
        """Get workforce utilization chart"""
        stmt = select(Worker.worker_id, Worker.name, Worker.current_hours, Worker.max_hours_per_week).where(
            Worker.availability == "Available"
        )
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        utilizations = [(row.current_hours / max(1, row.max_hours_per_week) * 100) for row in data]
        
        return {
            "type": "bar",
            "data": {
                "labels": [row.name for row in data],
                "datasets": [{
                    "label": "Utilization %",
                    "data": [round(u, 1) for u in utilizations],
                    "backgroundColor": ["#22c55e" if u >= 80 else "#f59e0b" if u >= 60 else "#ef4444" for u in utilizations]
                }]
            }
        }
    
    async def _get_production_cost_trend_chart(self) -> Dict:
        """Get production cost trend"""
        stmt = select(
            Order.date,
            func.avg(Order.production_cost).label('avg_cost')
        ).where(
            Order.date >= date.today() - timedelta(days=30)
        ).group_by(Order.date).order_by(Order.date)
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        return {
            "type": "line",
            "data": {
                "labels": [str(row.date) for row in data],
                "datasets": [{
                    "label": "Avg Production Cost",
                    "data": [round(row.avg_cost, 2) for row in data],
                    "borderColor": "#8b5cf6"
                }]
            }
        }
    
    async def _get_overtime_trend_chart(self) -> Dict:
        """Get overtime trend"""
        stmt = select(
            Order.date,
            func.sum(Order.overtime_hours).label('total_overtime')
        ).where(
            Order.date >= date.today() - timedelta(days=30)
        ).group_by(Order.date).order_by(Order.date)
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        return {
            "type": "line",
            "data": {
                "labels": [str(row.date) for row in data],
                "datasets": [{
                    "label": "Overtime Hours",
                    "data": [row.total_overtime for row in data],
                    "borderColor": "#ef4444"
                }]
            }
        }
    
    async def _get_machine_risk_distribution_chart(self) -> Dict:
        """Get machine risk distribution"""
        stmt = select(Machine.risk_score)
        result = await self.db.execute(stmt)
        scores = [row[0] for row in result.all()]
        
        low = sum(1 for s in scores if s < 0.3)
        medium = sum(1 for s in scores if 0.3 <= s < 0.6)
        high = sum(1 for s in scores if s >= 0.6)
        
        return {
            "type": "doughnut",
            "data": {
                "labels": ["Low", "Medium", "High"],
                "datasets": [{
                    "data": [low, medium, high],
                    "backgroundColor": ["#22c55e", "#f59e0b", "#ef4444"]
                }]
            }
        }
    
    async def _get_orders_by_priority_chart(self) -> Dict:
        """Get orders by priority"""
        stmt = select(
            Order.priority,
            func.count(Order.id).label('count')
        ).where(
            Order.date >= date.today() - timedelta(days=30)
        ).group_by(Order.priority)
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        priority_map = {"Low": 0, "Medium": 0, "High": 0}
        for row in data:
            priority_map[row.priority.value] = row.count
        
        return {
            "type": "doughnut",
            "data": {
                "labels": ["High", "Medium", "Low"],
                "datasets": [{
                    "data": [priority_map["High"], priority_map["Medium"], priority_map["Low"]],
                    "backgroundColor": ["#ef4444", "#f59e0b", "#22c55e"]
                }]
            }
        }
    
    async def _get_inventory_status_chart(self) -> Dict:
        """Get inventory status"""
        stmt = select(Inventory.current_level, Inventory.safety_stock, Product.name).join(
            Product, Inventory.product_id == Product.product_id
        )
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        healthy = low = critical = 0
        for row in data:
            if row.current_level > row.safety_stock * 1.5:
                healthy += 1
            elif row.current_level > row.safety_stock:
                low += 1
            else:
                critical += 1
        
        return {
            "type": "bar",
            "data": {
                "labels": ["Healthy", "Low", "Critical"],
                "datasets": [{
                    "label": "Products",
                    "data": [healthy, low, critical],
                    "backgroundColor": ["#22c55e", "#f59e0b", "#ef4444"]
                }]
            }
        }
    
    async def _get_upcoming_maintenance_chart(self) -> Dict:
        """Get upcoming maintenance timeline"""
        stmt = select(
            Maintenance.machine_id,
            Maintenance.type,
            Maintenance.start_date,
            Maintenance.end_date,
            Maintenance.status
        ).where(
            Maintenance.start_date >= date.today(),
            Maintenance.start_date <= date.today() + timedelta(days=30)
        ).order_by(Maintenance.start_date).limit(10)
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        return {
            "type": "timeline",
            "data": [{
                "machine_id": row.machine_id,
                "type": row.type.value,
                "start": str(row.start_date),
                "end": str(row.end_date),
                "status": row.status.value
            } for row in data]
        }
    
    async def get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary"""
        
        # Demand growth
        current_month_demand = await self._sum_demand(date.today().replace(day=1), date.today())
        last_month_start = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month_end = date.today().replace(day=1) - timedelta(days=1)
        last_month_demand = await self._sum_demand(last_month_start, last_month_end)
        demand_growth = ((current_month_demand - last_month_demand) / max(1, last_month_demand)) * 100
        
        # Production fulfillment %
        total_demand = await self._sum_demand(date.today() - timedelta(days=30), date.today())
        total_production = await self._sum_production(date.today() - timedelta(days=30), date.today())
        fulfillment_pct = (total_production / max(1, total_demand)) * 100
        
        # Machine utilization
        machine_util = await self._avg_machine_util(date.today() - timedelta(days=30), date.today())
        
        # Worker utilization
        worker_util = await self._avg_workforce_util(date.today() - timedelta(days=30), date.today())
        
        # Inventory coverage
        inventory_coverage = await self._calculate_inventory_coverage()
        
        # Overtime %
        total_hours = await self._sum_production_hours(date.today() - timedelta(days=30), date.today())
        overtime_hours = await self._sum_overtime(date.today() - timedelta(days=30), date.today())
        overtime_pct = (overtime_hours / max(1, total_hours)) * 100
        
        # Late order %
        total_orders = await self._count_orders(date.today() - timedelta(days=30), date.today())
        late_orders = await self._count_late_orders(date.today() - timedelta(days=30), date.today())
        late_order_pct = (late_orders / max(1, total_orders)) * 100
        
        # Production cost
        avg_cost = await self._avg_production_cost(date.today() - timedelta(days=30), date.today())
        
        # Avg production time
        avg_time = await self._avg_production_time(date.today() - timedelta(days=30), date.today())
        
        # Machine risk distribution
        risk_dist = await self._get_machine_risk_distribution()
        
        return {
            "demand_growth": round(demand_growth, 2),
            "production_fulfillment_pct": round(fulfillment_pct, 2),
            "machine_utilization": round(machine_util, 2),
            "worker_utilization": round(worker_util, 2),
            "inventory_coverage": round(inventory_coverage, 2),
            "overtime_pct": round(overtime_pct, 2),
            "late_order_pct": round(late_order_pct, 2),
            "avg_production_cost": round(avg_cost, 2),
            "avg_production_time": round(avg_time, 2),
            "machine_risk_distribution": risk_dist
        }
    
    async def _sum_demand(self, start: date, end: date) -> int:
        stmt = select(func.sum(Order.demand)).where(
            Order.date >= start,
            Order.date <= end
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def _sum_production_hours(self, start: date, end: date) -> float:
        stmt = select(func.sum(Order.production_time_minutes)).where(
            Order.date >= start,
            Order.date <= end
        )
        result = await self.db.execute(stmt)
        minutes = result.scalar() or 0
        return minutes / 60
    
    async def _avg_production_cost(self, start: date, end: date) -> float:
        stmt = select(func.avg(Order.production_cost)).where(
            Order.date >= start,
            Order.date <= end
        )
        result = await self.db.execute(stmt)
        return float(result.scalar() or 0)
    
    async def _avg_production_time(self, start: date, end: date) -> float:
        stmt = select(func.avg(Order.production_time_minutes)).where(
            Order.date >= start,
            Order.date <= end
        )
        result = await self.db.execute(stmt)
        return float(result.scalar() or 0)
    
    async def _calculate_inventory_coverage(self) -> float:
        stmt = select(Inventory.product_id, Inventory.current_level, Inventory.safety_stock).join(
            Product, Inventory.product_id == Product.product_id
        )
        result = await self.db.execute(stmt)
        data = result.all()
        
        if not data:
            return 0.0
        
        coverages = []
        for row in data:
            daily_demand = await self._get_avg_daily_demand(row.product_id)
            if daily_demand > 0:
                coverage = row.current_level / daily_demand
                coverages.append(coverage)
        
        return float(np.mean(coverages)) if coverages else 0.0
    
    async def _get_avg_daily_demand(self, product_id: str) -> float:
        stmt = select(func.avg(DemandHistory.demand)).where(
            DemandHistory.product_id == product_id,
            DemandHistory.date >= date.today() - timedelta(days=30),
            DemandHistory.date <= date.today(),
        )
        result = await self.db.execute(stmt)
        return float(result.scalar() or 0)
    
    async def _get_machine_risk_distribution(self) -> Dict[str, int]:
        stmt = select(Machine.risk_score)
        result = await self.db.execute(stmt)
        scores = [row[0] for row in result.all()]
        
        return {
            "low": sum(1 for s in scores if s < 0.3),
            "medium": sum(1 for s in scores if 0.3 <= s < 0.6),
            "high": sum(1 for s in scores if s >= 0.6)
        }