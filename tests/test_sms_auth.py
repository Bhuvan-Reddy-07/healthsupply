import pytest
from datetime import datetime, timezone, timedelta
from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.models.quarantine import QuarantinedEvent
from backend.app.models.sms_auth import FacilitySmsAuth, hash_phone, hash_pin
from backend.app.ingestion.sms_parser import parse_and_process_sms
from simulator.generator import SyntheticDataGenerator

@pytest.fixture
def sms_auth_db(db_session):
    gen = SyntheticDataGenerator(db=db_session)
    facilities = gen.generate_facilities(count_per_country=1)
    items = gen.generate_items()
    fac = facilities[0]
    itm = items[0]

    now = datetime.now(timezone.utc)
    # Seed active batch
    b = StockBatch(
        id=f"BATCH-AUTH-{fac.id}",
        batch_number="B-AUTH-01",
        facility_id=fac.id,
        item_id=itm.id,
        current_quantity=100.0,
        initial_quantity=100.0,
        mfg_date=now.date() - timedelta(days=30),
        expiry_date=now.date() + timedelta(days=365),
        gs1_gtin="08901234567890",
        status="active"
    )
    db_session.add(b)

    # Register authorized phone hash & PIN for this facility
    auth = FacilitySmsAuth(
        id="AUTH-01",
        facility_id=fac.id,
        phone_hash=hash_phone("+91-9876543210"),
        pin_hash=hash_pin("8421"),
        sender_role="chief_pharmacist",
        is_active=True
    )
    db_session.add(auth)
    db_session.commit()
    return db_session, fac, itm

def test_sms_sender_phone_authentication(sms_auth_db):
    """Verifies pre-registered phone hash allows stock movement, while unknown phone is quarantined."""
    db, fac, itm = sms_auth_db

    # 1. Authorized phone number
    sms_valid = f"STK {fac.id} {itm.name} 5"
    res_ok = parse_and_process_sms(db, sms_valid, sender_phone="+91-9876543210")
    assert res_ok["status"] == "success"
    assert res_ok["dispensed_quantity"] == 5.0

    # 2. Rogue/unregistered phone number
    sms_rogue = f"STK {fac.id} {itm.name} 10"
    res_unauth = parse_and_process_sms(db, sms_rogue, sender_phone="+1-555-999-0000")
    assert res_unauth["status"] == "rejected"
    assert res_unauth["reason_code"] == "ERR_UNAUTHORIZED_SMS_SENDER"

    # Verify quarantine record exists
    q = db.query(QuarantinedEvent).filter(QuarantinedEvent.reason_code == "ERR_UNAUTHORIZED_SMS_SENDER").first()
    assert q is not None
    assert "+1-555-999-0000" in q.raw_payload

def test_sms_pin_authentication(sms_auth_db):
    """Verifies facility PIN enables emergency authorization even from an alternate phone."""
    db, fac, itm = sms_auth_db

    # Correct PIN from untrusted burner phone
    sms_pin_valid = f"STK {fac.id} {itm.name} 2"
    res_ok = parse_and_process_sms(db, sms_pin_valid, sender_phone="+1-000-000-0000", sender_pin="8421")
    assert res_ok["status"] == "success"
    assert res_ok["dispensed_quantity"] == 2.0

    # Incorrect PIN
    sms_pin_bad = f"STK {fac.id} {itm.name} 2"
    res_bad = parse_and_process_sms(db, sms_pin_bad, sender_phone="+1-000-000-0000", sender_pin="0000")
    assert res_bad["status"] == "rejected"
    assert res_bad["reason_code"] == "ERR_UNAUTHORIZED_SMS_SENDER"
