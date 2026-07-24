from app.agents.schemas import PolicyAgentVerdict, ToxicityAgentVerdict
from pydantic import BaseModel


class AgentEvaluationResult(BaseModel):
    """
    Combined raw output of both Day-3 agents for one piece of content.
    Deliberately NOT a final moderation decision — that reconciliation
    is the Aggregator/Judge Agent's job (Day 5). This is here so the
    two agents can be tested and demoed independently before the full
    pipeline exists.
    """

    item_type: str
    item_id: str
    policy: PolicyAgentVerdict
    toxicity: ToxicityAgentVerdict
