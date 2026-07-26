from typing import Literal, TypedDict

from app.agents.dto import RuleDTO
from app.agents.schemas import (
    AggregatorVerdict,
    FraudAgentVerdict,
    PolicyAgentVerdict,
    ToxicityAgentVerdict,
)


class ModerationState(TypedDict, total=False):
    """
    Shared state threaded through the moderation graph. `total=False`
    because most fields start unset and get filled in as nodes run —
    only the graph's entry inputs (content_text, rules,
    guardrail_injection_detected, and reviewer_velocity for reviews)
    are present at invocation time.

    Deliberately holds plain data only (Pydantic verdicts, a dataclass
    for rules, primitives) — no DB session, no SQLAlchemy ORM objects.
    Independent nodes (policy/toxicity/fraud) run concurrently; a DB
    session isn't safe to share across concurrently-executing nodes,
    so all DB access happens before the graph is invoked, in the API
    layer (see api/moderation.py).
    """

    # --- inputs ---
    content_text: str
    rules: list[RuleDTO]
    guardrail_injection_detected: bool
    reviewer_velocity: int  # only meaningful for reviews; unused for listings

    # Day 8: seller trust-score-adjusted thresholds. Optional — when
    # absent, aggregator_node falls back to the Aggregator's own base
    # constants (see graph/nodes.py), so the graph works identically
    # to before Day 8 for any caller that doesn't set these (e.g.
    # review moderation, which isn't attributed to a seller).
    reject_threshold: float
    approve_threshold: float

    # --- populated by individual agent nodes ---
    policy_verdict: PolicyAgentVerdict
    toxicity_verdict: ToxicityAgentVerdict
    fraud_verdict: FraudAgentVerdict  # only present in the review graph

    # --- populated by the aggregator node ---
    final_verdict: AggregatorVerdict


ItemType = Literal["listing", "review"]
