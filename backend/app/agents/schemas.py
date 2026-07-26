from typing import Literal

from pydantic import BaseModel, Field


class PolicyAgentVerdict(BaseModel):
    """Structured output from the Policy Compliance Agent."""

    compliant: bool = Field(description="False if the content violates one or more policy rules.")
    violated_categories: list[str] = Field(
        default_factory=list,
        description="Policy rule categories violated (empty if compliant).",
    )
    reasoning: str = Field(description="Brief, specific explanation citing what in the content triggered the verdict.")
    confidence: float = Field(ge=0.0, le=1.0, description="Model's confidence in this verdict, 0 to 1.")


class ToxicityAgentVerdict(BaseModel):
    """Structured output from the Toxicity/Spam Agent."""

    is_toxic: bool = Field(description="True if the content contains hate speech, harassment, or abusive language.")
    is_spam: bool = Field(description="True if the content is spam, an ad, or contains off-platform solicitation.")
    reasoning: str = Field(description="Brief, specific explanation citing what in the content triggered the verdict.")
    confidence: float = Field(ge=0.0, le=1.0, description="Model's confidence in this verdict, 0 to 1.")


class FraudAgentVerdict(BaseModel):
    """Structured output from the Fraud Pattern Agent."""

    is_likely_fake: bool = Field(description="True if the review shows signs of being fake, incentivized, or inauthentic.")
    fraud_indicators: list[str] = Field(
        default_factory=list,
        description="Specific fraud signals found, e.g. 'generic_praise', 'incentive_disclosure', 'review_velocity_anomaly'.",
    )
    reasoning: str = Field(description="Brief, specific explanation citing what in the content and signals triggered the verdict.")
    confidence: float = Field(ge=0.0, le=1.0, description="Model's confidence in this verdict, 0 to 1.")


class AggregatorVerdict(BaseModel):
    """
    Final, reconciled moderation decision — the output of deterministic
    Python logic (see app/agents/aggregator.py), NOT another LLM call.
    Combines the Policy, Toxicity, and (for reviews) Fraud verdicts into
    one decision the system will actually act on.
    """

    decision: Literal["auto_approve", "auto_reject", "escalate_to_human"]
    confidence: float = Field(ge=0.0, le=1.0, description="Aggregate confidence behind this decision.")
    reasoning: str = Field(description="Human-readable explanation of how the contributing verdicts led to this decision.")
    contributing_signals: list[str] = Field(
        default_factory=list,
        description="Which agent(s) and signal(s) drove the decision, e.g. 'policy: non-compliant (confidence=0.92)'.",
    )
