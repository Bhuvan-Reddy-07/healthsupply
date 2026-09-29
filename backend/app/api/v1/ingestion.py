from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.models.quarantine import QuarantinedEvent
from backend.app.ingestion.pipeline import (
    ingest_stock_transaction,
    ingest_bed_state,
    ingest_staff_attendance,
    ingest_sensor_temperature
)
from backend.app.ingestion.sms_parser import parse_and_process_sms
from backend.app.ingestion.nats_client import event_bus, NATS_SUBJECTS

router = APIRouter(prefix="/ingest", tags=["ingestion"])

class SmsWebhookRequest(BaseModel):
    text: str
    sender: Optional[str] = "+91-9876543210"

class CrdtBatchSyncRequest(BaseModel):
    facility_id: str
    client_timestamp: str
    transactions: List[Dict[str, Any]]

class QuarantinedEventResponse(BaseModel):
    id: str
    subject: str
    source: str
    raw_payload: str
    reason_code: str
    details: Optional[str] = None
    quarantined_at: str

    class Config:
        from_attributes = True

@router.post("/stock-tx")
def submit_stock_transaction(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Direct ingestion endpoint for stock transaction event."""
    tx, is_quarantined, status_msg = ingest_stock_transaction(db=db, raw_event=payload)
    if is_quarantined:
        return {"status": "quarantined", "reason_code": status_msg, "transaction": None}
    return {"status": "success", "transaction_id": tx.id, "crdt_tx_id": tx.crdt_tx_id, "quality_score": tx.data_quality_score}

@router.post("/bed-state")
def submit_bed_state(payload: Dict[str, Any], db: Session = Depends(get_db)):
    state, is_quarantined, status_msg = ingest_bed_state(db=db, raw_event=payload)
    if is_quarantined:
        return {"status": "quarantined", "reason_code": status_msg}
    return {"status": "success", "id": state.id}

@router.post("/staff-attendance")
def submit_staff_attendance(payload: Dict[str, Any], db: Session = Depends(get_db)):
    att, is_quarantined, status_msg = ingest_staff_attendance(db=db, raw_event=payload)
    if is_quarantined:
        return {"status": "quarantined", "reason_code": status_msg}
    return {"status": "success", "id": att.id}

@router.post("/sensor-temp")
def submit_sensor_temperature(payload: Dict[str, Any], db: Session = Depends(get_db)):
    sens, is_quarantined, status_msg = ingest_sensor_temperature(db=db, raw_event=payload)
    if is_quarantined:
        return {"status": "quarantined", "reason_code": status_msg}
    return {"status": "success", "id": sens.id, "is_breached": sens.is_breached}

@router.post("/sms")
def sms_gateway_webhook(payload: SmsWebhookRequest, db: Session = Depends(get_db)):
    """
    SMS Fallback Gateway endpoint:
    Parses STK <facility> <item_code> <qty>
    Fuzzy matches item, enforces non-negative stock, quarantines bad messages.
    """
    result = parse_and_process_sms(db=db, raw_text=payload.text, sender_phone=payload.sender)
    if result["status"] == "rejected":
        return result
    return result

@router.post("/sync")
def crdt_batch_sync(payload: CrdtBatchSyncRequest, db: Session = Depends(get_db)):
    """
    CRDT Batch Synchronization endpoint for Facility PWA:
    Idempotently ingests an array of queued offline transactions.
    """
    results = []
    processed_count = 0
    duplicate_count = 0
    quarantine_count = 0

    for tx_raw in payload.transactions:
        # Guarantee facility_id is passed
        tx_raw["facility_id"] = payload.facility_id
        tx, is_quarantined, status_msg = ingest_stock_transaction(db=db, raw_event=tx_raw)

        if is_quarantined:
            quarantine_count += 1
            results.append({"crdt_tx_id": tx_raw.get("crdt_tx_id"), "status": "quarantined", "reason": status_msg})
        elif status_msg == "DEDUPLICATED_SUCCESS":
            duplicate_count += 1
            results.append({"crdt_tx_id": tx.crdt_tx_id, "status": "deduplicated", "transaction_id": tx.id})
        else:
            processed_count += 1
            results.append({"crdt_tx_id": tx.crdt_tx_id, "status": "processed", "transaction_id": tx.id})

    return {
        "status": "completed",
        "total_received": len(payload.transactions),
        "processed": processed_count,
        "deduplicated": duplicate_count,
        "quarantined": quarantine_count,
        "details": results
    }

@router.get("/quarantine")
def list_quarantined_events(
    reason_code: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Inspects quarantined events and rejection reason codes."""
    query = db.query(QuarantinedEvent)
    if reason_code:
        query = query.filter(QuarantinedEvent.reason_code == reason_code)
    if subject:
        query = query.filter(QuarantinedEvent.subject == subject)
    events = query.order_by(QuarantinedEvent.quarantined_at.desc()).limit(limit).all()

    return [
        {
            "id": e.id,
            "subject": e.subject,
            "source": e.source,
            "raw_payload": e.raw_payload,
            "reason_code": e.reason_code,
            "details": e.details,
            "quarantined_at": e.quarantined_at.isoformat()
        }
        for e in events
    ]
