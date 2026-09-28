from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.models.intelligence import Alert
from backend.app.models.audit import record_audit
from backend.app.schemas.intelligence import AlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("", response_model=List[AlertResponse])
def list_alerts(
    facility_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None), # amber, red, black
    is_acknowledged: Optional[bool] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    query = db.query(Alert)
    if facility_id:
        query = query.filter(Alert.facility_id == facility_id)
    if severity:
        query = query.filter(Alert.severity == severity)
    if is_acknowledged is not None:
        query = query.filter(Alert.is_acknowledged == is_acknowledged)
    return query.order_by(Alert.created_at.desc()).limit(limit).all()

@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = user.get("sub", "system")
    db.commit()
    db.refresh(alert)

    record_audit(
        db=db,
        table_name="alerts",
        record_id=alert.id,
        action="ACKNOWLEDGE_ALERT",
        actor=user.get("sub", "system"),
        new_state={"acknowledged": True, "at": alert.acknowledged_at.isoformat()}
    )

    return alert
