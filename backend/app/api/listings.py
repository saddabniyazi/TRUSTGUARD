from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import Listing, Seller, User
from app.db.session import get_db
from app.guardrails.sanitizer import run_guardrail
from app.schemas.content import GuardrailInfo, ListingCreate, ListingOut

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.post("", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def submit_listing(payload: ListingCreate, db: Session = Depends(get_db)) -> ListingOut:
    """
    Ingests a new listing. Left unauthenticated deliberately: in the real
    architecture, this is called by the marketplace's own backend on
    behalf of a seller (not by the seller directly) — API-key auth for
    that server-to-server call lands on Day 9 alongside rate limiting.

    Runs the guardrail pre-filter on title + description BEFORE any of
    it would ever reach an LLM agent (Day 3+). This endpoint does NOT
    decide approve/reject — that's the multi-agent pipeline's job. It
    only records what the pre-filter found and leaves the item pending.
    """
    seller = db.get(Seller, payload.seller_id)
    if seller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")

    combined_text = f"{payload.title}\n{payload.description}"
    report = run_guardrail(combined_text)

    listing = Listing(
        seller_id=payload.seller_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        status="pending",
        injection_detected=report.injection_detected,
        guardrail_notes=report.to_notes_dict(),
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return ListingOut(
        **{k: getattr(listing, k) for k in ("id", "seller_id", "title", "description", "category", "status", "injection_detected", "created_at")},
        guardrail=GuardrailInfo(
            injection_detected=report.injection_detected,
            injection_matches=report.injection_matches,
            link_count=report.link_count,
        ),
    )


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Listing:
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing


@router.get("", response_model=list[ListingOut])
def list_listings(
    status_filter: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[Listing]:
    query = db.query(Listing)
    if status_filter:
        query = query.filter(Listing.status == status_filter)
    return query.order_by(Listing.created_at.desc()).limit(min(limit, 200)).all()
