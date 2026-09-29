from typing import List, Optional, Dict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.models.intelligence import TransferProposal, Forecast
from backend.app.models.audit import record_audit
from backend.app.schemas.intelligence import TransferProposalResponse
from backend.app.optimization.redistribution import RedistributionOptimizer

router = APIRouter(prefix="/transfers", tags=["transfers"])

class RejectProposalRequest(BaseModel):
    reason: str

class GenerateTransfersRequest(BaseModel):
    planning_horizon_days: int = 30
    forecasts: Optional[Dict[str, float]] = None # "fac_id:item_id" -> demand_qty

@router.get("", response_model=List[TransferProposalResponse])
def list_proposals(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(TransferProposal)
    if status_filter:
        query = query.filter(TransferProposal.status == status_filter)
    return query.order_by(TransferProposal.created_at.desc()).limit(limit).all()

@router.post("/generate", response_model=List[TransferProposalResponse])
def generate_transfers(
    payload: Optional[GenerateTransfersRequest] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    """
    Triggers Google OR-Tools MILP Redistribution Engine:
    Solves optimal transfers from surplus to deficit clinics respecting cold-chain and expiry.
    """
    optimizer = RedistributionOptimizer(
        planning_horizon_days=payload.planning_horizon_days if payload else 30
    )
    demand_dict = {}
    if payload and payload.forecasts:
        for k, v in payload.forecasts.items():
            if ":" in k:
                fac, itm = k.split(":", 1)
                demand_dict[(fac, itm)] = float(v)
    else:
        # Load latest p50 forecasts from DB
        db_forecasts = db.query(Forecast).all()
        for f in db_forecasts:
            val = f.reconciled_p50 if f.reconciled_p50 is not None else f.p50
            demand_dict[(f.facility_id, f.item_id)] = float(val)
            
    proposals = optimizer.solve_redistribution(
        db=db,
        demand_forecasts=demand_dict,
        actor=user.get("sub", "redistribution_engine")
    )
    return proposals

@router.post("/{proposal_id}/approve", response_model=TransferProposalResponse)
def approve_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    proposal = db.query(TransferProposal).filter(TransferProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    proposal.status = "approved"
    proposal.reviewed_by = user.get("sub", "human_reviewer")
    proposal.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)

    record_audit(
        db=db,
        table_name="transfer_proposals",
        record_id=proposal.id,
        action="APPROVE_TRANSFER",
        actor=user.get("sub", "human_reviewer"),
        new_state={"status": "approved", "qty": proposal.quantity}
    )

    return proposal

@router.post("/{proposal_id}/reject", response_model=TransferProposalResponse)
def reject_proposal(
    proposal_id: str,
    payload: RejectProposalRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_stub)
):
    proposal = db.query(TransferProposal).filter(TransferProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    proposal.status = "rejected"
    proposal.rejection_reason = payload.reason
    proposal.reviewed_by = user.get("sub", "human_reviewer")
    proposal.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)

    record_audit(
        db=db,
        table_name="transfer_proposals",
        record_id=proposal.id,
        action="REJECT_TRANSFER",
        actor=user.get("sub", "human_reviewer"),
        new_state={"status": "rejected", "reason": payload.reason}
    )

    return proposal
