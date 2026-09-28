from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user_stub
from backend.app.models.intelligence import TransferProposal
from backend.app.models.audit import record_audit
from backend.app.schemas.intelligence import TransferProposalResponse

router = APIRouter(prefix="/transfers", tags=["transfers"])

class RejectProposalRequest(BaseModel):
    reason: str

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
