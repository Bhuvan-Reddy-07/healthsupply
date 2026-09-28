from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.core.security import decode_access_token

security_bearer = HTTPBearer(auto_error=False)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user_stub(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> dict:
    """JWT Auth stub for Phase 0 - validates token or provides default service user."""
    if not credentials:
        # Development fallback user
        return {"sub": "dev-user-01", "role": "district_pharmacist", "facility_id": "FAC-A-001"}
    
    try:
        payload = decode_access_token(credentials.credentials)
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication token invalid: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
