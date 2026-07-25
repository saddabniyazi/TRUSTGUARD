from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.evaluation_schemas import AgentEvaluationResult
from app.agents.fraud_agent import run_fraud_agent
from app.agents.policy_agent import run_policy_agent
from app.agents.toxicity_agent import run_toxicity_agent
from app.api.auth import get_current_user
from app.core.llm_client import AgentCallError
from app.db.models import Listing, PolicyRule, Review, User
from app.db.session import get_db

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _get_reviewer_velocity(db: Session, reviewer_name: str, exclude_review_id: UUID, window_hours: int = 24) -> int:
    """
    Real DB signal for the Fraud Agent: how many other reviews has this
    reviewer_name posted in the last `window_hours`? A crude proxy (no
    real user accounts yet — Day 8's trust-score system is where this
    gets attached to actual seller/reviewer identity), but it's a real
    query against real data, not a number the LLM is asked to guess.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    return (
        db.query(Review)
        .filter(
            Review.reviewer_name == reviewer_name,
            Review.created_at >= cutoff,
            Review.id != exclude_review_id,
        )
        .count()
    )


@router.post("/evaluate/listing/{listing_id}", response_model=AgentEvaluationResult)
def evaluate_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> AgentEvaluationResult:
    """
    Runs the Policy Compliance Agent and Toxicity/Spam Agent on a
    listing's title + description. Fraud detection doesn't apply here
    (see AgentEvaluationResult docstring) — this endpoint exists so
    each agent can be tested and demoed before the full multi-agent
    pipeline (Day 6) wires them together automatically.
    """
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    content_text = f"{listing.title}\n{listing.description}"
    active_rules = db.query(PolicyRule).filter(PolicyRule.active.is_(True)).all()

    try:
        policy_verdict = run_policy_agent(content_text, active_rules)
        toxicity_verdict = run_toxicity_agent(content_text)
    except AgentCallError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return AgentEvaluationResult(
        item_type="listing",
        item_id=str(listing_id),
        policy=policy_verdict,
        toxicity=toxicity_verdict,
    )


@router.post("/evaluate/review/{review_id}", response_model=AgentEvaluationResult)
def evaluate_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> AgentEvaluationResult:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    active_rules = db.query(PolicyRule).filter(PolicyRule.active.is_(True)).all()
    reviewer_velocity = _get_reviewer_velocity(db, review.reviewer_name, review.id)

    try:
        policy_verdict = run_policy_agent(review.text, active_rules)
        toxicity_verdict = run_toxicity_agent(review.text)
        fraud_verdict = run_fraud_agent(review.text, reviewer_velocity)
    except AgentCallError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return AgentEvaluationResult(
        item_type="review",
        item_id=str(review_id),
        policy=policy_verdict,
        toxicity=toxicity_verdict,
        fraud=fraud_verdict,
    )
