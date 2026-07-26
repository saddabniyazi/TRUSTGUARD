"""
Node functions for the moderation graph.

Each node is a thin wrapper: it reads what it needs from state and
returns a partial state update. All the actual logic lives in
app/agents/*.py, built Days 3-5 — this file exists only to adapt those
functions to LangGraph's node signature (state in, partial state
update out). This separation matters: the agents themselves have no
LangGraph dependency at all, so they're just as usable outside a graph
(e.g. Day 3's standalone /api/agents/evaluate/* endpoints call them
directly, no graph involved).
"""

from app.agents.aggregator import run_aggregator
from app.agents.fraud_agent import run_fraud_agent
from app.agents.policy_agent import run_policy_agent
from app.agents.toxicity_agent import run_toxicity_agent
from app.graph.state import ModerationState


def policy_node(state: ModerationState) -> dict:
    verdict = run_policy_agent(state["content_text"], state["rules"])
    return {"policy_verdict": verdict}


def toxicity_node(state: ModerationState) -> dict:
    verdict = run_toxicity_agent(state["content_text"])
    return {"toxicity_verdict": verdict}


def fraud_node(state: ModerationState) -> dict:
    verdict = run_fraud_agent(state["content_text"], state["reviewer_velocity"])
    return {"fraud_verdict": verdict}


def aggregator_node(state: ModerationState) -> dict:
    # Day 8: use trust-adjusted thresholds when the caller provided
    # them (see agents/trust.py); otherwise run_aggregator's own
    # defaults apply, identical to pre-Day-8 behavior.
    kwargs = {}
    if "reject_threshold" in state:
        kwargs["reject_threshold"] = state["reject_threshold"]
    if "approve_threshold" in state:
        kwargs["approve_threshold"] = state["approve_threshold"]

    verdict = run_aggregator(
        policy=state["policy_verdict"],
        toxicity=state["toxicity_verdict"],
        fraud=state.get("fraud_verdict"),
        guardrail_injection_detected=state["guardrail_injection_detected"],
        **kwargs,
    )
    return {"final_verdict": verdict}
