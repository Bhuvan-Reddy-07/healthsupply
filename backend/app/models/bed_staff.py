from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Integer, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class BedState(Base):
    __tablename__ = "bed_states"

    id = Column(String(64), primary_key=True, index=True)
    facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    total_beds = Column(Integer, nullable=False, default=10)
    occupied_beds = Column(Integer, nullable=False, default=0)
    icu_occupied = Column(Integer, default=0)
    pediatric_occupied = Column(Integer, default=0)
    maternity_occupied = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    facility = relationship("Facility", back_populates="bed_states")


class StaffAttendance(Base):
    __tablename__ = "staff_attendance"

    id = Column(String(64), primary_key=True, index=True)
    facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    doctors_present = Column(Integer, default=1, nullable=False)
    nurses_present = Column(Integer, default=2, nullable=False)
    pharmacists_present = Column(Integer, default=1, nullable=False)
    shift = Column(String(16), default="day", nullable=False) # morning, evening, night, day
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    facility = relationship("Facility", back_populates="staff_attendance")
