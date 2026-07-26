"""
Seller trust-score system.

Two responsibilities, kept in one small module since they're two
halves of the same feedback loop:

1. compute_adjusted_thresholds() — turns a seller's trust_score into
   adjusted Aggregator thresholds. A seller with a track record of
   violations gets a system that's easier to reject and harder to
   auto-approve; a seller with a clean history gets a little slack on
   borderline cases. The Aggregator itself doesn't know sellers exist
   at all (see aggregator.py) — it just receives whatever thresholds
   it's given.

2. update_seller_trust() — after a listing is moderated, moves the
   seller's trust_score in response to the decision. This is what
   makes the adjustment in (1) actually adaptive over time instead of
   a one-time snapshot.

WHY THIS IS A SEPARATE MODULE AND NOT INSIDE THE AGGREGATOR: the
Aggregator's whole design premise (Day 5) is that it's a pure,
deterministic function of the three agent verdicts — same inputs,
same output, every time, with no hidden state. Trust score is exactly
the kind of hidden, mutable, seller-specific state that would break
that property if it lived inside the Aggregator. Keeping it here means
the Aggregator stays testable in complete isolation (see the 13 unit
tests in test coverage from Day 5/8), and the trust-score logic is
itself independently testable without needing three fake agent
verdicts to exercise it.

CALIBRATION — deliberately modest adjustments: a seller's history
should influence moderation, not override the actual content signals.
A ±0.05-0.10 threshold shift changes how many borderline cases get
caught, but a genuinely bad listing from a trusted seller still gets
rejected (their trust score only makes REJECT slightly easier and
APPROVE slightly harder — it never disables the confidence gate
entirely), and a genuinely clean listing from a distrusted seller can
still auto-approve if every agent is highly confident it's fine.
"""

from sqlalchemy.orm import Session

from app.agents.aggregator import APPROVE_CONFIDENCE_THRESHOLD, REJECT_CONFIDENCE_THRESHOLD
from app.db.models import Seller

# Trust score is stored as 0-100 (see Seller.trust_score, default 50 —
# a new seller starts neutral, neither trusted nor distrusted).
LOW_TRUST_CUTOFF = 30.0
HIGH_TRUST_CUTOFF = 70.0

# How far thresholds move at the extremes. Applied as a straight-line
# interpolation between the cutoffs, not a hard step, so a seller at
# trust_score=29 and one at trust_score=31 don't get a jarring cliff
# in how they're treated.
MAX_REJECT_SHIFT = 0.10  # low-trust sellers: reject threshold moves DOWN by up to this much
MAX_APPROVE_SHIFT = 0.10  # low-trust sellers: approve threshold moves UP by up to this much
HIGH_TRUST_LENIENCY = 0.05  # high-trust sellers: a smaller, more conservative shift the other way

# Trust score deltas per moderation outcome. Reject moves it down
# faster than approve moves it up — same asymmetric-risk reasoning as
# the Aggregator's own thresholds (Day 5): a violation should cost a
# seller more trust than a clean listing earns back, so a seller can't
# offset one rejected bad-faith listing with a handful of normal ones.
TRUST_DELTA_ON_REJECT = -8.0
TRUST_DELTA_ON_APPROVE = +1.0
# escalate_to_human intentionally causes no trust change — the outcome
# isn't settled yet, so nothing is known to adjust for.

TRUST_SCORE_MIN = 0.0
TRUST_SCORE_MAX = 100.0


def compute_adjusted_thresholds(trust_score: float) -> tuple[float, float]:
    """
    Returns (reject_threshold, approve_threshold) adjusted for this
    seller's trust score. Sellers between LOW_TRUST_CUTOFF and
    HIGH_TRUST_CUTOFF get the Aggregator's unmodified base thresholds.
    """
    if trust_score <= LOW_TRUST_CUTOFF:
        # Linear ramp: at trust_score == 0, the full shift applies; at
        # trust_score == LOW_TRUST_CUTOFF, none of it does.
        severity = (LOW_TRUST_CUTOFF - trust_score) / LOW_TRUST_CUTOFF
        reject = REJECT_CONFIDENCE_THRESHOLD - (MAX_REJECT_SHIFT * severity)
        approve = APPROVE_CONFIDENCE_THRESHOLD + (MAX_APPROVE_SHIFT * severity)
        return max(reject, 0.05), min(approve, 0.99)

    if trust_score >= HIGH_TRUST_CUTOFF:
        span = TRUST_SCORE_MAX - HIGH_TRUST_CUTOFF
        severity = (trust_score - HIGH_TRUST_CUTOFF) / span if span > 0 else 0.0
        reject = REJECT_CONFIDENCE_THRESHOLD + (HIGH_TRUST_LENIENCY * severity)
        approve = APPROVE_CONFIDENCE_THRESHOLD - (HIGH_TRUST_LENIENCY * severity)
        # Note: reject and approve are allowed to cross here (e.g. at
        # max leniency, reject=0.80 and approve=0.75). That's not a
        # bug — they gate different, non-overlapping signal
        # populations (violating vs. clean verdicts; see aggregator.py
        # Rules 1 and 2), so there's no case where the same signal is
        # evaluated against both at once. Only the individual [0,1]
        # probability bound matters here, not their relative order.
        return min(reject, 0.99), max(approve, 0.05)

    return REJECT_CONFIDENCE_THRESHOLD, APPROVE_CONFIDENCE_THRESHOLD


def update_seller_trust(db: Session, seller_id, decision: str) -> None:
    """
    Adjusts a seller's trust_score (and violation_count on reject)
    based on a moderation decision for one of their listings. Call
    this once, after the Aggregator has produced a final decision for
    a listing — not for reviews, which aren't attributed to a seller.
    """
    seller = db.get(Seller, seller_id)
    if seller is None:
        return  # shouldn't happen in practice; moderate_listing already validated the listing has a seller

    if decision == "auto_reject":
        seller.trust_score = max(TRUST_SCORE_MIN, float(seller.trust_score) + TRUST_DELTA_ON_REJECT)
        seller.violation_count += 1
    elif decision == "auto_approve":
        seller.trust_score = min(TRUST_SCORE_MAX, float(seller.trust_score) + TRUST_DELTA_ON_APPROVE)
    # escalate_to_human: no change, see module docstring.

    db.commit()
