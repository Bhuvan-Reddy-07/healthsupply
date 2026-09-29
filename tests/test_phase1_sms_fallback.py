import pytest
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.models.quarantine import QuarantinedEvent
from backend.app.ingestion.sms_parser import parse_and_process_sms
from simulator.generator import SyntheticDataGenerator

@pytest.fixture
def seeded_db(db_session):
    from datetime import datetime, timezone, timedelta
    gen = SyntheticDataGenerator(db=db_session)
    facilities = gen.generate_facilities(count_per_country=2)
    items = gen.generate_items()
    
    # Initialize active batches with known positive on-hand stock
    now = datetime.now(timezone.utc)
    for fac in facilities:
        for itm in items:
            b = StockBatch(
                id=f"BATCH-{fac.id}-{itm.id}-ACTIVE",
                batch_number="B-TEST-01",
                facility_id=fac.id,
                item_id=itm.id,
                current_quantity=200.0,
                initial_quantity=200.0,
                mfg_date=now.date() - timedelta(days=30),
                expiry_date=now.date() + timedelta(days=365),
                gs1_gtin="08901234567890",
                status="active"
            )
            db_session.add(b)
    db_session.commit()
    return db_session, facilities, items

def test_sms_end_to_end_stock_transaction_and_fuzzy_matching(seeded_db):
    """
    CRITICAL ACCEPTANCE TEST:
    SMS message becomes a stock transaction end-to-end with fuzzy matching.
    """
    db, facilities, items = seeded_db
    fac = facilities[0]

    # Find initial on-hand stock for Amoxicillin
    amox_item = next(it for it in items if "Amoxicillin" in it.name)
    initial_stock = sum(
        b.current_quantity for b in db.query(StockBatch)
        .filter(StockBatch.facility_id == fac.id, StockBatch.item_id == amox_item.id)
        .all()
    )
    assert initial_stock > 0

    # 1. Send SMS with shorthand query "AMOX"
    sms_text = f"STK {fac.id} AMOX 25"
    result = parse_and_process_sms(db, sms_text, sender_phone="+91-9845000001")

    assert result["status"] == "success"
    assert result["item"]["id"] == amox_item.id
    assert result["dispensed_quantity"] == 25.0
    assert result["data_quality_score"] > 0.0

    # Verify transaction in database
    tx = db.query(StockTransaction).filter(StockTransaction.id == result["transaction_id"]).first()
    assert tx is not None
    assert tx.source == "sms_fallback"
    assert tx.facility_id == fac.id
    assert tx.item_id == amox_item.id
    assert tx.quantity == 25.0

    # Verify stock deduction occurred in batches
    updated_stock = sum(
        b.current_quantity for b in db.query(StockBatch)
        .filter(StockBatch.facility_id == fac.id, StockBatch.item_id == amox_item.id)
        .all()
    )
    assert updated_stock == initial_stock - 25.0

    # 2. Send SMS with lowercase full name "paracetamol"
    para_item = next(it for it in items if "Paracetamol" in it.name)
    sms_text_para = f"STK {fac.id} paracetamol 10"
    result_para = parse_and_process_sms(db, sms_text_para, sender_phone="+91-9845000002")

    assert result_para["status"] == "success"
    assert "Paracetamol" in result_para["item"]["name"]
    assert result_para["dispensed_quantity"] == 10.0

def test_sms_bad_data_quarantined_with_reason_codes(seeded_db):
    """
    CRITICAL ACCEPTANCE TEST:
    Bad SMS messages are quarantined with reason codes, never silently dropped.
    """
    db, facilities, items = seeded_db
    fac = facilities[0]

    # 1. Malformed syntax
    res1 = parse_and_process_sms(db, "HELLO PLEASE SEND DRUGS", sender_phone="+91-9999999999")
    assert res1["status"] == "rejected"
    assert res1["reason_code"] == "ERR_MALFORMED_SMS"

    # 2. Unknown facility
    res2 = parse_and_process_sms(db, "STK FAC-UNKNOWN-999 AMOX 20", sender_phone="+91-9999999999")
    assert res2["status"] == "rejected"
    assert res2["reason_code"] == "ERR_UNKNOWN_FACILITY"

    # 3. Unidentifiable drug name
    res3 = parse_and_process_sms(db, f"STK {fac.id} UNKNOWN_RANDOM_CHEMICAL_999 15", sender_phone="+91-9999999999")
    assert res3["status"] == "rejected"
    assert res3["reason_code"] == "ERR_ITEM_FUZZY_FAIL"

    # 4. Invalid non-positive quantity
    res4 = parse_and_process_sms(db, f"STK {fac.id} AMOX 0", sender_phone="+91-9999999999")
    assert res4["status"] == "rejected"
    assert res4["reason_code"] == "ERR_INVALID_SMS_QTY"

    # Verify that all 4 rejections were saved into quarantined_events with details preserved
    q_events = db.query(QuarantinedEvent).filter(QuarantinedEvent.source == "sms_fallback").all()
    q_reasons = {q.reason_code for q in q_events}
    assert "ERR_MALFORMED_SMS" in q_reasons
    assert "ERR_UNKNOWN_FACILITY" in q_reasons
    assert "ERR_ITEM_FUZZY_FAIL" in q_reasons
    assert "ERR_INVALID_SMS_QTY" in q_reasons
