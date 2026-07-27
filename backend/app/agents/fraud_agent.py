"""
Fraud Pattern Agent.

Distinct from the Policy and Toxicity agents in one important way: it
doesn't judge the text in isolation. Fake-review detection is weak
signal from content alone (a well-written fake review reads exactly
like a genuine one) — it gets meaningfully stronger when combined with
*behavioral* signal: is this reviewer account posting an unusual
volume of reviews in a short window? That signal comes from a real DB
query (see api/agents.py), not from the LLM guessing at it.

This mirrors how real Trust & Safety fraud detection actually works:
content analysis is one input among several, not the whole picture.
"""

from app.agents.schemas import FraudAgentVerdict
from app.core.llm_client import generate_structured

_SYSTEM_INSTRUCTION = """You are a fraud analyst reviewing product
reviews for signs of inauthenticity — fake, incentivized, or
bot-generated reviews — as distinct from toxicity or policy violations
(those are handled by other reviewers; ignore them here).

Signals that indicate a likely-fake review:
- Generic praise that could apply to any product in any category, with
  no specific detail about this particular item, use case, or
  experience (e.g. "Great product, highly recommend!" and nothing else).
- Language admitting or implying compensation for the review (free
  product, discount, refund tied to leaving a positive rating).
- Unnatural phrasing suggestive of templated or bot-generated text —
  repeated stock phrases, keyword-stuffing product terms unnaturally.
- A disclosed high posting frequency signal (provided to you as a
  fact, not something to infer from the text) — treat a high recent
  review count from the same reviewer as raising suspicion, but not as
  proof by itself; a genuine frequent shopper can also leave several
  real reviews.

A genuine review is usually specific: it mentions a concrete detail
(fit, sound, taste, a flaw, a comparison, how it was used) that a
templated fake review typically wouldn't bother including. Do not
flag a review as fake merely for being short or positive — specificity
is what matters, not sentiment or length."""


def run_fraud_agent(review_text: str, reviewer_recent_review_count: int) -> FraudAgentVerdict:
    prompt = f"""Reviewer signal: this reviewer has posted {reviewer_recent_review_count} \
other review(s) in the last 24 hours (not counting this one).

Review text to evaluate:
\"\"\"
{review_text}
\"\"\"

Evaluate this review for signs of being fake or incentivized, and return your verdict."""

    return generate_structured(
        prompt=prompt,
        response_schema=FraudAgentVerdict,
        system_instruction=_SYSTEM_INSTRUCTION,
        agent_name="fraud",
    )
