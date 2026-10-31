#!/bin/bash
# Quick test script for SmartPlan AI backend

# Usage: bash test_upload.py   (run from anywhere; paths resolve relative to this file)
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "=== Installing backend dependencies ==="
cd backend
pip install -r requirements.txt -q

echo "=== Testing data processor with sample CSV ==="
cd ..
python3 << 'EOF'
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, 'backend')

from app.services.data_processor import DataProcessor, CSV_NA_VALUES

# Read the main CSV ("None" in Maintenance_Status is a value, not a missing cell)
df = pd.read_csv("data/raw/Production_Planning_AI_10K_Dataset.csv", nrows=10,
                 keep_default_na=False, na_values=CSV_NA_VALUES)
raw = df.copy()
print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
print(f"Columns: {list(df.columns)}")

# Test normalization
processor = DataProcessor(None)  # db not needed for normalization
normalized = processor._normalize_dataset_columns(df)

required = {'Order_ID', 'Date', 'Product_ID', 'Demand', 'Machine_ID', 'Worker_ID'}
missing = required - set(normalized.columns)
print(f"Required columns missing: {missing}")
print(f"All required present: {len(missing) == 0}")

# Test quality analysis
report = processor._analyze_data_quality(raw, "test.csv", normalized=normalized)
print(f"Quality score: {report.quality_score:.2f}%")
print(f"Total rows: {report.total_rows}")
print(f"Total columns: {report.total_columns}")
print(f"Missing values: {report.missing_values}")
print(f"Duplicates: {report.duplicate_rows}")
print(f"Invalid records: {report.invalid_records}")

print("\n=== Smoke check finished ===")
EOF