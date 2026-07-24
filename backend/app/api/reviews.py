from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import Listing, Review, User
from app.db.session import get_db
from app.guardrails.sanitizer import run_guardrail
from app.schemas.content import GuardrailInfo, ReviewCreate, ReviewOut

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def submit_review(payload: ReviewCreate, db: Session = Depends(get_db)) -> ReviewOut:
    product = db.get(Listing, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product (listing) not found")

    report = run_guardrail(payload.text)

    review = Review(
        product_id=payload.product_id,
        reviewer_name=payload.reviewer_name,
        text=payload.text,
        rating=payload.rating,
        status="pending",
        injection_detected=report.injection_detected,
        guardrail_notes=report.to_notes_dict(),
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return ReviewOut(
        **{k: getattr(review, k) for k in ("id", "product_id", "reviewer_name", "text", "rating", "status", "injection_detected", "created_at")},
        guardrail=GuardrailInfo(
            injection_detected=report.injection_detected,
            injection_matches=report.injection_matches,
            link_count=report.link_count,
        ),
    )


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Review:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review


@router.get("", response_model=list[ReviewOut])
def list_reviews(
    status_filter: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[Review]:
    query = db.query(Review)
    if status_filter:
        query = query.filter(Review.status == status_filter)
    return query.order_by(Review.created_at.desc()).limit(min(limit, 200)).all()
