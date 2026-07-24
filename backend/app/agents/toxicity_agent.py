"""
Toxicity / Spam Agent.

Separate from the Policy Compliance Agent on purpose: toxicity/spam
detection is a distinct judgment call (tone and intent of the language
itself) from policy-rule compliance (does the content match a specific
prohibited category). Keeping them as separate agents means the
Aggregator (Day 5) gets two independent signals instead of one agent
conflating "this breaks rule #7" with "this is also abusive."
"""

from app.agents.schemas import ToxicityAgentVerdict
from app.core.llm_client import generate_structured

_SYSTEM_INSTRUCTION = """You are a content moderation reviewer focused
specifically on toxicity and spam — not general policy compliance.

Toxicity: hate speech, slurs, harassment, threats, or content demeaning
a person or group.

Spam: promotional content unrelated to a genuine product/review,
off-platform contact solicitation, referral/discount schemes tied to
reviews, or repetitive low-effort text clearly aimed at gaming the
platform rather than informing a buyer.

Be specific in your reasoning: quote or closely paraphrase the exact
part of the content that drove your verdict. If the content is a
normal, genuine listing or review, say so plainly rather than
manufacturing a concern."""


def run_toxicity_agent(content_text: str) -> ToxicityAgentVerdict:
    prompt = f"""Content to review:
\"\"\"
{content_text}
\"\"\"

Evaluate the content for toxicity and spam and return your verdict."""

    return generate_structured(
        prompt=prompt,
        response_schema=ToxicityAgentVerdict,
        system_instruction=_SYSTEM_INSTRUCTION,
    )
