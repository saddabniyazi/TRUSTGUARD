from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import ModeratorFeedback, User, Verdict
from app.db.session import get_db
from app.schemas.feedback import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ModeratorFeedback:
    """
    Records a human moderator's decision on a given Verdict — whether
    that's confirming the Aggregator got it right (human_decision
    matches the verdict's own decision) or overriding it. Every
    submission here, agree or disagree, is a labeled example: this is
    what Day 9's evaluation harness will read to measure how often the
    Aggregator's decision actually matches what a human would have
    done. Nothing here changes the listing/review's status — an
    override is a record for evaluation, not a live re-moderation
    (re-running POST /api/moderate/* does that).
    """
    verdict = db.get(Verdict, payload.verdict_id)
    if verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verdict not found")

    feedback = ModeratorFeedback(
        verdict_id=payload.verdict_id,
        moderator_id=current_user.id,
        human_decision=payload.human_decision,
        notes=payload.notes,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/verdict/{verdict_id}", response_model=list[FeedbackOut])
def list_feedback_for_verdict(
    verdict_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[ModeratorFeedback]:
    verdict = db.get(Verdict, verdict_id)
    if verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verdict not found")

    return (
        db.query(ModeratorFeedback)
        .filter(ModeratorFeedback.verdict_id == verdict_id)
        .order_by(ModeratorFeedback.created_at.desc())
        .all()
    )
