import pytest
from datetime import datetime, timezone
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.ingestion.pipeline import ingest_stock_transaction
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

def test_offline_kill_test_and_crdt_idempotency_zero_duplicates(seeded_db):
    """
    CRITICAL ACCEPTANCE TEST:
    Kill network mid-entry -> transactions queue locally -> sync cleanly on reconnect
    with zero duplicates (CRDT idempotency test).
    """
    db, facilities, items = seeded_db
    fac = facilities[0]
    itm = items[0]
    now = datetime.now(timezone.utc)

    # Initial batch stock level
    initial_stock = sum(
        b.current_quantity for b in db.query(StockBatch)
        .filter(StockBatch.facility_id == fac.id, StockBatch.item_id == itm.id)
        .all()
    )
    assert initial_stock >= 100.0

    # 1. Facility is OFFLINE: User records 10 dispense transactions locally (5 units each)
    offline_queue = []
    for seq in range(1, 11):
        crdt_id = f"CRDT-{fac.id}-LAMPORT-{seq}-UUID-{seq*100}"
        offline_queue.append({
            "crdt_tx_id": crdt_id,
            "facility_id": fac.id,
            "item_id": itm.id,
            "tx_type": "dispense",
            "quantity": 5.0,
            "tx_timestamp": now,
            "source": "edge_pwa"
        })

    assert len(offline_queue) == 10

    # 2. Simulate NETWORK KILL MID-SYNC:
    # First 5 transactions arrive and are processed by server
    first_wave = offline_queue[:5]
    for tx_payload in first_wave:
        tx, is_q, status = ingest_stock_transaction(db, tx_payload)
        assert is_q is False
        assert status == "SUCCESS"

    # Verify 5 transactions in DB
    tx_count_mid = db.query(StockTransaction).filter(StockTransaction.facility_id == fac.id, StockTransaction.item_id == itm.id).count()
    assert tx_count_mid == 5

    # Stock deducted for 5 transactions = 25 units
    stock_after_wave1 = sum(
        b.current_quantity for b in db.query(StockBatch)
        .filter(StockBatch.facility_id == fac.id, StockBatch.item_id == itm.id)
        .all()
    )
    assert stock_after_wave1 == initial_stock - 25.0

    # 3. Connection is RESTORED:
    # Client re-sends the entire queue of 10 transactions (including the 5 already sent)
    processed_count = 0
    deduped_count = 0

    for tx_payload in offline_queue:
        tx, is_q, status = ingest_stock_transaction(db, tx_payload)
        assert is_q is False
        if status == "DEDUPLICATED_SUCCESS":
            deduped_count += 1
        elif status == "SUCCESS":
            processed_count += 1

    # Exactly 5 should be deduplicated, 5 newly processed!
    assert deduped_count == 5
    assert processed_count == 5

    # 4. PROVE: EXACTLY 10 transactions exist in database (ZERO DUPLICATES)
    all_txs = db.query(StockTransaction).filter(StockTransaction.facility_id == fac.id, StockTransaction.item_id == itm.id).all()
    assert len(all_txs) == 10

    crdt_ids_in_db = [t.crdt_tx_id for t in all_txs]
    assert len(crdt_ids_in_db) == len(set(crdt_ids_in_db)), "Duplicate CRDT transaction IDs detected in DB!"

    # 5. PROVE: Total stock deducted is exactly 10 * 5 = 50 units (no double deduction)
    final_stock = sum(
        b.current_quantity for b in db.query(StockBatch)
        .filter(StockBatch.facility_id == fac.id, StockBatch.item_id == itm.id)
        .all()
    )
    assert final_stock == initial_stock - 50.0
