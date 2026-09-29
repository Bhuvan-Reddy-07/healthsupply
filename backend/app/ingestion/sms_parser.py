import re
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.ingestion.quarantine import quarantine_event
from backend.app.ingestion.pipeline import ingest_stock_transaction
from backend.app.core.logging import logger

def parse_and_process_sms(db: Session, raw_text: str, sender_phone: str = "UNKNOWN") -> Dict[str, Any]:
    """
    Parses SMS command: STK <facility> <item_code> <qty>
    Features:
    - Fuzzy matching of item code via RapidFuzz
    - Strict validation & rejection quarantine log
    - Conversion to stock transaction end-to-end
    """
    text_clean = raw_text.strip()
    logger.info(f"SMS Received: '{text_clean}' from {sender_phone}")

    # 1. Regex parse: STK <facility> <item_code> <qty>
    pattern = r"^STK\s+(\S+)\s+(.+?)\s+([0-9]+(?:\.[0-9]+)?)$"
    match = re.match(pattern, text_clean, re.IGNORECASE)

    if not match:
        quarantine_event(
            db=db,
            subject="sms.gateway",
            source="sms_fallback",
            raw_payload={"text": raw_text, "sender": sender_phone},
            reason_code="ERR_MALFORMED_SMS",
            details="SMS format invalid. Expected: STK <facility_id> <item_code> <quantity>"
        )
        return {
            "status": "rejected",
            "reason_code": "ERR_MALFORMED_SMS",
            "message": "Format rejected. Must be: STK <facility> <item_code> <qty>",
            "raw_text": raw_text
        }

    facility_raw, item_raw, qty_raw = match.groups()

    # 2. Validate Quantity
    try:
        quantity = float(qty_raw)
        if quantity <= 0:
            raise ValueError()
    except ValueError:
        quarantine_event(
            db=db,
            subject="sms.gateway",
            source="sms_fallback",
            raw_payload={"text": raw_text, "sender": sender_phone},
            reason_code="ERR_INVALID_SMS_QTY",
            details=f"Quantity '{qty_raw}' is invalid or non-positive"
        )
        return {
            "status": "rejected",
            "reason_code": "ERR_INVALID_SMS_QTY",
            "message": f"Invalid quantity '{qty_raw}'",
            "raw_text": raw_text
        }

    # 3. Validate Facility
    facility = db.query(Facility).filter(Facility.id.ilike(facility_raw)).first()
    if not facility:
        quarantine_event(
            db=db,
            subject="sms.gateway",
            source="sms_fallback",
            raw_payload={"text": raw_text, "sender": sender_phone},
            reason_code="ERR_UNKNOWN_FACILITY",
            details=f"Facility '{facility_raw}' not found"
        )
        return {
            "status": "rejected",
            "reason_code": "ERR_UNKNOWN_FACILITY",
            "message": f"Facility '{facility_raw}' not recognized",
            "raw_text": raw_text
        }

    # 4. Fuzzy Match Item
    all_items = db.query(Item).all()
    if not all_items:
        quarantine_event(
            db=db,
            subject="sms.gateway",
            source="sms_fallback",
            raw_payload={"text": raw_text, "sender": sender_phone},
            reason_code="ERR_CATALOG_EMPTY",
            details="No items found in system database"
        )
        return {
            "status": "rejected",
            "reason_code": "ERR_CATALOG_EMPTY",
            "message": "System item catalog is empty",
            "raw_text": raw_text
        }

    # Prepare item candidate lookup dictionary
    candidates = {}
    for it in all_items:
        # Index ID, Name, and Category
        candidates[it.id] = it
        candidates[it.name] = it

    # Check direct ID or substring match first
    matched_item = None
    query_upper = item_raw.strip().upper()

    for it in all_items:
        if query_upper in it.id.upper() or query_upper in it.name.upper():
            matched_item = it
            match_score = 100
            break

    if not matched_item:
        # Run RapidFuzz string comparison
        candidate_names = list(candidates.keys())
        result = process.extractOne(
            item_raw,
            candidate_names,
            scorer=fuzz.token_set_ratio
        )
        if result and result[1] >= 55.0: # Match confidence threshold
            matched_key, match_score, _ = result
            matched_item = candidates[matched_key]
        else:
            quarantine_event(
                db=db,
                subject="sms.gateway",
                source="sms_fallback",
                raw_payload={"text": raw_text, "sender": sender_phone, "item_query": item_raw},
                reason_code="ERR_ITEM_FUZZY_FAIL",
                details=f"Could not reliably resolve item query '{item_raw}'. Highest score: {result[1] if result else 0}%"
            )
            return {
                "status": "rejected",
                "reason_code": "ERR_ITEM_FUZZY_FAIL",
                "message": f"Item '{item_raw}' could not be identified",
                "raw_text": raw_text
            }

    # 5. Ingest as Stock Transaction
    now_utc = datetime.now(timezone.utc)
    crdt_id = f"SMS-{facility.id}-{matched_item.id}-{int(now_utc.timestamp())}"

    tx_payload = {
        "crdt_tx_id": crdt_id,
        "facility_id": facility.id,
        "item_id": matched_item.id,
        "batch_id": None, # Will allocate via FEFO
        "tx_type": "dispense",
        "quantity": quantity,
        "tx_timestamp": now_utc,
        "source": "sms_fallback"
    }

    tx, is_quarantined, status_msg = ingest_stock_transaction(db=db, raw_event=tx_payload)

    if is_quarantined:
        return {
            "status": "quarantined",
            "reason_code": status_msg,
            "message": f"Transaction was quarantined: {status_msg}",
            "raw_text": raw_text
        }

    return {
        "status": "success",
        "crdt_tx_id": tx.crdt_tx_id,
        "transaction_id": tx.id,
        "facility": {"id": facility.id, "name": facility.name},
        "item": {"id": matched_item.id, "name": matched_item.name},
        "dispensed_quantity": tx.quantity,
        "censored": tx.censored,
        "unfulfilled_quantity": tx.unfulfilled_quantity,
        "data_quality_score": tx.data_quality_score,
        "raw_text": raw_text
    }
