from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import EvalRun, ModeratorFeedback, User, Verdict
from app.db.session import get_db
from app.schemas.eval import AgreementBreakdown, AgreementSummary, EvalRunOut

router = APIRouter(prefix="/api/eval", tags=["evaluation"])

_ALL_DECISIONS = ["auto_approve", "auto_reject", "escalate_to_human"]


def _eval_run_to_out(run: EvalRun) -> EvalRunOut:
    return EvalRunOut(
        id=run.id,
        total_cases=run.total_cases,
        escalated_count=run.escalated_count,
        error_count=run.error_count,
        true_positives=run.true_positives,
        false_positives=run.false_positives,
        false_negatives=run.false_negatives,
        true_negatives=run.true_negatives,
        precision=float(run.precision) if run.precision is not None else None,
        recall=float(run.recall) if run.recall is not None else None,
        f1=float(run.f1) if run.f1 is not None else None,
        accuracy_on_decided=float(run.accuracy_on_decided) if run.accuracy_on_decided is not None else None,
        per_category=run.per_category_json,
        created_at=run.created_at,
    )


@router.get("/agreement", response_model=AgreementSummary)
def get_agreement_summary(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> AgreementSummary:
    """
    Computes the real, live moderator-agreement rate: joins every
    ModeratorFeedback entry (Day 6) to the Verdict it was submitted
    against, and measures how often feedback.human_decision matched
    verdict.decision — both overall and broken down per decision type
    (e.g. "when the Aggregator auto-rejected, how often did the human
    agree it should have been rejected?"). This is computed fresh on
    every call rather than cached/persisted, since it's a simple query
    over a table that's expected to stay small enough for that to be
    fine at this project's scale — a real production system would
    materialize this on a schedule instead of recomputing per request.
    """
    rows = (
        db.query(ModeratorFeedback.human_decision, Verdict.decision)
        .join(Verdict, ModeratorFeedback.verdict_id == Verdict.id)
        .all()
    )

    total = len(rows)
    overall_agreements = sum(1 for human, system in rows if human == system)
    overall_rate = (overall_agreements / total) if total > 0 else None

    breakdown: list[AgreementBreakdown] = []
    for decision in _ALL_DECISIONS:
        subset = [(human, system) for human, system in rows if system == decision]
        subset_total = len(subset)
        subset_agreements = sum(1 for human, system in subset if human == system)
        breakdown.append(
            AgreementBreakdown(
                decision=decision,
                total_feedback=subset_total,
                agreements=subset_agreements,
                agreement_rate=(subset_agreements / subset_total) if subset_total > 0 else None,
            )
        )

    return AgreementSummary(
        total_feedback_entries=total,
        overall_agreement_rate=overall_rate,
        by_decision=breakdown,
    )


@router.get("/runs", response_model=list[EvalRunOut])
def list_eval_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[EvalRunOut]:
    """History of offline harness runs, newest first — lets a trend be tracked across runs, not just the latest number."""
    runs = db.query(EvalRun).order_by(EvalRun.created_at.desc()).limit(min(limit, 100)).all()
    return [_eval_run_to_out(r) for r in runs]


@router.get("/runs/latest", response_model=EvalRunOut)
def get_latest_eval_run(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> EvalRunOut:
    run = db.query(EvalRun).order_by(EvalRun.created_at.desc()).first()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No eval runs yet — run `python -m app.eval.run_full_eval` first.",
        )
    return _eval_run_to_out(run)
