import pytest
from sqlalchemy import text
from backend.app.models.audit import AuditLog, record_audit, verify_audit_log_integrity

def test_audit_log_append_and_cryptographic_chain(db_session):
    """
    Acceptance Test: Audit log writes append sequential cryptographically chained SHA-256 hashes.
    """
    entry1 = record_audit(
        db=db_session,
        table_name="facilities",
        record_id="FAC-A-001",
        action="INSERT",
        actor="admin",
        new_state={"name": "Kolar PHC"}
    )
    assert entry1.id is not None
    assert entry1.tamper_hash != "PENDING"
    assert entry1.previous_hash == "GENESIS_ROOT_HASH_0000000000000000"

    entry2 = record_audit(
        db=db_session,
        table_name="stock_batches",
        record_id="BATCH-001",
        action="RECEIVE",
        actor="pharmacist",
        new_state={"qty": 100}
    )
    assert entry2.previous_hash == entry1.tamper_hash
    assert verify_audit_log_integrity(db_session) is True

def test_audit_log_update_prohibition_enforced(db_session):
    """
    Acceptance Test: Proves audit_log is strictly append-only.
    UPDATE operations are forbidden and raise PermissionError.
    """
    entry = record_audit(
        db=db_session,
        table_name="facilities",
        record_id="FAC-A-002",
        action="INSERT",
        actor="officer"
    )

    # Attempt to modify the audit record
    entry.actor = "malicious_actor"
    with pytest.raises(PermissionError) as exc_info:
        db_session.flush()

    assert "audit_log is strictly append-only. UPDATE operations are forbidden" in str(exc_info.value)
    db_session.rollback()

def test_audit_log_delete_prohibition_enforced(db_session):
    """
    Acceptance Test: Proves audit_log is strictly append-only.
    DELETE operations are forbidden and raise PermissionError.
    """
    entry = record_audit(
        db=db_session,
        table_name="facilities",
        record_id="FAC-A-003",
        action="INSERT",
        actor="system"
    )

    # Attempt to delete the audit record
    db_session.delete(entry)
    with pytest.raises(PermissionError) as exc_info:
        db_session.flush()

    assert "audit_log is strictly append-only. DELETE operations are forbidden" in str(exc_info.value)
    db_session.rollback()

def test_tamper_evidence_detects_illicit_database_tampering(db_session):
    """
    Acceptance Test: Proves that if data is altered at the raw storage level,
    the cryptographic verification algorithm immediately flags the tampering.
    """
    # Create valid chain of 3 entries
    for i in range(3):
        record_audit(
            db=db_session,
            table_name="items",
            record_id=f"ITEM-{i}",
            action="INSERT",
            actor=f"user-{i}"
        )

    assert verify_audit_log_integrity(db_session) is True

    # Tamper with record 2 directly in SQL (simulating malicious DB admin tampering)
    db_session.execute(
        text("UPDATE audit_log SET actor = 'compromised_actor' WHERE id = 2")
    )
    db_session.commit()

    # Integrity verification must catch this!
    is_intact = verify_audit_log_integrity(db_session)
    assert is_intact is False, "Cryptographic verification failed to catch tampered audit record!"
