# SmartPlan AI – Production Planning & Workforce Optimization

An AI-powered production planning and workforce optimization platform for manufacturing companies. The system takes production, demand, machine, maintenance, inventory, and workforce data to generate optimized production plans using Google OR-Tools CP-SAT solver.

## Features

### Core Features
- **Executive Dashboard** - Real-time KPIs, charts, and analytics
- **Demand Forecasting** - Backtest-selected Naive, Moving Average, Seasonal Naive, or Random Forest models
- **Machine Health Monitoring** - Risk analysis using sensor data (vibration, temperature)
- **Production Optimization** - CP-SAT optimization for production planning
- **Workforce Scheduling** - Skill-based worker assignment optimization
- **What-If Analysis** - Scenario simulation and comparison
- **Data Management** - CSV upload, validation, and quality reporting
- **Reports** - Automated report generation (CSV/PDF)

### Technical Highlights
- **Clean Architecture** - Separated frontend/backend with proper layering
- **Type Safety** - TypeScript frontend, Pydantic models backend
- **Async Python** - FastAPI with async SQLAlchemy
- **PostgreSQL** - Relational database with migrations
- **Docker Ready** - Complete containerized deployment
- **Test Coverage** - Unit and integration tests

## Architecture

```
smartplan-ai/
├── frontend/                 # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Page components
│   │   ├── layouts/         # Layout components
│   │   ├── charts/          # Chart components (Recharts)
│   │   ├── services/        # API services
│   │   ├── hooks/           # Custom React hooks
│   │   ├── types/           # TypeScript types
│   │   └── utils/           # Utility functions
│   └── package.json
│
├── backend/                  # FastAPI + Python
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Core config, database
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic services
│   │   ├── ml/             # ML modules
│   │   ├── optimization/   # OR-Tools optimization
│   │   └── utils/          # Utilities
│   ├── requirements.txt
│   └── alembic/            # Database migrations
│
├── data/
│   ├── raw/                # Raw CSV datasets
│   └── processed/          # Processed data
│
├── docker-compose.yml
├── .env.example
└── README.md
```

## Technology Stack

### Frontend
- **React 18** with TypeScript
- **Vite** for fast development
- **Tailwind CSS** for styling
- **Recharts** for data visualization
- **Lucide React** for icons
- **React Router** for navigation
- **Axios** for API calls

### Backend
- **FastAPI** for REST API
- **SQLAlchemy 2.0** with async support
- **PostgreSQL** with asyncpg
- **Pydantic** for validation
- **Pandas/NumPy** for data processing
- **Scikit-learn/XGBoost** for ML
- **Google OR-Tools CP-SAT** for optimization

### DevOps
- **Docker** & **Docker Compose**
- **Alembic** for migrations
- **Pytest/Vitest** for testing

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 22+ (for local frontend dev; `jsdom@30` and `@testing-library/jest-dom@7` used by the tests require Node >= 22)
- Python 3.11 (for local backend dev; the pinned versions in `backend/requirements.txt` do not install on Python 3.13)

### Using Docker (Recommended)

```bash
# Clone the repository
cd smartplan-ai

# Copy environment file
cp .env.example .env

# Start all services
docker compose up --build

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Local Development

#### Backend
```bash
cd backend

# Create virtual environment (Python 3.11)
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp ../.env.example .env

# Database schema: tables are created on startup by app/core/database.py:init_db
# (there are no Alembic revisions yet; see "Database Migrations" below)

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Dataset

The project dataset is `data/raw/Production_Planning_AI_10K_Dataset.csv` (10,000 records). To load it into the application, start the services, sign in using **Demo Login**, open **Data → Upload Dataset**, and select that CSV.

The importer maps the dataset's source columns to the application's order, product, machine, worker, inventory, and maintenance fields:

- **Availability** is kept fractional (0-1). Each order row stores the source values; each machine and worker gets `availability_factor` = the mean of its rows (the 0/1 `availability` flag on machines means "in service"). The planner multiplies machine capacity and worker regular hours by these factors.
- **Order status**: orders due on or after the planning reference date (the upload day, or `PLANNING_REFERENCE_DATE` if set) are the open order book and are imported as `Pending`; the planner schedules these. Orders already past due are `Delayed` if `Late_Units > 0`, `Completed` if planned production covers demand, otherwise `In Progress`.
- **Maintenance**: `Maintenance_Status` values `Scheduled` / `Emergency` become one-day maintenance events per machine and date (`Preventive` / `Emergency` type; `Completed` before the reference date, `Scheduled` from it on). `None` means no maintenance.
- Safety stock is not in the dataset and is set to zero. Re-uploading updates existing orders (bulk upsert on `Order_ID`).

Source fields include order/date/product identifiers, `Process_Type`, `Demand_Qty`, `Planned_Production_Qty`, `Late_Units`, machine capacity and availability, worker department and availability, inventory, production cost, machine sensor readings, priority, due date, and next-day demand.

## Demand forecasting

Uploaded order demand is normalized to `date`, `product_id`, and `demand`, aggregated as the sum of all same-product orders on each date, and persisted in the existing `demand_history` table. The daily series uses zero for dates without an order between a product's first and last observed dates; it does not extend a product's history outside that span. Rows with invalid dates/products/quantities and negative demand are rejected from demand-history ingestion. `Next_Day_Demand` is explicitly excluded from all forecast features to prevent target leakage.

The forecasting feature pipeline adds lags 1, 7, 14, and 28; rolling means and standard deviations over the prior 7, 14, and 28 days; and calendar features. Each feature for date T uses demand available strictly before T. Models are compared using chronological expanding-window backtests with 7-day validation windows: Naive, 7-day moving average, seasonal naive, and a per-product Random Forest when sufficient feature history exists. The forecast uses the lowest validation WAPE, with MAE as a tie-breaker. MAE, RMSE, MAPE, WAPE, and bias are exposed through `/api/forecast/metrics` and `/api/forecast/models`; generated forecasts are persisted in the existing `forecasts` table and are read without retraining on page refresh. Backtest results are cached by a hash of the uploaded daily demand series.

The lower and upper forecast bounds use the selected model's absolute backtest residual quantile at the configured interval level (80% by default). These are estimated prediction intervals, not guaranteed confidence intervals. Short product histories are not forecast; the API reports insufficient data instead of fabricating demand. Forecasting configuration is available through `FORECAST_DEFAULT_HORIZON`, `FORECAST_MAX_HORIZON`, `FORECAST_INTERVAL_LEVEL`, and `FORECAST_MIN_HISTORY`.

### Dataset profile (checked into this project)

`Production_Planning_AI_10K_Dataset.csv` contains 10,000 order records from 2026-01-01 through 2026-12-31, covering 15 products. Date, product ID, and demand quantity are populated in all rows; demand is non-negative. The file contains 5,387 repeated date/product order pairs that must be aggregated into daily product demand. There are 4,613 resulting date/product observations before expanding 859 no-order product-days within each product's observed range (5,472 product-days total). Overall, all 365 calendar dates have recorded demand. The file has no empty cells. `Maintenance_Status` contains the literal value `None` in 8,182 rows (meaning "no maintenance"; 1,436 `Scheduled`, 382 `Emergency`); the importer reads it as a value rather than as a missing cell, so the data-quality report counts missing values in the file as uploaded, before any filling.

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login
- `POST /api/auth/demo-login` - Demo login
- `GET /api/auth/me` - Current user

### Dashboard
- `GET /api/dashboard` - KPIs and charts
- `GET /api/analytics/summary` - Analytics summary
- `GET /api/analytics/charts` - Chart data

### Orders
- `GET /api/orders` - Paginated orders with filters
- `GET /api/orders/{order_id}` - Single order

### Products
- `GET /api/products` - All products
- `GET /api/products/{product_id}` - Single product

### Machines
- `GET /api/machines` - All machines
- `GET /api/machines/{machine_id}` - Single machine

### Workers
- `GET /api/workers` - All workers
- `GET /api/workers/{worker_id}` - Single worker

### Inventory
- `GET /api/inventory` - All inventory
- `GET /api/inventory/{product_id}` - Single product inventory

### Forecast
- `GET /api/forecast` - Get saved forecasts, filterable by horizon, product, and date
- `POST /api/forecast/generate` - Generate a 7-, 14-, or 30-day forecast
- `GET /api/forecast/history` - Daily aggregated demand used for forecasting
- `GET /api/forecast/metrics` - Chronological backtest model comparison and selected model
- `GET /api/forecast/models` - Baseline and ML model metrics
- `GET /api/forecast/latest` - Latest saved forecast values
- `GET /api/forecast/accuracy/{product_id}` - Forecast accuracy

### Planning
- `GET /api/planning` - All plans
- `GET /api/planning/latest` - Latest plan
- `GET /api/planning/{plan_id}` - Single plan
- `POST /api/planning/generate` - Generate optimized plan
- `POST /api/planning/{plan_id}/approve` - Approve plan

### Scenario
- `GET /api/scenario` - All scenarios
- `POST /api/scenario` - Create scenario
- `POST /api/scenario/{scenario_id}/run` - Run scenario

### Data
- `POST /api/data/upload` - Upload CSV
- `GET /api/data/quality` - Quality reports
- `GET /api/data/quality/{report_id}` - Single report

### Reports
- `POST /api/reports` - Generate report
- `GET /api/reports` - List reports

### Maintenance
- `GET /api/maintenance` - Maintenance records
- `GET /api/maintenance/timeline` - Upcoming maintenance
- `GET /api/maintenance/machine-risk` - Machine risk analysis
- `GET /api/maintenance/risk-distribution` - Risk distribution

## Demo Credentials

```
Email: admin@smartplan.ai
Password: admin123
```

Or use the "Demo Login" button on the login page.

## Optimization Engine

`POST /api/planning/generate` plans the open orders due in `[start_date, end_date]` (at most `PLANNING_MAX_HORIZON_DAYS`, default 31). The model is in `backend/app/optimization/planning_model.py`; it is solved with Google OR-Tools CP-SAT in a worker thread so the API stays responsive.

### Production model (CP-SAT, daily buckets)
- **Variables**: integer units per order x eligible machine (same process type) x day, from the order date (or window start) to the window end; units allocated from inventory on hand; backlog units per order; a late flag per order.
- **Demand balance**: produced + from inventory + backlog = order quantity (after scenario adjustments).
- **Machine capacity**: `Machine_Capacity_Per_Hour` x productive hours per day (`PLANNING_SHIFTS` x `PLANNING_SHIFT_HOURS`, default 3 x 8 h) x machine `availability_factor`, minus `PLANNING_MAINTENANCE_DOWNTIME_HOURS` (default 8 h) on days with a scheduled maintenance event.
- **Inventory**: allocations per product cannot exceed inventory on hand.
- **Objective** (minimise): production cost + a small holding cost for producing early + a per-unit-per-day penalty for production after the due date (weighted by priority) + a larger, priority-weighted backlog penalty + a penalty per late order. An order is *late* if any unit is produced after its due date or is backlogged.

### Workforce assignment (post-solve heuristic)
Operators are assigned after the production solve: each machine-hour needs `PLANNING_OPERATORS_PER_MACHINE` operators who have a skill for the machine type (from the uploaded data) and work that shift; the least-loaded qualified worker is chosen, with regular hours = shift length x availability and overtime capped by `max_overtime_hours`. Hours that cannot be staffed are reported (`notes.unstaffed_hours`) rather than dropped. This is not yet a joint optimisation of production, maintenance windows and shifts.

### Output
The plan, one item per order (quantity, schedule by day/machine, inventory used, backlog, late units, completion date, main operator) and the workforce assignments are persisted and returned unchanged by `GET /api/planning/{plan_id}` and `/api/planning/latest`.

### What-if scenarios
`POST /api/scenario/{scenario_id}/run` with body `{"baseline_run_id": "<OPT-... or run UUID>"}` re-optimises the baseline window with the scenario levers applied to the inputs: demand %, production target %, machine availability %, worker availability %, overtime limit %, inventory % and failed machines. A failed re-optimisation marks the scenario `Failed`.

## ML Pipeline

### Demand Forecasting
1. **Data Preparation** - Historical demand from orders
2. **Feature Engineering** - Lag features, rolling stats, calendar features
3. **Models** - Naive, Moving Average, Seasonal Naive, Random Forest
4. **Validation** - Expanding-window chronological backtesting with MAE, RMSE, MAPE, WAPE, and bias
5. **Forecasting** - Recursive multi-step prediction

### Machine Risk Analysis
1. **Sensor Data** - Vibration, temperature, utilization
2. **Anomaly Detection** - Isolation Forest
3. **Risk Scoring** - Weighted combination of normalized sensors
4. **Categories** - Low (<0.3), Medium (0.3-0.6), High (>0.6)
5. **Maintenance Recommendations** - Based on risk + anomalies

## Data Processing Pipeline

```
CSV Upload
    ↓
Validation (schema, types, constraints)
    ↓
Cleaning (duplicates, missing values, outliers)
    ↓
Feature Engineering (date parsing, derived fields)
    ↓
Database Ingestion (upsert products, machines, workers, orders)
    ↓
Analytics Computation (KPIs, aggregations)
    ↓
ML Training (forecast, risk models)
    ↓
Optimization (production planning)
    ↓
API → Frontend
```

## Development

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Code Quality

```bash
# Backend linting
cd backend
ruff check .
black .

# Frontend linting
cd frontend
npm run lint
```

### Database Migrations

There are no Alembic revisions yet (`backend/alembic/versions/` is empty). Tables are created on startup with `Base.metadata.create_all`, and `app/core/schema_upgrades.py` applies idempotent, additive upgrades to existing PostgreSQL databases (new columns, widening integer availability/hours columns to `double precision`). Re-upload the dataset after upgrading so existing rows get the fractional values. Creating an Alembic baseline is a recommended next step.

## Project Structure Details

### Backend Services
- **DataProcessor** - CSV ingestion, validation, cleaning
- **DemandForecaster** - Forecast generation and accuracy
- **MachineRiskAnalyzer** - Risk scoring and anomaly detection
- **ProductionOptimizer** - CP-SAT optimization
- **AnalyticsService** - KPIs, charts, summaries

### Frontend Hooks
- `useDashboard` - Dashboard data
- `useOrders` - Orders with pagination/filters
- `useProducts/Machines/Workers` - Reference data
- `useInventory` - Inventory levels
- `useForecasts` - Forecasts with generation
- `usePlans` - Production plans with generation
- `useScenarios` - What-if scenarios
- `useDataQuality` - Upload and quality reports
- `useMaintenance` - Maintenance records

### UI Components
- **KPICard** - Metric display with trend
- **ChartCard** - Wrapper for charts
- **Data Tables** - Sortable, filterable, paginated
- **Modals** - Forms and confirmations
- **Status Badges** - Consistent status display

## Deployment

### Production Considerations
1. **Environment Variables** - Use strong SECRET_KEY
2. **Database** - Use managed PostgreSQL (RDS, Cloud SQL)
3. **HTTPS** - Configure reverse proxy (nginx, Traefik)
4. **Scaling** - Backend can run multiple replicas
5. **Monitoring** - Add Prometheus/Grafana
6. **Backups** - Automated PostgreSQL backups

### Docker Production Build
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Common Issues

**Database Connection Failed**
- Check PostgreSQL is running: `docker compose ps`
- Verify DATABASE_URL in .env
- Check logs: `docker compose logs postgres`

**Optimization Takes Too Long**
- Reduce time limit in ProductionOptimizer
- Check constraint feasibility
- Review solver parameters

**Forecast Accuracy Low**
- Ensure sufficient historical data (30+ days)
- Compare Naive, Moving Average, Seasonal Naive, and Random Forest in `/api/forecast/metrics`; do not assume the ML model is best
- Review the source demand aggregation and zero-demand-day assumption
- Check for data quality issues

**Frontend Not Loading Data**
- Check CORS_ORIGINS includes frontend URL
- Verify API_BASE_URL in frontend
- Check network tab for failed requests

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/your-repo/issues)
- Documentation: Check `/docs` folder
- API Docs: http://localhost:8000/docs (when running)

---

**SmartPlan AI** - Empowering manufacturing with intelligent planning.