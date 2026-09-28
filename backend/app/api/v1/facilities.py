from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.models.facilities import Facility
from backend.app.models.audit import record_audit
from backend.app.schemas.facility import FacilityCreate, FacilityResponse

router = APIRouter(prefix="/facilities", tags=["facilities"])

@router.get("", response_model=List[FacilityResponse])
def list_facilities(
    country: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    query = db.query(Facility)
    if country:
        query = query.filter(Facility.country == country)
    if district:
        query = query.filter(Facility.district == district)
    if tier:
        query = query.filter(Facility.tier == tier)
    return query.limit(limit).all()

@router.get("/{facility_id}", response_model=FacilityResponse)
def get_facility(facility_id: str, db: Session = Depends(get_db)):
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail=f"Facility {facility_id} not found")
    return facility

@router.post("", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED)
def create_facility(
    payload: FacilityCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    existing = db.query(Facility).filter(Facility.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Facility ID already exists")
    
    facility = Facility(**payload.model_dump())
    db.add(facility)
    db.commit()
    db.refresh(facility)

    # Tamper-evident audit trail
    record_audit(
        db=db,
        table_name="facilities",
        record_id=facility.id,
        action="INSERT",
        actor=user.get("sub", "system"),
        new_state=payload.model_dump()
    )

    return facility
