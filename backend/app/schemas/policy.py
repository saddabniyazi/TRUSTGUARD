from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyRuleCreate(BaseModel):
    category: str = Field(min_length=1, max_length=255)
    rule_text: str = Field(min_length=1)


class PolicyRuleOut(BaseModel):
    id: UUID
    category: str
    rule_text: str
    version: int
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
