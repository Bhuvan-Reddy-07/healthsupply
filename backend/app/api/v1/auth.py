from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from backend.app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    role: str

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """JWT Auth stub endpoint for clinical & district officer access."""
    # Statically verified dev credential stub
    if request.password in ["secret", "password", "demo"]:
        token = create_access_token(
            subject=request.username,
            claims={"role": "pharmacist", "facility_id": "FAC-A-001"}
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=request.username,
            role="pharmacist"
        )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
