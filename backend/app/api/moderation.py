import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.dto import RuleDTO
from app.agents.schemas import AggregatorVerdict
from app.agents.signals import get_reviewer_velocity
from app.agents.trust import compute_adjusted_thresholds, update_seller_trust
from app.api.auth import get_current_user
from app.core.llm_client import AgentCallError
from app.db.models import Listing, PolicyRule, Review, Seller, User, Verdict
from app.db.session import get_db
from app.graph.pipeline import listing_graph, review_graph

router = APIRouter(prefix="/api/moderate", tags=["moderation"])

# Maps the Aggregator's decision straight onto content status.
_DECISION_TO_STATUS = {
    "auto_approve": "approved",
    "auto_reject": "rejected",
    "escalate_to_human": "escalated",
}


def _active_rule_dtos(db: Session) -> list[RuleDTO]:
    """
    Fetches active rules and converts them to plain RuleDTOs before
    they ever reach the graph — see app/agents/dto.py for why.
    """
    rows = db.query(PolicyRule).filter(PolicyRule.active.is_(True)).all()
    return [RuleDTO(category=r.category, rule_text=r.rule_text) for r in rows]


def _listing_thresholds(db: Session, seller_id) -> tuple[float, float]:
    """
    Day 8: looks up the listing's seller and returns trust-adjusted
    (reject_threshold, approve_threshold). Falls back to the
    Aggregator's own base thresholds if the seller can't be found
    (shouldn't happen — a listing's seller_id is a real FK — but
    moderation shouldn't hard-fail over a missing trust-score lookup).
    """
    seller = db.get(Seller, seller_id)
    if seller is None:
        from app.agents.aggregator import APPROVE_CONFIDENCE_THRESHOLD, REJECT_CONFIDENCE_THRESHOLD
        return REJECT_CONFIDENCE_THRESHOLD, APPROVE_CONFIDENCE_THRESHOLD
    return compute_adjusted_thresholds(float(seller.trust_score))


def _persist_verdict(db: Session, item_id: UUID, item_type: str, result: AggregatorVerdict, agent_scores: dict) -> Verdict:
    verdict = Verdict(
        item_id=item_id,
        item_type=item_type,
        decision=result.decision,
        confidence=result.confidence,
        rationale_json={"reasoning": result.reasoning, "contributing_signals": result.contributing_signals},
        agent_scores_json=agent_scores,
    )
    db.add(verdict)
    db.commit()
    db.refresh(verdict)
    return verdict


@router.post("/listing/{listing_id}", response_model=AggregatorVerdict)
def moderate_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> AggregatorVerdict:
    """
    Runs the full pipeline for a listing through the LangGraph
    listing_graph (Policy + Toxicity, run concurrently, converging on
    the Aggregator), persists the result as a Verdict row, and updates
    the listing's status. /api/agents/evaluate/* (Day 3) exists only
    for inspecting individual agents in isolation, without going
    through the graph or persisting anything.
    """
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    reject_threshold, approve_threshold = _listing_thresholds(db, listing.seller_id)
    initial_state = {
        "content_text": f"{listing.title}\n{listing.description}",
        "rules": _active_rule_dtos(db),
        "guardrail_injection_detected": listing.injection_detected,
        "reject_threshold": reject_threshold,
        "approve_threshold": approve_threshold,
    }

    try:
        final_state = listing_graph.invoke(initial_state)
    except AgentCallError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    result = final_state["final_verdict"]
    _persist_verdict(
        db, listing_id, "listing", result,
        agent_scores={
            "policy": final_state["policy_verdict"].model_dump(),
            "toxicity": final_state["toxicity_verdict"].model_dump(),
        },
    )
    listing.status = _DECISION_TO_STATUS[result.decision]
    db.commit()

    # Day 8: move the seller's trust score in response to this decision.
    # Deliberately after persisting the Verdict and updating status, not
    # before — trust should reflect a decision that's actually final and
    # recorded, not one that might still fail on the way to being saved.
    update_seller_trust(db, listing.seller_id, result.decision)

    return result


@router.post("/review/{review_id}", response_model=AggregatorVerdict)
def moderate_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> AggregatorVerdict:
    """Same as moderate_listing, but through review_graph (adds the Fraud node)."""
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    initial_state = {
        "content_text": review.text,
        "rules": _active_rule_dtos(db),
        "guardrail_injection_detected": review.injection_detected,
        "reviewer_velocity": get_reviewer_velocity(db, review.reviewer_name, review.id),
    }

    try:
        final_state = review_graph.invoke(initial_state)
    except AgentCallError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    result = final_state["final_verdict"]
    _persist_verdict(
        db, review_id, "review", result,
        agent_scores={
            "policy": final_state["policy_verdict"].model_dump(),
            "toxicity": final_state["toxicity_verdict"].model_dump(),
            "fraud": final_state["fraud_verdict"].model_dump(),
        },
    )
    review.status = _DECISION_TO_STATUS[result.decision]
    db.commit()

    return result


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _stream_pipeline(db: Session, graph, initial_state: dict, item_id: UUID, item_type: str, seller_id=None):
    """
    Shared generator for both streaming endpoints below. Runs the graph
    with stream_mode="updates" so each node's output is yielded the
    moment that node finishes — a caller watching this can render
    "Policy: done", "Fraud: done", etc. live, instead of waiting for
    the whole ~3-6s pipeline before seeing anything.

    Persistence happens once, after the aggregator node's update is
    seen — same as the non-streaming endpoints, just deferred until
    the graph actually reaches that point. seller_id, when provided
    (listings only — see stream_moderate_listing), triggers the same
    Day 8 trust-score update the non-streaming endpoint performs.
    """
    agent_scores: dict = {}
    final_result: AggregatorVerdict | None = None

    try:
        for update in graph.stream(initial_state, stream_mode="updates"):
            for node_name, node_output in update.items():
                if node_name == "aggregator":
                    final_result = node_output["final_verdict"]
                    yield _sse_event("aggregator", final_result.model_dump())
                else:
                    # policy_verdict / toxicity_verdict / fraud_verdict — one key each
                    verdict_key = next(iter(node_output))
                    verdict = node_output[verdict_key]
                    agent_scores[node_name] = verdict.model_dump()
                    yield _sse_event(node_name, verdict.model_dump())
    except AgentCallError as exc:
        yield _sse_event("error", {"detail": str(exc)})
        return

    if final_result is not None:
        _persist_verdict(db, item_id, item_type, final_result, agent_scores)
        model = db.get(Listing, item_id) if item_type == "listing" else db.get(Review, item_id)
        if model is not None:
            model.status = _DECISION_TO_STATUS[final_result.decision]
            db.commit()
        if seller_id is not None:
            update_seller_trust(db, seller_id, final_result.decision)

    yield _sse_event("done", {})


@router.get("/stream/listing/{listing_id}")
def stream_moderate_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Same pipeline as POST /listing/{id}, but streamed as Server-Sent
    Events — one event per agent as it completes, then a final
    "aggregator" event with the decision, then "done". This is what a
    real dashboard would connect to (via EventSource) to show live
    per-agent progress instead of a blank loading spinner for several
    seconds.
    """
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    reject_threshold, approve_threshold = _listing_thresholds(db, listing.seller_id)
    initial_state = {
        "content_text": f"{listing.title}\n{listing.description}",
        "rules": _active_rule_dtos(db),
        "guardrail_injection_detected": listing.injection_detected,
        "reject_threshold": reject_threshold,
        "approve_threshold": approve_threshold,
    }

    return StreamingResponse(
        _stream_pipeline(db, listing_graph, initial_state, listing_id, "listing", seller_id=listing.seller_id),
        media_type="text/event-stream",
    )


@router.get("/stream/review/{review_id}")
def stream_moderate_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    initial_state = {
        "content_text": review.text,
        "rules": _active_rule_dtos(db),
        "guardrail_injection_detected": review.injection_detected,
        "reviewer_velocity": get_reviewer_velocity(db, review.reviewer_name, review.id),
    }

    return StreamingResponse(
        _stream_pipeline(db, review_graph, initial_state, review_id, "review"),
        media_type="text/event-stream",
    )


def _serialize_verdicts(verdicts: list[Verdict]) -> list[dict]:
    return [
        {
            "id": str(v.id),
            "decision": v.decision,
            "confidence": float(v.confidence),
            "rationale": v.rationale_json,
            "agent_scores": v.agent_scores_json,
            "created_at": v.created_at.isoformat(),
        }
        for v in verdicts
    ]


@router.get("/listing/{listing_id}/verdicts", response_model=list[dict])
def get_listing_verdicts(
    listing_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[dict]:
    """History of every moderation run for this listing — re-moderation produces a new Verdict row, so this is an audit trail, not just the current status. Includes each agent's raw verdict (agent_scores) alongside the Aggregator's reconciled decision, so a UI can render the same per-agent breakdown for historical verdicts that it renders live during streaming."""
    verdicts = (
        db.query(Verdict)
        .filter(Verdict.item_id == listing_id, Verdict.item_type == "listing")
        .order_by(Verdict.created_at.desc())
        .all()
    )
    return _serialize_verdicts(verdicts)


@router.get("/review/{review_id}/verdicts", response_model=list[dict])
def get_review_verdicts(
    review_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Same as get_listing_verdicts, for reviews."""
    verdicts = (
        db.query(Verdict)
        .filter(Verdict.item_id == review_id, Verdict.item_type == "review")
        .order_by(Verdict.created_at.desc())
        .all()
    )
    return _serialize_verdicts(verdicts)
