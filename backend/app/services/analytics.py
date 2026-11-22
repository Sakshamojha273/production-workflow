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
from app.core.config import reference_date, settings
from app.services.plan_metrics import latest_baseline_plan, machine_utilization_by_machine, worker_metrics


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # "Today" for every window below: PLANNING_REFERENCE_DATE when set (so a
        # historical dataset is analysed as of its planning date), else the
        # real date. Windows have an upper bound so future-dated rows don't leak in.
        self.today = reference_date()
    
    async def get_dashboard_kpis(self) -> Dict[str, Any]:
        """Get all KPI cards for dashboard"""
        
        # All imported orders (the headline number) ...
        all_orders = (await self.db.execute(select(func.count(Order.id)))).scalar() or 0
        # ... and the ones dated in the last 30 days up to the reference date.
        stmt = select(func.count(Order.id)).where(
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
        )
        result = await self.db.execute(stmt)
        total_orders = result.scalar() or 0
        
        # Production planned (last 30 days)
        stmt = select(func.sum(Order.production_quantity)).where(
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
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
        # "Current Demand" is the demand of one day: the last recorded day on or
        # before PLANNING_REFERENCE_DATE when that is set (the app's "today"),
        # otherwise the last day in the data.
        current_demand_date = latest_demand_date
        current_demand_basis = "last day in the data"
        if settings.PLANNING_REFERENCE_DATE and latest_demand_date:
            current_demand_date = (await self.db.execute(
                select(func.max(DemandHistory.date)).where(
                    DemandHistory.date <= settings.PLANNING_REFERENCE_DATE
                )
            )).scalar()
            current_demand_basis = (
                "PLANNING_REFERENCE_DATE"
                if current_demand_date == settings.PLANNING_REFERENCE_DATE
                else f"last recorded day before PLANNING_REFERENCE_DATE {settings.PLANNING_REFERENCE_DATE.isoformat()}"
            )
        if current_demand_date:
            current_demand_result = await self.db.execute(
                select(func.sum(DemandHistory.demand)).where(
                    DemandHistory.date == current_demand_date
                )
            )
            current_demand = current_demand_result.scalar() or 0
        if latest_demand_date:
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
        # Growth definition shared with the Demand Forecast page: forecast
        # total / number of forecast days vs. trailing-30-day total / observed days.
        forecast_days_result = await self.db.execute(
            select(func.count(func.distinct(Forecast.forecast_date))).join(
                latest_product_forecasts,
                and_(
                    Forecast.product_id == latest_product_forecasts.c.product_id,
                    Forecast.created_at == latest_product_forecasts.c.latest_created_at,
                ),
            ).where(Forecast.forecast_horizon_days <= 7)
        )
        forecast_days = forecast_days_result.scalar() or 0
        forecast_daily_average = demand_forecast / forecast_days if forecast_days else 0.0
        forecast_growth = (
            (forecast_daily_average - historical_daily_average)
            / historical_daily_average * 100
            if historical_daily_average
            else 0.0
        )
        
        # Machine / workforce utilization come from the latest baseline plan
        # (the same numbers the Production Planning page shows).
        latest_plan = await latest_baseline_plan(self.db)
        machine_util = float(latest_plan.machine_utilization or 0) if latest_plan else 0.0
        workforce_util = float(latest_plan.workforce_utilization or 0) if latest_plan else 0.0
        util_description = (
            f"Latest plan {latest_plan.plan_id} ({latest_plan.start_date:%b %d}–{latest_plan.end_date:%b %d})"
            if latest_plan else "No plan generated yet"
        )

        # Inventory level
        stmt = select(func.sum(Inventory.current_level))
        result = await self.db.execute(stmt)
        inventory_level = result.scalar() or 0
        
        # Overtime hours (last 30 days)
        stmt = select(func.sum(Order.overtime_hours)).where(
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
        )
        result = await self.db.execute(stmt)
        overtime_hours = result.scalar() or 0
        
        # Late orders
        stmt = select(func.count(Order.id)).where(
            Order.status == OrderStatus.DELAYED,
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
        )
        result = await self.db.execute(stmt)
        late_orders = result.scalar() or 0
        
        # Calculate trends (compare with previous period)
        prev_start = self.today - timedelta(days=60)
        prev_end = self.today - timedelta(days=30)
        
        trends = await self._calculate_trends(prev_start, prev_end, self.today - timedelta(days=30), self.today)
        trends["demand_forecast"] = forecast_growth
        
        return {
            "total_orders": {
                "title": "Total Orders",
                "value": f"{all_orders:,}",
                # The trend compares 30-day windows, which is not what the
                # all-time value measures, so none is shown.
                "trend": None,
                "trend_direction": "neutral",
                "description": f"All imported orders · {total_orders:,} in the 30 days to {self.today:%b %d, %Y}",
                "status": "Healthy"
            },
            "production_planned": {
                "title": "Production Planned",
                "value": f"{production_planned:,}",
                "trend": trends.get("production_planned", 0),
                "trend_direction": "up" if trends.get("production_planned", 0) > 0 else "down" if trends.get("production_planned", 0) < 0 else "neutral",
                "description": f"30 days to {self.today:%b %d, %Y}",
                "status": "Healthy"
            },
            "current_demand": {
                "title": "Current Demand",
                "value": f"{current_demand:,}",
                "trend": None,
                "trend_direction": "neutral",
                "description": f"Demand on {current_demand_date} ({current_demand_basis})" if current_demand_date else "No historical demand",
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
                "description": "Forecast daily avg vs. trailing 30-day daily avg",
                "status": "Healthy"
            },
            "machine_utilization": {
                "title": "Machine Utilization",
                "value": f"{machine_util:.1f}%",
                "trend": None,
                "trend_direction": "neutral",
                "description": util_description,
                "status": "Healthy" if machine_util > 70 else "Warning" if machine_util > 50 else "Critical"
            },
            "workforce_utilization": {
                "title": "Workforce Utilization",
                "value": f"{workforce_util:.1f}%",
                "trend": None,
                "trend_direction": "neutral",
                "description": util_description,
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
                "description": f"30 days to {self.today:%b %d, %Y} (lower is better)",
                "status": "Healthy" if overtime_hours < 100 else "Warning" if overtime_hours < 200 else "Critical"
            },
            "late_orders": {
                "title": "Late Orders",
                "value": f"{late_orders:,}",
                "trend": trends.get("late_orders", 0),
                "trend_direction": "down" if trends.get("late_orders", 0) > 0 else "up" if trends.get("late_orders", 0) < 0 else "neutral",
                "description": f"30 days to {self.today:%b %d, %Y} (lower is better)",
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
        
        # Utilization is a property of the latest plan (see get_dashboard_kpis),
        # so no period-over-period trend is computed for it.

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
        curr_forecast = await self._sum_forecast(self.today, self.today + timedelta(days=7))
        prev_forecast = await self._sum_forecast(self.today - timedelta(days=7), self.today)
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
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
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
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
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
        """Per-machine utilization in the latest baseline plan (planned / available units)."""
        plan = await latest_baseline_plan(self.db)
        by_machine = machine_utilization_by_machine(plan)
        stmt = select(Machine.machine_id, Machine.name).where(Machine.availability == 1)
        rows = (await self.db.execute(stmt)).all()
        data = sorted(
            ((row.name, float(by_machine.get(row.machine_id, 0.0))) for row in rows),
            key=lambda item: item[1], reverse=True,
        )
        values = [round(u, 1) for _, u in data]
        return {
            "type": "bar",
            "plan_id": plan.plan_id if plan else None,
            "data": {
                "labels": [name for name, _ in data],
                "datasets": [{
                    "label": "Utilization %",
                    "data": values,
                    "backgroundColor": ["#22c55e" if u >= 80 else "#f59e0b" if u >= 60 else "#ef4444" for u in values]
                }]
            }
        }

    async def _get_workforce_utilization_chart(self) -> Dict:
        """Per-worker regular-hour utilization in the latest baseline plan.

        Only workers with hours in the plan are charted (top 20), so the chart
        isn't 150 empty bars."""
        plan = await latest_baseline_plan(self.db)
        workers = (await self.db.execute(
            select(Worker.worker_id, Worker.name, Worker.availability_factor)
        )).all()
        metrics = await worker_metrics(
            self.db, plan, {w.worker_id: (w.availability_factor if w.availability_factor is not None else 1.0) for w in workers}
        )
        names = {w.worker_id: w.name for w in workers}
        data = sorted(
            ((names.get(wid, wid), m["utilization"]) for wid, m in metrics.items()),
            key=lambda item: item[1], reverse=True,
        )[:20]
        values = [round(u, 1) for _, u in data]
        return {
            "type": "bar",
            "plan_id": plan.plan_id if plan else None,
            "data": {
                "labels": [name for name, _ in data],
                "datasets": [{
                    "label": "Utilization %",
                    "data": values,
                    "backgroundColor": ["#22c55e" if u >= 80 else "#f59e0b" if u >= 60 else "#ef4444" for u in values]
                }]
            }
        }

    async def _get_production_cost_trend_chart(self) -> Dict:
        """Get production cost trend"""
        stmt = select(
            Order.date,
            func.avg(Order.production_cost).label('avg_cost')
        ).where(
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
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
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
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
            Order.date >= self.today - timedelta(days=30),
            Order.date <= self.today
        ).group_by(Order.priority)
        
        result = await self.db.execute(stmt)
        data = result.all()
        
        priority_map = {"Critical": 0, "Low": 0, "Medium": 0, "High": 0}
        for row in data:
            priority_map[row.priority.value] = row.count
        
        return {
            "type": "doughnut",
            "data": {
                "labels": ["Critical", "High", "Medium", "Low"],
                "datasets": [{
                    "data": [priority_map["Critical"], priority_map["High"], priority_map["Medium"], priority_map["Low"]],
                    "backgroundColor": ["#7f1d1d", "#ef4444", "#f59e0b", "#22c55e"]
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
            Maintenance.start_date >= self.today,
            Maintenance.start_date <= self.today + timedelta(days=30)
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
        current_month_demand = await self._sum_demand(self.today.replace(day=1), self.today)
        last_month_start = (self.today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month_end = self.today.replace(day=1) - timedelta(days=1)
        last_month_demand = await self._sum_demand(last_month_start, last_month_end)
        demand_growth = ((current_month_demand - last_month_demand) / max(1, last_month_demand)) * 100
        
        # Production fulfillment %
        total_demand = await self._sum_demand(self.today - timedelta(days=30), self.today)
        total_production = await self._sum_production(self.today - timedelta(days=30), self.today)
        fulfillment_pct = (total_production / max(1, total_demand)) * 100
        
        # Machine utilization
        latest_plan = await latest_baseline_plan(self.db)
        machine_util = float(latest_plan.machine_utilization or 0) if latest_plan else 0.0
        
        # Worker utilization
        worker_util = float(latest_plan.workforce_utilization or 0) if latest_plan else 0.0
        
        # Inventory coverage
        inventory_coverage = await self._calculate_inventory_coverage()
        
        # Overtime %
        total_hours = await self._sum_production_hours(self.today - timedelta(days=30), self.today)
        overtime_hours = await self._sum_overtime(self.today - timedelta(days=30), self.today)
        overtime_pct = (overtime_hours / max(1, total_hours)) * 100
        
        # Late order %
        total_orders = await self._count_orders(self.today - timedelta(days=30), self.today)
        late_orders = await self._count_late_orders(self.today - timedelta(days=30), self.today)
        late_order_pct = (late_orders / max(1, total_orders)) * 100
        
        # Production cost
        avg_cost = await self._avg_production_cost(self.today - timedelta(days=30), self.today)
        
        # Avg production time
        avg_time = await self._avg_production_time(self.today - timedelta(days=30), self.today)
        
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
            DemandHistory.date >= self.today - timedelta(days=30),
            DemandHistory.date <= self.today,
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