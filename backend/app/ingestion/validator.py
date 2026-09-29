from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, model_validator

class StockTxEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    crdt_tx_id: str = Field(..., min_length=4, description="Client CRDT idempotency ID")
    facility_id: str = Field(..., description="Target facility ID")
    item_id: str = Field(..., description="Target item code")
    batch_id: Optional[str] = None
    tx_type: str = Field(..., description="dispense, receive, waste_expired, waste_damaged, transfer_in, transfer_out")
    quantity: float = Field(..., description="Transaction quantity (must be strictly > 0)")
    tx_timestamp: datetime = Field(..., description="Timestamp of transaction at client")
    source: str = Field(default="edge_pwa", description="edge_pwa, sms_fallback, batch_sync, sensor")
    
    # Optional batch validation attributes
    batch_mfg_date: Optional[date] = None
    batch_expiry_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_business_rules(self):
        # 1. Quantity must be strictly positive
        if self.quantity <= 0:
            raise ValueError("ERR_NEGATIVE_QTY: Quantity must be strictly greater than zero")
        
        # 2. Expiry must not precede manufacturing date
        if self.batch_expiry_date and self.batch_mfg_date:
            if self.batch_expiry_date < self.batch_mfg_date:
                raise ValueError("ERR_EXPIRY_BEFORE_MFG: Expiry date cannot be earlier than manufacturing date")

        return self


class BedStateEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    facility_id: str
    timestamp: datetime
    total_beds: int = Field(..., ge=0)
    occupied_beds: int = Field(..., ge=0)
    icu_occupied: int = Field(default=0, ge=0)
    pediatric_occupied: int = Field(default=0, ge=0)
    maternity_occupied: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_bed_capacity(self):
        if self.total_beds < 0 or self.occupied_beds < 0:
            raise ValueError("ERR_NEGATIVE_BED_COUNT: Bed counts must be non-negative")
        return self


class StaffAttendanceEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    facility_id: str
    date: date
    doctors_present: int = Field(..., ge=0)
    nurses_present: int = Field(..., ge=0)
    pharmacists_present: int = Field(..., ge=0)
    shift: str = Field(default="day")


class SensorTempEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    facility_id: str
    device_id: str
    temperature_c: float
    timestamp: datetime
    batch_id: Optional[str] = None
