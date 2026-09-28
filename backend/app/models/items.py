from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(String(64), primary_key=True, index=True) # e.g. MED-AMOX-500
    name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False, index=True) # antipyretic, antibiotic, antimalarial, rehydration, vaccine, etc.
    dosage_form = Column(String(64), nullable=False) # tablet, vial, sachet, suspension
    unit_of_measure = Column(String(32), nullable=False) # strip, bottle, sachet, box
    velocity_class = Column(String(32), nullable=False, index=True) # high_velocity, intermittent, standard
    requires_cold_chain = Column(Boolean, default=False, nullable=False, index=True)
    temp_min_c = Column(Float, nullable=True) # e.g. 2.0
    temp_max_c = Column(Float, nullable=True) # e.g. 8.0
    unit_cost_usd = Column(Float, default=1.0, nullable=False)
    shelf_life_days = Column(Integer, default=730, nullable=False) # 2 years default
    criticality_tier = Column(String(16), default="B", nullable=False) # A (Life-saving), B (Essential), C (Standard)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    batches = relationship("StockBatch", back_populates="item")
    transactions = relationship("StockTransaction", back_populates="item")
    forecasts = relationship("Forecast", back_populates="item")
    alerts = relationship("Alert", back_populates="item")
    transfer_proposals = relationship("TransferProposal", back_populates="item")
