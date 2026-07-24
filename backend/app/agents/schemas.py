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
