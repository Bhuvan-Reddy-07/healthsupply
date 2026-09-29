from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey
from backend.app.core.database import Base

class SensorTemperature(Base):
    __tablename__ = "sensor_temp"

    id = Column(String(64), primary_key=True, index=True)
    facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(String(64), ForeignKey("stock_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    temperature_c = Column(Float, nullable=False)
    is_breached = Column(Boolean, default=False, nullable=False, index=True) # Outside 2-8 C
    timestamp = Column(DateTime, nullable=False, index=True)
    data_quality_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
