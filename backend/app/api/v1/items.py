from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.models.items import Item
from backend.app.models.audit import record_audit
from backend.app.schemas.item import ItemCreate, ItemResponse

router = APIRouter(prefix="/items", tags=["items"])

@router.get("", response_model=List[ItemResponse])
def list_items(
    category: Optional[str] = Query(None),
    velocity_class: Optional[str] = Query(None),
    cold_chain: Optional[bool] = Query(None),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    query = db.query(Item)
    if category:
        query = query.filter(Item.category == category)
    if velocity_class:
        query = query.filter(Item.velocity_class == velocity_class)
    if cold_chain is not None:
        query = query.filter(Item.requires_cold_chain == cold_chain)
    return query.limit(limit).all()

@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return item

@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    existing = db.query(Item).filter(Item.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Item ID already exists")

    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)

    record_audit(
        db=db,
        table_name="items",
        record_id=item.id,
        action="INSERT",
        actor=user.get("sub", "system"),
        new_state=payload.model_dump()
    )

    return item
