from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Float
from backend.app.core.database import Base

class QuarantinedEvent(Base):
    __tablename__ = "quarantined_events"

    id = Column(String(64), primary_key=True, index=True) # e.g. QRN-UUID
    subject = Column(String(64), nullable=False, index=True) # stock.tx, bed.state, sensor.temp, sms.gateway
    source = Column(String(32), nullable=False, index=True) # edge_pwa, sms_fallback, batch_sync, sensor
    raw_payload = Column(Text, nullable=False)
    reason_code = Column(String(64), nullable=False, index=True) 
    # e.g. ERR_NEGATIVE_QTY, ERR_EXPIRY_BEFORE_MFG, ERR_TIMESTAMP_OUT_OF_GRACE, ERR_MALFORMED_SMS, ERR_UNKNOWN_ITEM
    details = Column(Text, nullable=True)
    quarantined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
