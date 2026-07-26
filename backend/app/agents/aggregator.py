"""
Aggregator / Judge.

Reconciles the Policy, Toxicity, and (for reviews) Fraud agent
verdicts into one final decision: auto_approve, auto_reject, or
escalate_to_human.

DELIBERATE DESIGN CHOICE: this is plain Python, not another LLM call.
By the time execution reaches here, three agents have already done the
judgment-heavy work of reading unstructured content and producing
structured, confidence-scored verdicts. Reconciling those verdicts
into a final decision is a business-rules problem, and business rules
should be deterministic, auditable, fast, and free to run, not
delegated to another model call. It's also why the Aggregator can be
trusted to be consistent: the same three input verdicts always produce
the same final decision.

WHY THERE'S NO "PICK A WINNER" DISAGREEMENT LOGIC: Policy, Toxicity,
and Fraud each evaluate a different, largely non-overlapping concern —
a listing can be policy-violating without being toxic; a review can be
fraudulent without violating any policy rule. Because the agents don't
usually make competing claims about the *same* fact, there's rarely a
genuine "Agent A says yes, Agent B says no" conflict to referee. So the
Aggregator doesn't try to weigh one agent's opinion against another's.
Instead, it does two simpler, more defensible things:

1. Any single agent flagging a violation at high confidence is enough
   to reject — a policy violation doesn't need toxicity to agree with
   it to be real.
2. The actual hard problem is CONFIDENCE, not consensus: if no agent
   is confident (in either direction), the system doesn't guess — it
   escalates. This is where "reconciling uncertain signals" actually
   happens in this system, and it's the honest answer to "how do you
   handle disagreement": by not forcing a decision when the evidence
   doesn't clearly support one.

CONFIDENCE CALIBRATION: the two thresholds below are the "how much do
we trust the agents" knob for the whole system:

- REJECT_CONFIDENCE_THRESHOLD is intentionally LOWER than
  APPROVE_CONFIDENCE_THRESHOLD. This is asymmetric on purpose: the
  cost of wrongly approving a bad listing/review (real user harm,
  regulatory/brand risk) is higher than the cost of escalating a
  borderline-fine one to a human (a few seconds of moderator time).
  When in doubt, the system leans toward caution, not throughput.
- Auto-approval requires EVERY agent that ran is both clean and
  confident — a single uncertain "looks fine" is enough to block
  auto-approval and send the item to a human instead.

DAY 8 ADDITION — trust-aware thresholds are now parameters, not just
module constants: `run_aggregator` accepts optional `reject_threshold`
and `approve_threshold` overrides. This is how the seller trust-score
system (app/agents/trust.py) plugs in without touching this file's
core logic at all — a low-trust seller's listings get a *lower*
reject threshold (easier to reject) and *higher* approve threshold
(harder to approve) computed elsewhere, then passed in here. The
Aggregator itself stays exactly as deterministic and single-purpose as
before; it just no longer assumes the thresholds are always the same
two numbers.
"""

from app.agents.schemas import (
    AggregatorVerdict,
    FraudAgentVerdict,
    PolicyAgentVerdict,
    ToxicityAgentVerdict,
)

# Base thresholds — used as-is unless a caller (e.g. the trust-score
# system) passes adjusted ones. See module docstring for why these two
# specific values, and why reject is lower than approve.
REJECT_CONFIDENCE_THRESHOLD = 0.75
APPROVE_CONFIDENCE_THRESHOLD = 0.80

# System-manipulation (prompt injection) is zero-tolerance: it doesn't
# go through the normal confidence gate at all.
_INJECTION_OVERRIDE_CATEGORY = "system_manipulation"


def _violation_signals(
    policy: PolicyAgentVerdict,
    toxicity: ToxicityAgentVerdict,
    fraud: FraudAgentVerdict | None,
    guardrail_injection_detected: bool,
) -> list[tuple[str, bool, float, str]]:
    """
    Returns a normalized list of (agent_name, flagged_violation, confidence, detail)
    across all agents that actually ran, so the rest of the aggregator
    doesn't need agent-specific branching.
    """
    signals: list[tuple[str, bool, float, str]] = [
        ("policy", not policy.compliant, policy.confidence, ", ".join(policy.violated_categories) or "compliant"),
        ("toxicity", toxicity.is_toxic or toxicity.is_spam, toxicity.confidence,
         "toxic" if toxicity.is_toxic else ("spam" if toxicity.is_spam else "clean")),
    ]
    if fraud is not None:
        signals.append(("fraud", fraud.is_likely_fake, fraud.confidence,
                         ", ".join(fraud.fraud_indicators) or "no fraud indicators"))
    if guardrail_injection_detected:
        signals.append(("guardrail", True, 1.0, "prompt-injection pattern matched at ingestion"))
    return signals


def run_aggregator(
    policy: PolicyAgentVerdict,
    toxicity: ToxicityAgentVerdict,
    fraud: FraudAgentVerdict | None = None,
    guardrail_injection_detected: bool = False,
    reject_threshold: float = REJECT_CONFIDENCE_THRESHOLD,
    approve_threshold: float = APPROVE_CONFIDENCE_THRESHOLD,
) -> AggregatorVerdict:
    signals = _violation_signals(policy, toxicity, fraud, guardrail_injection_detected)

    # --- Zero-tolerance override: system manipulation ---
    if _INJECTION_OVERRIDE_CATEGORY in policy.violated_categories or guardrail_injection_detected:
        return AggregatorVerdict(
            decision="auto_reject",
            confidence=1.0,
            reasoning=(
                "Content attempted to manipulate the moderation system directly "
                "(prompt injection). Rejected regardless of any other signal, "
                "since the content itself is misbehaving independent of whether "
                "the underlying product/review would otherwise be fine."
            ),
            contributing_signals=[
                f"{name}: {detail} (confidence={conf:.2f})" for name, flagged, conf, detail in signals if flagged
            ],
        )

    violating = [(name, conf, detail) for name, flagged, conf, detail in signals if flagged]
    clean = [(name, conf, detail) for name, flagged, conf, detail in signals if not flagged]
    high_confidence_violations = [v for v in violating if v[1] >= reject_threshold]

    # Rule 1: any single agent confidently flagging a violation is enough
    # to reject. Agents check different concerns, so another agent being
    # clean on ITS concern doesn't contradict this one being violated.
    if high_confidence_violations:
        return AggregatorVerdict(
            decision="auto_reject",
            confidence=max(v[1] for v in high_confidence_violations),
            reasoning=(
                "At least one agent flagged a violation with high confidence. "
                "Auto-rejected without requiring agreement from the other "
                "agents, since each evaluates a distinct concern."
            ),
            contributing_signals=[f"{name}: {detail} (confidence={conf:.2f})" for name, conf, detail in violating],
        )

    # Rule 2: no violations at all, and every agent that ran is
    # confidently clean -> auto-approve.
    if not violating and clean and all(conf >= approve_threshold for _, conf, _ in clean):
        return AggregatorVerdict(
            decision="auto_approve",
            confidence=min(conf for _, conf, _ in clean),
            reasoning="All agents that evaluated this content found no violations, each with high confidence.",
            contributing_signals=[f"{name}: {detail} (confidence={conf:.2f})" for name, conf, detail in clean],
        )

    # Rule 3: everything else — low-confidence violations, low-confidence
    # clean readings, or any mix that doesn't clearly clear the approve
    # or reject bar. This is where genuine uncertainty gets resolved: not
    # by picking a side, but by asking a human.
    all_confidences = [conf for _, flagged, conf, _ in signals]
    return AggregatorVerdict(
        decision="escalate_to_human",
        confidence=min(all_confidences) if all_confidences else 0.0,
        reasoning=(
            "No agent confidently flagged a violation, but at least one "
            "verdict fell below the confidence bar required for auto-approval. "
            "Escalating rather than guessing."
        ),
        contributing_signals=[f"{name}: {detail} (confidence={conf:.2f})" for name, flagged, conf, detail in signals],
    )
