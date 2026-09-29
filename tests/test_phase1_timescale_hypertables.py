import pytest
from pathlib import Path

def test_timescale_hypertable_ddl_and_migration_definition():
    """
    Acceptance Test: Confirms Timescale hypertable conversion statements
    are registered in migration 0002 for time-series hypertables:
    - stock_transactions (time column: tx_timestamp)
    - bed_states (time column: timestamp)
    - sensor_temp (time column: timestamp)
    """
    migration_file = Path("backend/alembic/versions/0002_add_quarantine_and_sensor_hypertables.py")
    assert migration_file.exists(), "Migration 0002 file not found"
    
    content = migration_file.read_text(encoding="utf-8")
    assert "create_hypertable('stock_transactions', 'tx_timestamp'" in content
    assert "create_hypertable('bed_states', 'timestamp'" in content
    assert "create_hypertable('sensor_temp', 'timestamp'" in content
