from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class ForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    facility_id: str
    item_id: str
    forecast_date: date
    model_version: str
    p10: float
    p50: float
    p90: float
    reconciled_p50: Optional[float] = None
    created_at: datetime

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    facility_id: str
    item_id: Optional[str] = None
    alert_type: str
    severity: str
    days_remaining: Optional[float] = None
    p_stockout_before_lead: Optional[float] = None
    message: str
    is_acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    created_at: datetime

class TransferProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    donor_facility_id: str
    recipient_facility_id: str
    item_id: str
    batch_id: str
    quantity: float
    donor_cover_days_before: float
    donor_cover_days_after: float
    recipient_cover_days_before: float
    recipient_cover_days_after: float
    eta_days: float
    cold_chain_required: bool
    priority: str = "medium"
    explanation: str
    status: str
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

class OutbreakInjectionRequest(BaseModel):
    district: str
    item_class: str = Field(..., description="e.g. antipyretic, antibiotic, antimalarial")
    multiplier: float = Field(default=3.5, gt=1.0, description="Peak demand surge multiplier")
    ramp_days: int = Field(default=7, ge=1, le=30, description="Logistic ramp rise time in days")
    start_date: Optional[date] = None
