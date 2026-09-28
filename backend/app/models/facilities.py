from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class Facility(Base):
    __tablename__ = "facilities"

    id = Column(String(64), primary_key=True, index=True) # e.g. FAC-A-001
    name = Column(String(255), nullable=False)
    country = Column(String(64), nullable=False, index=True) # 'Country_A' or 'Country_B'
    region = Column(String(128), nullable=False)
    district = Column(String(128), nullable=False, index=True)
    tier = Column(String(32), nullable=False, index=True) # PHC, CHC, DH
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    has_cold_chain = Column(Boolean, default=False, nullable=False)
    cold_chain_capacity_liters = Column(Float, default=0.0)
    population_served = Column(Integer, default=10000)
    contact_phone = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    batches = relationship("StockBatch", back_populates="facility", cascade="all, delete-orphan")
    transactions = relationship("StockTransaction", back_populates="facility")
    bed_states = relationship("BedState", back_populates="facility")
    staff_attendance = relationship("StaffAttendance", back_populates="facility")
    alerts = relationship("Alert", back_populates="facility")
    forecasts = relationship("Forecast", back_populates="facility")
