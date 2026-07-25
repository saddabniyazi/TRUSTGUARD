from app.agents.schemas import FraudAgentVerdict, PolicyAgentVerdict, ToxicityAgentVerdict
from pydantic import BaseModel


class AgentEvaluationResult(BaseModel):
    """
    Combined raw output of the agents run on one piece of content.
    Deliberately NOT a final moderation decision — that reconciliation
    is the Aggregator/Judge Agent's job (Day 5). This is here so agents
    can be tested and demoed independently before the full pipeline
    exists.

    fraud is only populated for reviews — fake-review detection doesn't
    apply to listings the same way (a listing has no "reviewer" to
    judge the authenticity of).
    """

    item_type: str
    item_id: str
    policy: PolicyAgentVerdict
    toxicity: ToxicityAgentVerdict
    fraud: FraudAgentVerdict | None = None
