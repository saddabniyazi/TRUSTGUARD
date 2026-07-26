from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    verdict_id: UUID
    human_decision: Literal["auto_approve", "auto_reject", "escalate_to_human"]
    notes: str | None = None


class FeedbackOut(BaseModel):
    id: UUID
    verdict_id: UUID
    moderator_id: UUID
    human_decision: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
