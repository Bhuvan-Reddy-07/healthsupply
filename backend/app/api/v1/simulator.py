from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.schemas.intelligence import OutbreakInjectionRequest
from simulator.outbreak import inject_outbreak

router = APIRouter(prefix="/simulator", tags=["simulator"])

@router.post("/inject-outbreak")
def trigger_outbreak_injection(
    payload: OutbreakInjectionRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    """
    Spikes demand with a logistic ramp for a target district and item class.
    inject_outbreak(district, item_class, multiplier, ramp_days)
    """
    try:
        result = inject_outbreak(
            db=db,
            district=payload.district,
            item_class=payload.item_class,
            multiplier=payload.multiplier,
            ramp_days=payload.ramp_days,
            start_date=payload.start_date
        )
        return {
            "status": "success",
            "message": f"Injected outbreak in {payload.district} for {payload.item_class}",
            "details": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Outbreak injection failed: {str(e)}"
        )
