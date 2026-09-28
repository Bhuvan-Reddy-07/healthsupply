from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    table_name: str
    record_id: str
    action: str
    actor: str
    timestamp: datetime
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    previous_hash: str
    tamper_hash: str

class AuditIntegrityCheckResponse(BaseModel):
    is_valid: bool
    total_records: int
    verified_records: int
    message: str
