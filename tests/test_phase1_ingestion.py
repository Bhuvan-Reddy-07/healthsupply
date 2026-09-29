import pytest
from datetime import datetime, timezone, timedelta
from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.models.quarantine import QuarantinedEvent
from backend.app.models.sensor import SensorTemperature
from backend.app.ingestion.pipeline import (
    ingest_stock_transaction,
    ingest_bed_state,
    ingest_staff_attendance,
    ingest_sensor_temperature
)
from backend.app.ingestion.quality import compute_data_quality_score
from simulator.generator import SyntheticDataGenerator

@pytest.fixture
def seeded_db(db_session):
    gen = SyntheticDataGenerator(db=db_session)
    facilities = gen.generate_facilities(count_per_country=2)
    items = gen.generate_items()
    # Seed 1 month of batches
    gen.generate_simulation_history(facilities=facilities, items=items, months=1)
    return db_session, facilities, items

def test_data_quality_scoring_engine():
    """
    Acceptance Test: Data-quality engine calculates composite score based on
    freshness, source reliability, and physical plausibility.
    """
    now = datetime.now(timezone.utc)
    
    # Fresh edge PWA event (within 1 hour)
    score_fresh, rel, valid, _ = compute_data_quality_score(
        subject="stock.tx",
        source="edge_pwa",
        event_timestamp=now,
        payload={"quantity": 25}
    )
    assert valid is True
    assert score_fresh >= 0.95
    assert rel == 1.0

    # SMS fallback event
    score_sms, rel_sms, valid_sms, _ = compute_data_quality_score(
        subject="stock.tx",
        source="sms_fallback",
        event_timestamp=now - timedelta(hours=2),
        payload={"quantity": 10}
    )
    assert valid_sms is True
    assert rel_sms == 0.75
    assert score_sms < score_fresh

    # Event older than 7 days (outside grace period) -> Must be rejected!
    score_old, _, valid_old, reason = compute_data_quality_score(
        subject="stock.tx",
        source="edge_pwa",
        event_timestamp=now - timedelta(days=8),
        payload={"quantity": 20}
    )
    assert valid_old is False
    assert reason == "ERR_TIMESTAMP_OUT_OF_GRACE"

def test_bad_data_quarantined_never_silently_dropped(seeded_db):
    """
    CRITICAL ACCEPTANCE TEST:
    Bad data quarantined with reason codes, never silently dropped.
    Tests:
    - Negative quantity -> ERR_NEGATIVE_QTY
    - Expiry before mfg date -> ERR_EXPIRY_BEFORE_MFG
    - Event out of 7d grace -> ERR_TIMESTAMP_OUT_OF_GRACE
    - Unknown facility ID -> ERR_UNKNOWN_FACILITY
    """
    db, facilities, items = seeded_db
    fac = facilities[0]
    itm = items[0]
    now = datetime.now(timezone.utc)

    # 1. Negative quantity
    bad_payload_neg = {
        "crdt_tx_id": "CRDT-BAD-NEG-001",
        "facility_id": fac.id,
        "item_id": itm.id,
        "tx_type": "dispense",
        "quantity": -50.0,
        "tx_timestamp": now,
        "source": "edge_pwa"
    }
    tx, is_q, reason = ingest_stock_transaction(db, bad_payload_neg)
    assert is_q is True
    assert reason == "ERR_NEGATIVE_QTY"
    assert tx is None

    # Check quarantine table
    q_entry = db.query(QuarantinedEvent).filter(QuarantinedEvent.reason_code == "ERR_NEGATIVE_QTY").first()
    assert q_entry is not None
    assert "CRDT-BAD-NEG-001" in q_entry.raw_payload

    # 2. Expiry before manufacturing date
    bad_payload_exp = {
        "crdt_tx_id": "CRDT-BAD-EXP-002",
        "facility_id": fac.id,
        "item_id": itm.id,
        "tx_type": "receive",
        "quantity": 100.0,
        "tx_timestamp": now,
        "batch_mfg_date": "2026-05-01",
        "batch_expiry_date": "2025-05-01", # Earlier than mfg!
        "source": "batch_sync"
    }
    tx, is_q, reason = ingest_stock_transaction(db, bad_payload_exp)
    assert is_q is True
    assert reason == "ERR_EXPIRY_BEFORE_MFG"

    # 3. Timestamp out of 7-day grace period (e.g. 15 days old)
    bad_payload_grace = {
        "crdt_tx_id": "CRDT-BAD-TIME-003",
        "facility_id": fac.id,
        "item_id": itm.id,
        "tx_type": "dispense",
        "quantity": 10.0,
        "tx_timestamp": now - timedelta(days=15),
        "source": "edge_pwa"
    }
    tx, is_q, reason = ingest_stock_transaction(db, bad_payload_grace)
    assert is_q is True
    assert reason == "ERR_TIMESTAMP_OUT_OF_GRACE"

    # 4. Unknown facility
    bad_payload_fac = {
        "crdt_tx_id": "CRDT-BAD-FAC-004",
        "facility_id": "FAC-NONEXISTENT-999",
        "item_id": itm.id,
        "tx_type": "dispense",
        "quantity": 10.0,
        "tx_timestamp": now,
        "source": "edge_pwa"
    }
    tx, is_q, reason = ingest_stock_transaction(db, bad_payload_fac)
    assert is_q is True
    assert reason == "ERR_UNKNOWN_FACILITY"

    # Verify that all 4 bad events exist in quarantined_events
    quarantined_count = db.query(QuarantinedEvent).count()
    assert quarantined_count >= 4

def test_sensor_temperature_ingestion_and_breach(seeded_db):
    """
    Acceptance Test: Sensor temperature telemetry ingestion and cold chain breach detection (2-8 C).
    """
    db, facilities, items = seeded_db
    fac = facilities[0]
    now = datetime.now(timezone.utc)

    # Normal cold chain temp: 4.5 C
    normal_event = {
        "facility_id": fac.id,
        "device_id": "SENS-CC-01",
        "temperature_c": 4.5,
        "timestamp": now
    }
    sens, is_q, _ = ingest_sensor_temperature(db, normal_event)
    assert is_q is False
    assert sens.is_breached is False
    assert sens.data_quality_score >= 0.9

    # Breached cold chain temp: 11.2 C (High temp breach)
    breach_event = {
        "facility_id": fac.id,
        "device_id": "SENS-CC-01",
        "temperature_c": 11.2,
        "timestamp": now
    }
    sens_breach, is_q2, _ = ingest_sensor_temperature(db, breach_event)
    assert is_q2 is False
    assert sens_breach.is_breached is True
