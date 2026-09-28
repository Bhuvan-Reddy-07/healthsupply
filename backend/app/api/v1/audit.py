from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db
from backend.app.models.audit import AuditLog, verify_audit_log_integrity
from backend.app.schemas.audit import AuditLogResponse, AuditIntegrityCheckResponse

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/logs", response_model=List[AuditLogResponse])
def list_audit_logs(
    table_name: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if table_name:
        query = query.filter(AuditLog.table_name == table_name)
    return query.order_by(AuditLog.id.desc()).limit(limit).all()

@router.get("/verify-integrity", response_model=AuditIntegrityCheckResponse)
def verify_integrity(db: Session = Depends(get_db)):
    """
    Cryptographically verifies the SHA-256 hash chain of the entire audit log.
    If any row was altered, deleted, or inserted out of order, this returns is_valid=False.
    """
    count = db.query(AuditLog).count()
    is_valid = verify_audit_log_integrity(db)
    return AuditIntegrityCheckResponse(
        is_valid=is_valid,
        total_records=count,
        verified_records=count if is_valid else 0,
        message="Cryptographic SHA-256 hash chain verified with zero tampering detected." if is_valid else "INTEGRITY VIOLATION DETECTED: Hash chain mismatch!"
    )
