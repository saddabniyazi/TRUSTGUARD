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

DAY 9 ADDITION: each node now checks app/core/cache.py before calling
its agent, and writes the result back on a miss. This is the other
half of protecting the free-tier Gemini quota (rate limiting on the
API layer is the first half) — re-moderating identical content, or two
different listings that happen to share text, costs zero additional
Gemini calls. See cache.py's docstring for why the cache key is a hash
of the actual inputs rather than any item ID.
"""

import hashlib

from app.agents.aggregator import run_aggregator
from app.agents.fraud_agent import run_fraud_agent
from app.agents.policy_agent import run_policy_agent
from app.agents.schemas import FraudAgentVerdict, PolicyAgentVerdict, ToxicityAgentVerdict
from app.agents.toxicity_agent import run_toxicity_agent
from app.core.cache import get_cached, set_cached
from app.graph.state import ModerationState


def _rules_hash(rules) -> str:
    """
    A stable hash of the active rule set, so the Policy cache key
    changes if rules are added/edited/deactivated — otherwise a rule
    change would silently be invisible to already-cached content.
    """
    joined = "|".join(sorted(f"{r.category}:{r.rule_text}" for r in rules))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def policy_node(state: ModerationState) -> dict:
    content_text = state["content_text"]
    rules = state["rules"]
    rules_key = _rules_hash(rules)

    cached = get_cached("policy", PolicyAgentVerdict, content_text, rules_key)
    if cached is not None:
        return {"policy_verdict": cached}

    verdict = run_policy_agent(content_text, rules)
    set_cached("policy", verdict, content_text, rules_key)
    return {"policy_verdict": verdict}


def toxicity_node(state: ModerationState) -> dict:
    content_text = state["content_text"]

    cached = get_cached("toxicity", ToxicityAgentVerdict, content_text)
    if cached is not None:
        return {"toxicity_verdict": cached}

    verdict = run_toxicity_agent(content_text)
    set_cached("toxicity", verdict, content_text)
    return {"toxicity_verdict": verdict}


def fraud_node(state: ModerationState) -> dict:
    content_text = state["content_text"]
    velocity = state["reviewer_velocity"]
    # Velocity is part of the cache key: the same review text with a
    # different velocity signal is a genuinely different input to the
    # Fraud Agent (see fraud_agent.py) and must not share a cache entry.
    velocity_key = str(velocity)

    cached = get_cached("fraud", FraudAgentVerdict, content_text, velocity_key)
    if cached is not None:
        return {"fraud_verdict": cached}

    verdict = run_fraud_agent(content_text, velocity)
    set_cached("fraud", verdict, content_text, velocity_key)
    return {"fraud_verdict": verdict}


def aggregator_node(state: ModerationState) -> dict:
    # Day 8: use trust-adjusted thresholds when the caller provided
    # them (see agents/trust.py); otherwise run_aggregator's own
    # defaults apply, identical to pre-Day-8 behavior.
    # Not cached: it's plain Python (Day 5's whole design point), so
    # there's no LLM quota to protect and re-running it is free.
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
