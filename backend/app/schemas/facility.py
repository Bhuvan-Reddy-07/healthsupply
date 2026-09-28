from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class FacilityBase(BaseModel):
    id: str
    name: str
    country: str
    region: str
    district: str
    tier: str = Field(..., description="PHC, CHC, or DH")
    latitude: float
    longitude: float
    has_cold_chain: bool = False
    cold_chain_capacity_liters: float = 0.0
    population_served: int = 10000
    contact_phone: Optional[str] = None

class FacilityCreate(FacilityBase):
    pass

class FacilityResponse(FacilityBase):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime
