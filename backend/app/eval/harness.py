"""
Full-pipeline evaluation harness.

Day 4 built an adversarial dataset and a script that tested the Fraud
Agent alone. This tests the WHOLE system — Policy + Toxicity + Fraud +
the real Day-2 guardrail + the Day-5 Aggregator, exactly as a real
listing/review would be moderated — against every labeled case in the
dataset, and reports precision/recall instead of a plain pass/fail
count.

WHY PRECISION/RECALL AND NOT JUST "ACCURACY": this system has three
possible outputs (approve / reject / escalate), but the ground-truth
labels in the dataset are binary (should this have been blocked, or
not). Escalation is a deliberate, valid "I'm not sure" outcome (see
aggregator.py) — it would be wrong to count an escalated case as
either a hit or a miss against a binary label, since the system
correctly declined to guess. So metrics here are computed only over
DECIDED cases (auto_approve / auto_reject); escalated cases are
reported separately as an escalation rate, not folded into accuracy
in either direction. This is the standard, honest way to evaluate a
classifier with an abstain option — folding abstentions into either
side of the metric would misrepresent what the system actually did.

Ground truth: a case counts as "should be blocked" if EITHER
expected_policy_violation OR expected_is_fake is True (either signal
is a real reason to not approve the content).

This calls the real Gemini API — running all 36 cases costs 36 sets
of Policy+Toxicity+Fraud calls (~108 requests) unless the response-
level cache (Day 9's app/core/cache.py) already has them from a prior
run. On the free tier's tightest quota (5 req/min), a full run can take
several minutes; see run_full_eval.py's pacing.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents.fraud_agent import run_fraud_agent
from app.agents.policy_agent import run_policy_agent
from app.agents.toxicity_agent import run_toxicity_agent
from app.agents.aggregator import run_aggregator
from app.agents.dto import RuleDTO
from app.core.llm_client import AgentCallError
from app.db.models import PolicyRule
from app.eval.adversarial_dataset import ADVERSARIAL_DATASET, AdversarialCase
from app.guardrails.sanitizer import run_guardrail


@dataclass
class CaseOutcome:
    case_id: str
    category: str
    expected_violation: bool
    decision: str
    correct: bool | None  # None for escalated cases — not scored either way
    error: str | None = None


@dataclass
class EvalReport:
    total_cases: int
    escalated_count: int
    error_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float | None
    recall: float | None
    f1: float | None
    accuracy_on_decided: float | None
    per_category: dict[str, dict] = field(default_factory=dict)
    outcomes: list[CaseOutcome] = field(default_factory=list)


def _active_rule_dtos(db: Session) -> list[RuleDTO]:
    rows = db.query(PolicyRule).filter(PolicyRule.active.is_(True)).all()
    return [RuleDTO(category=r.category, rule_text=r.rule_text) for r in rows]


def _is_ground_truth_violation(case: AdversarialCase) -> bool:
    return bool(case.expected_policy_violation) or bool(case.expected_is_fake)


def _evaluate_case(db: Session, case: AdversarialCase, rules: list[RuleDTO]) -> CaseOutcome:
    expected_violation = _is_ground_truth_violation(case)

    try:
        guardrail_report = run_guardrail(case.text)
        policy_verdict = run_policy_agent(case.text, rules)
        toxicity_verdict = run_toxicity_agent(case.text)
        fraud_verdict = run_fraud_agent(case.text, case.reviewer_recent_review_count)

        result = run_aggregator(
            policy=policy_verdict,
            toxicity=toxicity_verdict,
            fraud=fraud_verdict,
            guardrail_injection_detected=guardrail_report.injection_detected,
        )
    except AgentCallError as exc:
        return CaseOutcome(
            case_id=case.id, category=case.category, expected_violation=expected_violation,
            decision="error", correct=None, error=str(exc),
        )

    if result.decision == "escalate_to_human":
        correct = None
    elif result.decision == "auto_reject":
        correct = expected_violation is True
    else:  # auto_approve
        correct = expected_violation is False

    return CaseOutcome(
        case_id=case.id, category=case.category, expected_violation=expected_violation,
        decision=result.decision, correct=correct,
    )


def run_full_eval(
    db: Session,
    dataset: list[AdversarialCase] | None = None,
    delay_between_cases: float = 0.0,
    on_case_complete=None,
) -> EvalReport:
    """
    delay_between_cases: seconds to sleep after each case (each case is
    3 Gemini calls — Policy, Toxicity, Fraud). Defaults to 0 for tests
    with mocked agents; run_full_eval.py sets this to a real value to
    respect the free tier's rate limit.
    on_case_complete: optional callback(index, total, outcome) for a
    CLI script to print progress — this function stays silent (no
    prints) so it's usable identically from a test.
    """
    import time

    cases = dataset if dataset is not None else ADVERSARIAL_DATASET
    rules = _active_rule_dtos(db)

    outcomes: list[CaseOutcome] = []
    for i, case in enumerate(cases):
        outcome = _evaluate_case(db, case, rules)
        outcomes.append(outcome)
        if on_case_complete is not None:
            on_case_complete(i + 1, len(cases), outcome)
        if delay_between_cases > 0 and i < len(cases) - 1:
            time.sleep(delay_between_cases)

    tp = fp = fn = tn = 0
    escalated = 0
    errors = 0

    for o in outcomes:
        if o.decision == "error":
            errors += 1
            continue
        if o.decision == "escalate_to_human":
            escalated += 1
            continue
        if o.decision == "auto_reject" and o.expected_violation:
            tp += 1
        elif o.decision == "auto_reject" and not o.expected_violation:
            fp += 1
        elif o.decision == "auto_approve" and o.expected_violation:
            fn += 1
        elif o.decision == "auto_approve" and not o.expected_violation:
            tn += 1

    decided = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) > 0 else None
    accuracy = (tp + tn) / decided if decided > 0 else None

    per_category: dict[str, dict] = {}
    categories = sorted({o.category for o in outcomes})
    for cat in categories:
        cat_outcomes = [o for o in outcomes if o.category == cat]
        scored = [o for o in cat_outcomes if o.correct is not None]
        per_category[cat] = {
            "total": len(cat_outcomes),
            "escalated": sum(1 for o in cat_outcomes if o.decision == "escalate_to_human"),
            "errors": sum(1 for o in cat_outcomes if o.decision == "error"),
            "correct": sum(1 for o in scored if o.correct),
            "scored": len(scored),
        }

    return EvalReport(
        total_cases=len(cases),
        escalated_count=escalated,
        error_count=errors,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy_on_decided=accuracy,
        per_category=per_category,
        outcomes=outcomes,
    )
