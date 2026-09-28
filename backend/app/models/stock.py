from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class StockBatch(Base):
    __tablename__ = "stock_batches"

    id = Column(String(64), primary_key=True, index=True) # e.g. BATCH-FAC-A-001-MED-AMOX-2024-01
    batch_number = Column(String(64), nullable=False, index=True) # e.g. B-2231
    facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(64), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    current_quantity = Column(Float, nullable=False, default=0.0)
    initial_quantity = Column(Float, nullable=False, default=0.0)
    mfg_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    gs1_gtin = Column(String(32), nullable=False, index=True) # GS1 GTIN-14
    qr_data_matrix = Column(String(255), nullable=True) # Raw GS1 DataMatrix string
    status = Column(String(32), default="active", nullable=False, index=True) # active, quarantined, expired, depleted
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("current_quantity >= 0", name="chk_stock_quantity_non_negative"),
        CheckConstraint("expiry_date >= mfg_date", name="chk_expiry_after_mfg"),
    )

    # Relationships
    facility = relationship("Facility", back_populates="batches")
    item = relationship("Item", back_populates="batches")
    transactions = relationship("StockTransaction", back_populates="batch")
    transfer_proposals = relationship("TransferProposal", back_populates="batch")


class StockTransaction(Base):
    __tablename__ = "stock_transactions"

    id = Column(String(64), primary_key=True, index=True) # TX-UUID
    crdt_tx_id = Column(String(64), nullable=False, unique=True, index=True) # Client idempotency key
    facility_id = Column(String(64), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(64), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(String(64), ForeignKey("stock_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Types: dispense, receive, waste_expired, waste_damaged, transfer_out, transfer_in, inventory_adjustment
    tx_type = Column(String(32), nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0.0)
    
    # Censored demand tagging when stock reaches zero
    censored = Column(Boolean, default=False, nullable=False, index=True)
    unfulfilled_quantity = Column(Float, default=0.0, nullable=False)
    
    tx_timestamp = Column(DateTime, nullable=False, index=True)
    source = Column(String(32), default="edge_pwa", nullable=False) # edge_pwa, sms_fallback, batch_sync, simulator
    source_reliability_score = Column(Float, default=1.0, nullable=False)
    data_quality_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="chk_tx_quantity_non_negative"),
    )

    # Relationships
    facility = relationship("Facility", back_populates="transactions")
    item = relationship("Item", back_populates="transactions")
    batch = relationship("StockBatch", back_populates="transactions")
