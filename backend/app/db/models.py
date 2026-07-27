import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid_col():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(Base):
    """
    Dashboard users: moderators and admins.
    (Marketplace *sellers* are a separate table — see Seller below —
    since they're subjects being moderated, not people who log in
    to review things, at least not in this version.)
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_col()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        Enum("admin", "moderator", name="user_role"),
        nullable=False,
        default="moderator",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    feedback_entries: Mapped[list["ModeratorFeedback"]] = relationship(back_populates="moderator")


class Seller(Base):
    """A marketplace seller — the subject of listings, and of trust scoring."""

    __tablename__ = "sellers"

    id: Mapped[uuid.UUID] = _uuid_col()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trust_score: Mapped[float] = mapped_column(Numeric(5, 2), default=50.00)
    violation_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listings: Mapped[list["Listing"]] = relationship(back_populates="seller")


class Listing(Base):
    """A product/service listing submitted by a seller — one of the two content types moderated."""

    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = _uuid_col()
    seller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sellers.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", "escalated", name="content_status"),
        default="pending",
        nullable=False,
    )
    injection_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    guardrail_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    seller: Mapped["Seller"] = relationship(back_populates="listings")
    verdicts: Mapped[list["Verdict"]] = relationship(
        primaryjoin="and_(Verdict.item_id==Listing.id, Verdict.item_type=='listing')",
        foreign_keys="Verdict.item_id",
        viewonly=True,
    )


class Review(Base):
    """A buyer review of a product — the second content type moderated."""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = _uuid_col()
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id"), nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", "escalated", name="content_status_review"),
        default="pending",
        nullable=False,
    )
    injection_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    guardrail_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyRule(Base):
    """
    Structured, versioned moderation policy — deliberately NOT a document
    that gets RAG'd over. Rules are discrete rows an agent can reason
    against directly, which is the whole point of this project's approach.
    """

    __tablename__ = "policy_rules"

    id: Mapped[uuid.UUID] = _uuid_col()
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Verdict(Base):
    """
    The output of the multi-agent pipeline for one item (listing or review).
    item_type + item_id together identify what was judged, since verdicts
    can apply to either table (kept polymorphic rather than two verdict
    tables, since the shape of a verdict is identical either way).
    """

    __tablename__ = "verdicts"

    id: Mapped[uuid.UUID] = _uuid_col()
    item_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(Enum("listing", "review", name="verdict_item_type"), nullable=False)
    decision: Mapped[str] = mapped_column(
        Enum("auto_approve", "auto_reject", "escalate_to_human", name="verdict_decision"),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rationale_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    agent_scores_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    feedback_entries: Mapped[list["ModeratorFeedback"]] = relationship(back_populates="verdict")


class EvalRun(Base):
    """
    A persisted result from running the full-pipeline adversarial-
    dataset harness (app/eval/harness.py) — the offline, "before you
    trust this in a demo" complement to the live moderator-agreement
    metric (app/api/eval.py's /agreement, computed fresh from
    ModeratorFeedback). Persisted because each run costs real Gemini
    quota; results shouldn't vanish the moment the script's stdout
    scrolls past, and a dashboard should be able to show a trend
    across runs, not just the most recent number.
    """

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = _uuid_col()
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    escalated_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False)
    true_positives: Mapped[int] = mapped_column(Integer, nullable=False)
    false_positives: Mapped[int] = mapped_column(Integer, nullable=False)
    false_negatives: Mapped[int] = mapped_column(Integer, nullable=False)
    true_negatives: Mapped[int] = mapped_column(Integer, nullable=False)
    precision: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    recall: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    f1: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    accuracy_on_decided: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    per_category_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModeratorFeedback(Base):
    """Human override/confirmation of a verdict — feeds the evaluation dataset later."""

    __tablename__ = "moderator_feedback"

    id: Mapped[uuid.UUID] = _uuid_col()
    verdict_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verdicts.id"), nullable=False)
    moderator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    human_decision: Mapped[str] = mapped_column(
        Enum("auto_approve", "auto_reject", "escalate_to_human", name="human_decision_type"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    verdict: Mapped["Verdict"] = relationship(back_populates="feedback_entries")
    moderator: Mapped["User"] = relationship(back_populates="feedback_entries")
