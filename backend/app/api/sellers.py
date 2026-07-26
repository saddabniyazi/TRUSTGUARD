from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.trust import compute_adjusted_thresholds
from app.api.auth import get_current_user
from app.db.models import Listing, Seller, User, Verdict
from app.db.session import get_db
from app.schemas.content import SellerCreate, SellerOut

router = APIRouter(prefix="/api/sellers", tags=["sellers"])


@router.post("", response_model=SellerOut, status_code=status.HTTP_201_CREATED)
def create_seller(payload: SellerCreate, db: Session = Depends(get_db)) -> Seller:
    # Left unauthenticated for now, matching /api/listings and /api/reviews:
    # in production this would be called by the marketplace backend via a
    # scoped API key (Day 9), not by end users directly.
    seller = Seller(name=payload.name)
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return seller


@router.get("/{seller_id}", response_model=SellerOut)
def get_seller(
    seller_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Seller:
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    return seller


@router.get("/{seller_id}/audit", response_model=dict)
def get_seller_audit(
    seller_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    """
    Full "why does this seller have this trust score" view: current
    trust_score and violation_count, the thresholds that score
    currently produces (so an analyst can see exactly how strict/lenient
    the system is being toward this seller right now, not just the raw
    number), and every verdict ever recorded across all of this
    seller's listings, newest first — the actual audit trail, not just
    a snapshot.
    """
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")

    listings = db.query(Listing).filter(Listing.seller_id == seller_id).all()
    listing_ids = [listing.id for listing in listings]

    verdicts = (
        db.query(Verdict)
        .filter(Verdict.item_type == "listing", Verdict.item_id.in_(listing_ids))
        .order_by(Verdict.created_at.desc())
        .all()
        if listing_ids
        else []
    )
    listing_titles = {listing.id: listing.title for listing in listings}

    reject_threshold, approve_threshold = compute_adjusted_thresholds(float(seller.trust_score))

    return {
        "seller": {
            "id": str(seller.id),
            "name": seller.name,
            "trust_score": float(seller.trust_score),
            "violation_count": seller.violation_count,
        },
        "current_thresholds": {
            "reject_threshold": round(reject_threshold, 3),
            "approve_threshold": round(approve_threshold, 3),
        },
        "listing_count": len(listings),
        "verdict_history": [
            {
                "verdict_id": str(v.id),
                "listing_id": str(v.item_id),
                "listing_title": listing_titles.get(v.item_id, "(deleted)"),
                "decision": v.decision,
                "confidence": float(v.confidence),
                "reasoning": v.rationale_json.get("reasoning"),
                "created_at": v.created_at.isoformat(),
            }
            for v in verdicts
        ],
    }
