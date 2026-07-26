from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Review


def get_reviewer_velocity(db: Session, reviewer_name: str, exclude_review_id: UUID, window_hours: int = 24) -> int:
    """
    How many other reviews has this reviewer_name posted in the last
    `window_hours`? A real DB query, not something the LLM is asked to
    guess at. Shared between /api/agents (standalone testing) and
    /api/moderate (the actual pipeline) so both use identical logic.
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
