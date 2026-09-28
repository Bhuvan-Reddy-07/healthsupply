import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.models.audit import record_audit
from backend.app.schemas.stock import StockTransactionCreate, StockTransactionResponse

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.get("", response_model=List[StockTransactionResponse])
def list_transactions(
    facility_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    censored: Optional[bool] = Query(None),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    query = db.query(StockTransaction)
    if facility_id:
        query = query.filter(StockTransaction.facility_id == facility_id)
    if item_id:
        query = query.filter(StockTransaction.item_id == item_id)
    if censored is not None:
        query = query.filter(StockTransaction.censored == censored)
    return query.order_by(StockTransaction.tx_timestamp.desc()).limit(limit).all()

@router.post("", response_model=StockTransactionResponse, status_code=status.HTTP_201_CREATED)
def record_transaction(
    payload: StockTransactionCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    """
    Idempotent transaction submission:
    - Deduplicates by crdt_tx_id (CRDT idempotency guarantee)
    - Enforces FEFO batch deduction on dispense
    - Enforces strictly non-negative stock (stock goes negative nowhere)
    - Tags censored=True and captures unfulfilled_quantity when stock hits zero
    """
    # 1. Idempotency Check by CRDT ID
    existing = db.query(StockTransaction).filter(StockTransaction.crdt_tx_id == payload.crdt_tx_id).first()
    if existing:
        return existing # Cleanly return existing transaction without re-applying

    tx_id = f"TX-{uuid.uuid4().hex[:12]}"
    effective_qty = payload.quantity
    is_censored = payload.censored
    unfulfilled = payload.unfulfilled_quantity
    assigned_batch_id = payload.batch_id

    # 2. Process Dispense
    if payload.tx_type == "dispense":
        # If specific batch provided
        if assigned_batch_id:
            batch = db.query(StockBatch).filter(StockBatch.id == assigned_batch_id).with_for_update().first()
            if not batch:
                raise HTTPException(status_code=404, detail="Specified stock batch not found")
            
            if batch.current_quantity <= 0:
                # Stockout occurred: Censored demand trap
                effective_qty = 0.0
                is_censored = True
                unfulfilled = payload.quantity
            elif batch.current_quantity < effective_qty:
                # Partial fulfillment
                unfulfilled = effective_qty - batch.current_quantity
                effective_qty = batch.current_quantity
                batch.current_quantity = 0.0
                batch.status = "depleted"
                is_censored = True
            else:
                batch.current_quantity -= effective_qty
                if batch.current_quantity == 0:
                    batch.status = "depleted"
        else:
            # FEFO Allocation across facility batches
            batches = (
                db.query(StockBatch)
                .filter(
                    StockBatch.facility_id == payload.facility_id,
                    StockBatch.item_id == payload.item_id,
                    StockBatch.status == "active",
                    StockBatch.current_quantity > 0
                )
                .order_by(StockBatch.expiry_date.asc())
                .with_for_update()
                .all()
            )

            total_available = sum(b.current_quantity for b in batches)
            if total_available <= 0:
                # Stockout: Zero consumption recorded, censored tagged True
                effective_qty = 0.0
                is_censored = True
                unfulfilled = payload.quantity
            else:
                remaining_to_dispense = payload.quantity
                if total_available < remaining_to_dispense:
                    unfulfilled = remaining_to_dispense - total_available
                    remaining_to_dispense = total_available
                    is_censored = True
                    effective_qty = total_available

                for b in batches:
                    if remaining_to_dispense <= 0:
                        break
                    deduct = min(b.current_quantity, remaining_to_dispense)
                    b.current_quantity -= deduct
                    remaining_to_dispense -= deduct
                    assigned_batch_id = b.id
                    if b.current_quantity == 0:
                        b.status = "depleted"

    elif payload.tx_type == "receive":
        if assigned_batch_id:
            batch = db.query(StockBatch).filter(StockBatch.id == assigned_batch_id).with_for_update().first()
            if batch:
                batch.current_quantity += payload.quantity
                if batch.status == "depleted":
                    batch.status = "active"

    # Create transaction record
    tx = StockTransaction(
        id=tx_id,
        crdt_tx_id=payload.crdt_tx_id,
        facility_id=payload.facility_id,
        item_id=payload.item_id,
        batch_id=assigned_batch_id,
        tx_type=payload.tx_type,
        quantity=effective_qty,
        censored=is_censored,
        unfulfilled_quantity=unfulfilled,
        tx_timestamp=payload.tx_timestamp,
        source=payload.source,
        source_reliability_score=payload.source_reliability_score,
        data_quality_score=payload.data_quality_score,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    record_audit(
        db=db,
        table_name="stock_transactions",
        record_id=tx.id,
        action=f"TX_{payload.tx_type.upper()}",
        actor=user.get("sub", "system"),
        new_state={"crdt_id": tx.crdt_tx_id, "qty": tx.quantity, "censored": tx.censored}
    )

    return tx
