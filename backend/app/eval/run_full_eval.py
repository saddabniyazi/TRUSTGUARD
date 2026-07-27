"""
Runs the full moderation pipeline (Policy + Toxicity + Fraud +
guardrail + Aggregator — the real thing, not an agent in isolation)
against every case in the adversarial dataset, prints a precision/
recall report, and persists it as an EvalRun row.

This costs real Gemini quota: 36 cases x 3 agent calls = up to 108
requests (fewer if the Day-9 response cache already has some of them
from a prior run). Paced conservatively for the free tier's tightest
observed limit (5 requests/minute) — see SECONDS_BETWEEN_CASES below.
At that pace, a full run takes roughly 25-30 minutes. If your project
has a higher quota (check the RPM in any 429 error message, or
https://ai.dev/rate-limit), lower the constant.

Usage:
    python -m app.eval.run_full_eval
"""

from app.db.session import SessionLocal
from app.eval.harness import run_full_eval

# 3 calls/case at this pace keeps the average under ~4 req/min with
# margin — conservative on purpose since a 429 mid-run wastes the
# quota it already spent getting partway through a case's 3 calls.
SECONDS_BETWEEN_CASES = 45


def _print_progress(index: int, total: int, outcome) -> None:
    marker = {"escalate_to_human": "ESCALATED", "error": "ERROR"}.get(outcome.decision, "")
    if not marker:
        marker = "CORRECT" if outcome.correct else "WRONG"
    print(f"[{index}/{total}] {outcome.case_id} ({outcome.category}): {outcome.decision} — {marker}")


def run() -> None:
    db = SessionLocal()
    try:
        from app.eval.adversarial_dataset import ADVERSARIAL_DATASET

        estimated_minutes = (len(ADVERSARIAL_DATASET) * SECONDS_BETWEEN_CASES) / 60
        print(
            f"Running full-pipeline eval against {len(ADVERSARIAL_DATASET)} cases "
            f"(~{estimated_minutes:.0f} min at current pacing)...\n"
        )

        report = run_full_eval(db, delay_between_cases=SECONDS_BETWEEN_CASES, on_case_complete=_print_progress)

        print("\n--- Report ---")
        print(f"Total cases: {report.total_cases}")
        print(f"Escalated (not scored): {report.escalated_count}")
        print(f"Errors: {report.error_count}")
        print(f"TP={report.true_positives} FP={report.false_positives} "
              f"FN={report.false_negatives} TN={report.true_negatives}")
        print(f"Precision: {report.precision:.3f}" if report.precision is not None else "Precision: n/a")
        print(f"Recall:    {report.recall:.3f}" if report.recall is not None else "Recall: n/a")
        print(f"F1:        {report.f1:.3f}" if report.f1 is not None else "F1: n/a")
        print(f"Accuracy (decided only): {report.accuracy_on_decided:.3f}" if report.accuracy_on_decided is not None else "Accuracy: n/a")

        print("\nBy category:")
        for cat, stats in report.per_category.items():
            print(f"  {cat}: {stats['correct']}/{stats['scored']} correct, "
                  f"{stats['escalated']} escalated, {stats['errors']} errors")

        from app.db.models import EvalRun

        eval_run = EvalRun(
            total_cases=report.total_cases,
            escalated_count=report.escalated_count,
            error_count=report.error_count,
            true_positives=report.true_positives,
            false_positives=report.false_positives,
            false_negatives=report.false_negatives,
            true_negatives=report.true_negatives,
            precision=report.precision,
            recall=report.recall,
            f1=report.f1,
            accuracy_on_decided=report.accuracy_on_decided,
            per_category_json=report.per_category,
        )
        db.add(eval_run)
        db.commit()
        print(f"\nSaved as EvalRun {eval_run.id} — view it via GET /api/eval/runs/latest")
    finally:
        db.close()


if __name__ == "__main__":
    run()
