from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class ItemBase(BaseModel):
    id: str
    name: str
    category: str
    dosage_form: str
    unit_of_measure: str
    velocity_class: str = Field(..., description="high_velocity, intermittent, or standard")
    requires_cold_chain: bool = False
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    unit_cost_usd: float = 1.0
    shelf_life_days: int = 730
    criticality_tier: str = "B"

class ItemCreate(ItemBase):
    pass

class ItemResponse(ItemBase):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
