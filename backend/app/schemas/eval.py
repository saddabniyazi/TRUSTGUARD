from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AgreementBreakdown(BaseModel):
    decision: str
    total_feedback: int
    agreements: int
    agreement_rate: float | None


class AgreementSummary(BaseModel):
    """
    Real-world moderator-agreement metric: of all the feedback
    moderators have submitted (Day 6's /api/feedback), how often did
    their human_decision match what the Aggregator actually decided?
    This is the production analogue of Day 4's offline adversarial-
    dataset script — that one measures the Fraud Agent against
    hand-labeled synthetic cases before deployment; this one measures
    the live Aggregator against real human judgment after deployment.
    Both matter, and they answer different questions.
    """

    total_feedback_entries: int
    overall_agreement_rate: float | None
    by_decision: list[AgreementBreakdown]


class EvalRunOut(BaseModel):
    """
    A persisted result from the offline full-pipeline harness
    (app/eval/run_full_eval.py) — precision/recall/F1 against the
    36-case adversarial dataset, computed through the real
    Policy+Toxicity+Fraud+Aggregator pipeline, not a single agent in
    isolation.
    """

    id: UUID
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
    per_category: dict
    created_at: datetime

    model_config = {"from_attributes": True}
