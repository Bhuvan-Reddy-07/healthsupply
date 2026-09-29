import hashlib
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from backend.app.core.database import Base

def hash_phone(phone_raw: str) -> str:
    """Normalizes phone string and computes SHA-256 hash."""
    clean = "".join(c for c in phone_raw if c.isdigit())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()

def hash_pin(pin_raw: str) -> str:
    """Computes SHA-256 hash of a facility sender PIN."""
    return hashlib.sha256(pin_raw.strip().encode("utf-8")).hexdigest()

class FacilitySmsAuth(Base):
    """
    Authorized SMS Sender Mapping.
    Ensures only pre-registered phone hashes or facility PINs can execute stock movements.
    """
    __tablename__ = "facility_sms_auth"

    id = Column(String(64), primary_key=True)
    facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_hash = Column(String(64), nullable=True, index=True)
    pin_hash = Column(String(64), nullable=True, index=True)
    sender_role = Column(String(32), nullable=False, default="pharmacist")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
