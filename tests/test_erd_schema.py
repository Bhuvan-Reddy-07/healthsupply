import pytest
from sqlalchemy import inspect
from backend.app.core.database import Base

def test_erd_all_ten_tables_exist(engine):
    """
    Acceptance Test: ERD matches spec exactly.
    Must implement exactly these 10 tables:
    facilities, items, stock_batches, stock_transactions, bed_states,
    staff_attendance, forecasts, alerts, transfer_proposals, audit_log.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    required_tables = [
        "facilities",
        "items",
        "stock_batches",
        "stock_transactions",
        "bed_states",
        "staff_attendance",
        "forecasts",
        "alerts",
        "transfer_proposals",
        "audit_log"
    ]

    for req in required_tables:
        assert req in tables, f"Expected table '{req}' not found in database schema! Found: {tables}"

def test_batch_level_granularity_fields(engine):
    """
    Acceptance Test: Batch-level granularity is mandatory
    (qty, expiry_date, mfg_date, gs1_gtin).
    """
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("stock_batches")}

    assert "current_quantity" in columns, "stock_batches missing current_quantity"
    assert "expiry_date" in columns, "stock_batches missing expiry_date"
    assert "mfg_date" in columns, "stock_batches missing mfg_date"
    assert "gs1_gtin" in columns, "stock_batches missing gs1_gtin"
    assert "batch_number" in columns, "stock_batches missing batch_number"
    assert "facility_id" in columns, "stock_batches missing facility_id"
    assert "item_id" in columns, "stock_batches missing item_id"

def test_stock_transactions_granularity_and_censoring_fields(engine):
    """
    Acceptance Test: Transactions track batch, quantity, and censored demand flag.
    """
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("stock_transactions")}

    assert "crdt_tx_id" in columns, "stock_transactions missing crdt_tx_id"
    assert "batch_id" in columns, "stock_transactions missing batch_id"
    assert "quantity" in columns, "stock_transactions missing quantity"
    assert "censored" in columns, "stock_transactions missing censored"
    assert "unfulfilled_quantity" in columns, "stock_transactions missing unfulfilled_quantity"
    assert "data_quality_score" in columns, "stock_transactions missing data_quality_score"
