"""
Runs the Fraud Agent against every fraud-labeled case in the
adversarial dataset and reports how many it got right.

This is deliberately lightweight — NOT the full evaluation harness
(Day 9 adds LLM-as-judge scoring, precision/recall, and persistence of
results over time). This script exists so the Fraud Agent built today
can actually be stress-tested today, instead of waiting until Day 9 to
find out it doesn't handle the coordinated-review case.

Rate limiting: the Gemini free tier is genuinely tight — as low as 5
requests per minute on some models/projects. This script paces itself
with a fixed delay between calls (SECONDS_BETWEEN_CALLS below) instead
of firing all 32 calls back to back and relying on llm_client's retry
logic to absorb a wall of 429s. Adjust the constant down if your
project's quota is higher (check the RPM shown in your 429 error
messages, or https://ai.dev/rate-limit for your project).

Usage (requires a real GEMINI_API_KEY in your .env):
    python -m app.eval.run_fraud_eval
"""

import time

from app.agents.fraud_agent import run_fraud_agent
from app.core.llm_client import AgentCallError
from app.eval.adversarial_dataset import ADVERSARIAL_DATASET

# 13 seconds keeps you under a 5-requests-per-minute quota with a small
# safety margin. If your key allows 10-15 RPM (check your error message
# or the AI Studio dashboard), you can safely lower this to 5-6.
SECONDS_BETWEEN_CALLS = 13


def run() -> None:
    cases = [c for c in ADVERSARIAL_DATASET if c.expected_is_fake is not None]
    estimated_minutes = (len(cases) * SECONDS_BETWEEN_CALLS) / 60
    print(
        f"Running Fraud Agent against {len(cases)} labeled cases "
        f"(paced at 1 call / {SECONDS_BETWEEN_CALLS}s — "
        f"~{estimated_minutes:.1f} min total)...\n"
    )

    correct = 0
    failures: list[str] = []

    for i, case in enumerate(cases):
        try:
            verdict = run_fraud_agent(case.text, case.reviewer_recent_review_count)
        except AgentCallError as exc:
            print(f"[{case.id}] AGENT CALL FAILED: {exc}")
            failures.append(case.id)
        else:
            is_correct = verdict.is_likely_fake == case.expected_is_fake
            correct += int(is_correct)
            status = "PASS" if is_correct else "FAIL"
            print(
                f"[{status}] {case.id} ({case.category}): "
                f"expected={case.expected_is_fake} got={verdict.is_likely_fake} "
                f"(confidence={verdict.confidence:.2f})"
            )
            if not is_correct:
                print(f"         reasoning: {verdict.reasoning}")
                failures.append(case.id)

        # Pace ourselves regardless of success/failure — no point racing
        # ahead into another 429 immediately after one.
        if i < len(cases) - 1:
            time.sleep(SECONDS_BETWEEN_CALLS)

    attempted = len(cases)
    print(f"\n{correct}/{attempted} correct ({correct / attempted:.0%})" if attempted else "No cases run.")
    if failures:
        print(f"Failed/errored cases: {', '.join(failures)}")


if __name__ == "__main__":
    run()
