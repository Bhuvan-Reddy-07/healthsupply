import json
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models.quarantine import QuarantinedEvent
from backend.app.models.audit import record_audit
from backend.app.core.logging import logger

def quarantine_event(
    db: Session,
    subject: str,
    source: str,
    raw_payload: Any,
    reason_code: str,
    details: Optional[str] = None
) -> QuarantinedEvent:
    """
    Quarantines invalid, implausible, or out-of-grace events with reason codes.
    Guarantees that bad data is NEVER silently dropped.
    """
    if isinstance(raw_payload, (dict, list)):
        payload_str = json.dumps(raw_payload, default=str)
    else:
        payload_str = str(raw_payload)

    q_id = f"QRN-{uuid.uuid4().hex[:12]}"
    q_entry = QuarantinedEvent(
        id=q_id,
        subject=subject,
        source=source,
        raw_payload=payload_str,
        reason_code=reason_code,
        details=details or "Validation failed in ingestion pipeline"
    )
    db.add(q_entry)
    db.commit()
    db.refresh(q_entry)

    logger.warning(
        f"DATA QUARANTINED: [{reason_code}] on subject '{subject}' from '{source}'",
        extra={"props": {
            "quarantine_id": q_id,
            "subject": subject,
            "source": source,
            "reason_code": reason_code,
            "details": details
        }}
    )

    record_audit(
        db=db,
        table_name="quarantined_events",
        record_id=q_id,
        action="QUARANTINE_EVENT",
        actor=f"ingestion_{source}",
        new_state={"reason_code": reason_code, "subject": subject}
    )

    return q_entry
