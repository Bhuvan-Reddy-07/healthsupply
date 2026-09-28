from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db
from backend.app.models.intelligence import Forecast
from backend.app.schemas.intelligence import ForecastResponse

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

@router.get("", response_model=List[ForecastResponse])
def list_forecasts(
    facility_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db)
):
    query = db.query(Forecast)
    if facility_id:
        query = query.filter(Forecast.facility_id == facility_id)
    if item_id:
        query = query.filter(Forecast.item_id == item_id)
    if from_date:
        query = query.filter(Forecast.forecast_date >= from_date)
    if to_date:
        query = query.filter(Forecast.forecast_date <= to_date)
    return query.order_by(Forecast.forecast_date.asc()).limit(limit).all()
