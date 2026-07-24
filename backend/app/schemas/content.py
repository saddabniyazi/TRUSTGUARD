from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SellerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class SellerOut(BaseModel):
    id: UUID
    name: str
    trust_score: float
    violation_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class GuardrailInfo(BaseModel):
    injection_detected: bool
    injection_matches: list[str]
    link_count: int


class ListingCreate(BaseModel):
    seller_id: UUID
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    category: str | None = None


class ListingOut(BaseModel):
    id: UUID
    seller_id: UUID
    title: str
    description: str
    category: str | None
    status: str
    injection_detected: bool
    created_at: datetime
    guardrail: GuardrailInfo | None = None

    model_config = {"from_attributes": True}


class ReviewCreate(BaseModel):
    product_id: UUID
    reviewer_name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)


class ReviewOut(BaseModel):
    id: UUID
    product_id: UUID
    reviewer_name: str
    text: str
    rating: int
    status: str
    injection_detected: bool
    created_at: datetime
    guardrail: GuardrailInfo | None = None

    model_config = {"from_attributes": True}
