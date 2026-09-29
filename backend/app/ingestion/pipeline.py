import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.models.bed_staff import BedState, StaffAttendance
from backend.app.models.sensor import SensorTemperature
from backend.app.models.audit import record_audit
from backend.app.ingestion.validator import StockTxEvent, BedStateEvent, StaffAttendanceEvent, SensorTempEvent
from backend.app.ingestion.quality import compute_data_quality_score
from backend.app.ingestion.quarantine import quarantine_event
from backend.app.core.logging import logger

def ingest_stock_transaction(db: Session, raw_event: Dict[str, Any]) -> Tuple[Optional[StockTransaction], bool, str]:
    """
    Ingests and processes a stock transaction event:
    1. Validates Pydantic & business plausibility rules
    2. Quarantines invalid records with explicit reason codes
    3. Idempotently deduplicates by CRDT tx_id
    4. Computes data quality score (freshness, reliability, plausibility)
    5. Applies FEFO allocation, non-negative stock guards, and stock-out censoring
    Returns: (StockTransaction, is_quarantined, status_message)
    """
    source = raw_event.get("source", "edge_pwa")
    crdt_id = raw_event.get("crdt_tx_id", f"TX-GEN-{uuid.uuid4().hex[:8]}")

    # 1. Pydantic validation
    try:
        event = StockTxEvent(**raw_event)
    except Exception as e:
        err_str = str(e)
        reason_code = "ERR_VALIDATION_FAILED"
        if "ERR_NEGATIVE_QTY" in err_str:
            reason_code = "ERR_NEGATIVE_QTY"
        elif "ERR_EXPIRY_BEFORE_MFG" in err_str:
            reason_code = "ERR_EXPIRY_BEFORE_MFG"
        
        quarantine_event(
            db=db,
            subject="stock.tx",
            source=source,
            raw_payload=raw_event,
            reason_code=reason_code,
            details=err_str
        )
        return None, True, reason_code

    # 2. Check facility exists
    facility = db.query(Facility).filter(Facility.id == event.facility_id).first()
    if not facility:
        quarantine_event(
            db=db,
            subject="stock.tx",
            source=source,
            raw_payload=raw_event,
            reason_code="ERR_UNKNOWN_FACILITY",
            details=f"Facility '{event.facility_id}' does not exist"
        )
        return None, True, "ERR_UNKNOWN_FACILITY"

    # 3. Check item exists
    item = db.query(Item).filter(Item.id == event.item_id).first()
    if not item:
        quarantine_event(
            db=db,
            subject="stock.tx",
            source=source,
            raw_payload=raw_event,
            reason_code="ERR_UNKNOWN_ITEM",
            details=f"Item '{event.item_id}' does not exist"
        )
        return None, True, "ERR_UNKNOWN_ITEM"

    # 4. Data Quality & Freshness (7-day grace period check)
    quality_score, reliability_score, is_valid, reason_code = compute_data_quality_score(
        subject="stock.tx",
        source=event.source,
        event_timestamp=event.tx_timestamp,
        payload=raw_event
    )
    if not is_valid:
        quarantine_event(
            db=db,
            subject="stock.tx",
            source=source,
            raw_payload=raw_event,
            reason_code=reason_code,
            details=f"Data quality evaluation failed: {reason_code}"
        )
        return None, True, reason_code

    # 5. CRDT Idempotency Deduplication Check
    existing_tx = db.query(StockTransaction).filter(StockTransaction.crdt_tx_id == event.crdt_tx_id).first()
    if existing_tx:
        logger.info(f"CRDT Deduplication: Event {event.crdt_tx_id} already ingested. Zero duplicate write.")
        return existing_tx, False, "DEDUPLICATED_SUCCESS"

    # 6. Process Stock Movement (FEFO + Censoring)
    effective_qty = event.quantity
    is_censored = False
    unfulfilled_qty = 0.0
    assigned_batch_id = event.batch_id

    if event.tx_type == "dispense":
        if assigned_batch_id:
            batch = db.query(StockBatch).filter(StockBatch.id == assigned_batch_id).with_for_update().first()
            if not batch:
                quarantine_event(
                    db=db,
                    subject="stock.tx",
                    source=source,
                    raw_payload=raw_event,
                    reason_code="ERR_UNKNOWN_BATCH",
                    details=f"Specified batch {assigned_batch_id} not found"
                )
                return None, True, "ERR_UNKNOWN_BATCH"

            if batch.current_quantity <= 0:
                # Stock-out censoring
                effective_qty = 0.0
                is_censored = True
                unfulfilled_qty = event.quantity
            elif batch.current_quantity < effective_qty:
                unfulfilled_qty = effective_qty - batch.current_quantity
                effective_qty = batch.current_quantity
                batch.current_quantity = 0.0
                batch.status = "depleted"
                is_censored = True
            else:
                batch.current_quantity -= effective_qty
                if batch.current_quantity == 0:
                    batch.status = "depleted"
        else:
            # FEFO cross-batch allocation
            batches = (
                db.query(StockBatch)
                .filter(
                    StockBatch.facility_id == event.facility_id,
                    StockBatch.item_id == event.item_id,
                    StockBatch.status == "active",
                    StockBatch.current_quantity > 0
                )
                .order_by(StockBatch.expiry_date.asc())
                .with_for_update()
                .all()
            )
            total_stock = sum(b.current_quantity for b in batches)

            if total_stock <= 0:
                effective_qty = 0.0
                is_censored = True
                unfulfilled_qty = event.quantity
            else:
                needed = event.quantity
                if total_stock < needed:
                    unfulfilled_qty = needed - total_stock
                    effective_qty = total_stock
                    is_censored = True
                else:
                    unfulfilled_qty = 0.0
                    effective_qty = needed
                    is_censored = False

                remaining = effective_qty
                for b in batches:
                    if remaining <= 0:
                        break
                    deduct = min(b.current_quantity, remaining)
                    b.current_quantity -= deduct
                    remaining -= deduct
                    assigned_batch_id = b.id
                    if b.current_quantity == 0:
                        b.status = "depleted"

    elif event.tx_type == "receive":
        if assigned_batch_id:
            batch = db.query(StockBatch).filter(StockBatch.id == assigned_batch_id).with_for_update().first()
            if batch:
                batch.current_quantity += event.quantity
                if batch.status == "depleted":
                    batch.status = "active"

    tx_id = f"TX-{uuid.uuid4().hex[:12]}"
    tx = StockTransaction(
        id=tx_id,
        crdt_tx_id=event.crdt_tx_id,
        facility_id=event.facility_id,
        item_id=event.item_id,
        batch_id=assigned_batch_id,
        tx_type=event.tx_type,
        quantity=effective_qty,
        censored=is_censored,
        unfulfilled_quantity=unfulfilled_qty,
        tx_timestamp=event.tx_timestamp,
        source=event.source,
        source_reliability_score=reliability_score,
        data_quality_score=quality_score,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    record_audit(
        db=db,
        table_name="stock_transactions",
        record_id=tx.id,
        action=f"TX_{event.tx_type.upper()}",
        actor=f"pipeline_{event.source}",
        new_state={"crdt_id": tx.crdt_tx_id, "qty": tx.quantity, "quality": quality_score}
    )

    return tx, False, "SUCCESS"


def ingest_bed_state(db: Session, raw_event: Dict[str, Any]) -> Tuple[Optional[BedState], bool, str]:
    """Ingests bed state telemetry with validation and quarantine routing."""
    source = raw_event.get("source", "edge_pwa")
    try:
        event = BedStateEvent(**raw_event)
    except Exception as e:
        quarantine_event(db, "bed.state", source, raw_event, "ERR_INVALID_BED_STATE", str(e))
        return None, True, "ERR_INVALID_BED_STATE"

    bed_id = f"BED-{uuid.uuid4().hex[:12]}"
    state = BedState(
        id=bed_id,
        facility_id=event.facility_id,
        timestamp=event.timestamp,
        total_beds=event.total_beds,
        occupied_beds=event.occupied_beds,
        icu_occupied=event.icu_occupied,
        pediatric_occupied=event.pediatric_occupied,
        maternity_occupied=event.maternity_occupied
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state, False, "SUCCESS"


def ingest_staff_attendance(db: Session, raw_event: Dict[str, Any]) -> Tuple[Optional[StaffAttendance], bool, str]:
    """Ingests staff attendance with validation and quarantine routing."""
    source = raw_event.get("source", "edge_pwa")
    try:
        event = StaffAttendanceEvent(**raw_event)
    except Exception as e:
        quarantine_event(db, "staff.attendance", source, raw_event, "ERR_INVALID_STAFF_ATTENDANCE", str(e))
        return None, True, "ERR_INVALID_STAFF_ATTENDANCE"

    att_id = f"ATT-{uuid.uuid4().hex[:12]}"
    att = StaffAttendance(
        id=att_id,
        facility_id=event.facility_id,
        date=event.date,
        doctors_present=event.doctors_present,
        nurses_present=event.nurses_present,
        pharmacists_present=event.pharmacists_present,
        shift=event.shift
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att, False, "SUCCESS"


def ingest_sensor_temperature(db: Session, raw_event: Dict[str, Any]) -> Tuple[Optional[SensorTemperature], bool, str]:
    """Ingests cold-chain sensor temperature telemetry and flags breaches."""
    source = raw_event.get("source", "sensor")
    try:
        event = SensorTempEvent(**raw_event)
    except Exception as e:
        quarantine_event(db, "sensor.temp", source, raw_event, "ERR_INVALID_SENSOR_TEMP", str(e))
        return None, True, "ERR_INVALID_SENSOR_TEMP"

    quality_score, _, is_valid, reason = compute_data_quality_score(
        subject="sensor.temp",
        source=source,
        event_timestamp=event.timestamp,
        payload=raw_event
    )
    if not is_valid:
        quarantine_event(db, "sensor.temp", source, raw_event, reason, "Sensor plausibility check failed")
        return None, True, reason

    # Cold-chain standard 2.0C - 8.0C
    is_breached = (event.temperature_c < 2.0 or event.temperature_c > 8.0)

    sens = SensorTemperature(
        id=f"SEN-{uuid.uuid4().hex[:12]}",
        facility_id=event.facility_id,
        batch_id=event.batch_id,
        device_id=event.device_id,
        temperature_c=event.temperature_c,
        is_breached=is_breached,
        timestamp=event.timestamp,
        data_quality_score=quality_score
    )
    db.add(sens)
    db.commit()
    db.refresh(sens)
    return sens, False, "SUCCESS"
