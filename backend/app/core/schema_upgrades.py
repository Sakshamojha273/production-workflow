"""Idempotent, additive schema upgrades for databases created before these columns existed.

The project has no Alembic revisions yet (``alembic/versions`` is empty) and
creates tables with ``Base.metadata.create_all``, which never alters existing
tables.  These statements bring an existing PostgreSQL database in line with
the current models without dropping data:

* new nullable/defaulted columns are added with ``ADD COLUMN IF NOT EXISTS``;
* integer columns that now hold fractional values are widened to
  ``double precision`` (existing 0/1 values are preserved as 0.0/1.0; re-upload
  the dataset to replace them with the source fractions).

New tables (e.g. ``production_plan_items``) are created by ``create_all``.
Replace this module with a proper Alembic baseline + revision when migrations
are introduced.
"""

UPGRADE_STATEMENTS = [
    "ALTER TABLE machines ADD COLUMN IF NOT EXISTS availability_factor DOUBLE PRECISION DEFAULT 1.0",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS availability_factor DOUBLE PRECISION DEFAULT 1.0",
    # OrderPriority gained CRITICAL (the dataset's "Critical" orders used to be
    # stored as MEDIUM). Additive: appends one enum label; existing rows are kept.
    # Re-upload the dataset to store those orders as CRITICAL.
    """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'orderpriority') THEN
        ALTER TYPE orderpriority ADD VALUE IF NOT EXISTS 'CRITICAL';
    END IF;
END $$;
""",
]

_WIDEN_TO_DOUBLE = [
    ("orders", "machine_availability"),
    ("orders", "worker_availability"),
    ("workforce_assignments", "assigned_hours"),
    ("workforce_assignments", "overtime_hours"),
]

for _table, _column in _WIDEN_TO_DOUBLE:
    UPGRADE_STATEMENTS.append(
        f"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = '{_table}' AND column_name = '{_column}' AND data_type = 'integer'
    ) THEN
        ALTER TABLE {_table} ALTER COLUMN {_column} TYPE DOUBLE PRECISION USING {_column}::double precision;
    END IF;
END $$;
"""
    )
