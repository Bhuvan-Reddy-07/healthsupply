from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(String(64), primary_key=True, index=True)
    facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(64), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    forecast_date = Column(Date, nullable=False, index=True)
    model_version = Column(String(64), nullable=False) # e.g. lightgbm_q_v1.0
    p10 = Column(Float, nullable=False)
    p50 = Column(Float, nullable=False)
    p90 = Column(Float, nullable=False)
    reconciled_p50 = Column(Float, nullable=True) # Hierarchical reconciliation MinT / bottom-up
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    facility = relationship("Facility", back_populates="forecasts")
    item = relationship("Item", back_populates="forecasts")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(64), primary_key=True, index=True)
    facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(64), ForeignKey("items.id", ondelete="CASCADE"), nullable=True, index=True)
    alert_type = Column(String(64), nullable=False, index=True) # stockout_warning, outbreak_detected, cold_chain_breach, expiry_risk
    severity = Column(String(16), nullable=False, index=True) # amber, red, black
    days_remaining = Column(Float, nullable=True)
    p_stockout_before_lead = Column(Float, nullable=True)
    message = Column(Text, nullable=False)
    is_acknowledged = Column(Boolean, default=False, nullable=False, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    facility = relationship("Facility", back_populates="alerts")
    item = relationship("Item", back_populates="alerts")


class TransferProposal(Base):
    __tablename__ = "transfer_proposals"

    id = Column(String(64), primary_key=True, index=True)
    donor_facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(64), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(String(64), ForeignKey("stock_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    donor_cover_days_before = Column(Float, nullable=False)
    donor_cover_days_after = Column(Float, nullable=False)
    recipient_cover_days_before = Column(Float, nullable=False)
    recipient_cover_days_after = Column(Float, nullable=False)
    eta_days = Column(Float, nullable=False, default=1.0)
    cold_chain_required = Column(Boolean, default=False, nullable=False)
    explanation = Column(Text, nullable=False)
    status = Column(String(32), default="proposed", nullable=False, index=True) # proposed, approved, rejected, in_transit, completed
    rejection_reason = Column(Text, nullable=True)
    reviewed_by = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    item = relationship("Item", back_populates="transfer_proposals")
    batch = relationship("StockBatch", back_populates="transfer_proposals")
