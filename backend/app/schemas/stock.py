from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator

class StockBatchBase(BaseModel):
    id: str
    batch_number: str
    facility_id: str
    item_id: str
    current_quantity: float = Field(..., ge=0, description="Quantity must be non-negative")
    initial_quantity: float = Field(..., ge=0)
    mfg_date: date
    expiry_date: date
    gs1_gtin: str = Field(..., description="GS1 GTIN-14 code")
    qr_data_matrix: Optional[str] = None
    status: str = "active"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.expiry_date < self.mfg_date:
            raise ValueError("expiry_date cannot be earlier than mfg_date")
        return self

class StockBatchCreate(StockBatchBase):
    pass

class StockBatchResponse(StockBatchBase):
    model_config = ConfigDict(from_attributes=True)
    received_at: datetime
    created_at: datetime
    updated_at: datetime


class StockTransactionBase(BaseModel):
    crdt_tx_id: str
    facility_id: str
    item_id: str
    batch_id: Optional[str] = None
    tx_type: str = Field(..., description="dispense, receive, waste_expired, waste_damaged, transfer_out, transfer_in")
    quantity: float = Field(..., ge=0)
    censored: bool = False
    unfulfilled_quantity: float = 0.0
    tx_timestamp: datetime
    source: str = "edge_pwa"
    source_reliability_score: float = 1.0
    data_quality_score: float = 1.0

class StockTransactionCreate(StockTransactionBase):
    pass

class StockTransactionResponse(StockTransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
