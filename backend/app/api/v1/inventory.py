from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.models.stock import StockBatch
from backend.app.models.audit import record_audit
from backend.app.schemas.stock import StockBatchCreate, StockBatchResponse

router = APIRouter(prefix="/inventory", tags=["inventory"])

@router.get("/batches", response_model=List[StockBatchResponse])
def list_batches(
    facility_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    query = db.query(StockBatch)
    if facility_id:
        query = query.filter(StockBatch.facility_id == facility_id)
    if item_id:
        query = query.filter(StockBatch.item_id == item_id)
    if status_filter:
        query = query.filter(StockBatch.status == status_filter)
    return query.order_by(StockBatch.expiry_date.asc()).limit(limit).all()

@router.get("/on-hand/{facility_id}")
def get_facility_on_hand(facility_id: str, db: Session = Depends(get_db)):
    """Returns aggregated on-hand quantities grouped by item for a facility."""
    results = (
        db.query(
            StockBatch.item_id,
            func.sum(StockBatch.current_quantity).label("total_on_hand"),
            func.count(StockBatch.id).label("active_batches")
        )
        .filter(StockBatch.facility_id == facility_id)
        .filter(StockBatch.status == "active")
        .group_by(StockBatch.item_id)
        .all()
    )
    return [
        {"item_id": r[0], "total_on_hand": float(r[1] or 0), "active_batches": r[2]}
        for r in results
    ]

@router.post("/batches", response_model=StockBatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: StockBatchCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    existing = db.query(StockBatch).filter(StockBatch.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Batch ID already exists")

    batch = StockBatch(**payload.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)

    record_audit(
        db=db,
        table_name="stock_batches",
        record_id=batch.id,
        action="RECEIVE_BATCH",
        actor=user.get("sub", "system"),
        new_state={"batch_number": batch.batch_number, "qty": batch.current_quantity, "item_id": batch.item_id}
    )

    return batch
