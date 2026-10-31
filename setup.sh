#!/bin/bash
# SmartPlan AI - Quick Setup Script
# Usage: ./setup.sh  (works from any directory; paths are resolved relative to this script)
# Requires: Docker, Python 3.11, Node.js 22+

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" > /dev/null 2>&1; then
    PYTHON_BIN=python3
fi

echo "=== SmartPlan AI Setup ==="
echo "Project: $PROJECT_ROOT"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Start PostgreSQL
echo "=== Starting PostgreSQL ==="
cd "$PROJECT_ROOT"
docker compose up -d postgres

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    sleep 1
done
echo "✅ PostgreSQL is ready"
echo ""

# Install Python dependencies
echo "=== Installing Python dependencies ==="
cd "$PROJECT_ROOT/backend"
if [ ! -d "venv" ]; then
    "$PYTHON_BIN" -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Python dependencies installed"
echo ""

# Database schema
# There are no Alembic revisions yet: tables are created (and additive column
# upgrades applied) by the backend on startup (app/core/database.py:init_db).
echo "=== Database schema is created when the backend starts ==="
echo ""

# Install frontend dependencies
echo "=== Installing frontend dependencies ==="
cd "$PROJECT_ROOT/frontend"
npm install
echo "✅ Frontend dependencies installed"
echo ""

echo "=== Setup Complete! ==="
echo ""
echo "To start the application:"
echo "  Terminal 1 (Backend):  cd $PROJECT_ROOT/backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo "  Terminal 2 (Frontend): cd $PROJECT_ROOT/frontend && npm run dev"
echo ""
echo "Then open: http://localhost:5173"
echo "Login: admin@smartplan.ai / admin123"