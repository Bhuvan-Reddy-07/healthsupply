import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, event
from sqlalchemy.orm import Session
from backend.app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(64), nullable=False, index=True)
    record_id = Column(String(64), nullable=False, index=True)
    action = Column(String(32), nullable=False) # INSERT, STATE_CHANGE, DISPENSE, RECEIVE
    actor = Column(String(128), nullable=False, default="system")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    previous_state = Column(Text, nullable=True) # JSON serialized
    new_state = Column(Text, nullable=True)      # JSON serialized
    previous_hash = Column(String(64), nullable=False, default="GENESIS")
    tamper_hash = Column(String(64), nullable=False) # SHA-256 hash chain

    def compute_hash(self) -> str:
        """Compute SHA-256 cryptographic chain hash ensuring tamper-evidence."""
        if isinstance(self.timestamp, datetime):
            ts_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = str(self.timestamp)[:19]

        payload = (
            f"{self.table_name}|{self.record_id}|{self.action}|"
            f"{self.actor}|{ts_str}|{self.previous_hash}|"
            f"{self.previous_state or ''}|{self.new_state or ''}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# Strict ORM-level enforcement of Append-Only immutability
@event.listens_for(AuditLog, "before_update")
def receive_before_update(mapper, connection, target):
    raise PermissionError("SECURITY ALERT: audit_log is strictly append-only. UPDATE operations are forbidden.")

@event.listens_for(AuditLog, "before_delete")
def receive_before_delete(mapper, connection, target):
    raise PermissionError("SECURITY ALERT: audit_log is strictly append-only. DELETE operations are forbidden.")


def record_audit(
    db: Session,
    table_name: str,
    record_id: str,
    action: str,
    actor: str = "system",
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """Safely appends an entry to audit_log with cryptographic hash linking."""
    # Find last audit record to chain hash
    last_record = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last_record.tamper_hash if last_record else "GENESIS_ROOT_HASH_0000000000000000"

    now_ts = datetime.now(timezone.utc)
    entry = AuditLog(
        table_name=table_name,
        record_id=str(record_id),
        action=action,
        actor=actor,
        timestamp=now_ts,
        previous_state=json.dumps(previous_state) if previous_state else None,
        new_state=json.dumps(new_state) if new_state else None,
        previous_hash=prev_hash,
    )
    # Compute tamper-evident hash prior to initial insert
    entry.tamper_hash = entry.compute_hash()
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def verify_audit_log_integrity(db: Session) -> bool:
    """Recalculates the entire audit chain and verifies zero tampering."""
    records = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    if not records:
        return True
        
    expected_prev = "GENESIS_ROOT_HASH_0000000000000000"
    for r in records:
        if r.previous_hash != expected_prev:
            return False
        if r.tamper_hash != r.compute_hash():
            return False
        expected_prev = r.tamper_hash
        
    return True
