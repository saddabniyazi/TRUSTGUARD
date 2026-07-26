"""
Builds the moderation pipeline as LangGraph state machines.

Two separate compiled graphs — listing_graph (Policy + Toxicity) and
review_graph (Policy + Toxicity + Fraud) — rather than one graph with
conditional routing. LangGraph supports conditional edges, but for a
fan-out/fan-in pattern like this (multiple independent branches
converging on one aggregator node), making the fraud branch
conditional adds real complexity to reason about and to explain,
without adding any capability listings actually need. Two small,
easy-to-read graphs beat one graph with a routing function whose
behavior on edge cases has to be traced through carefully.

WHY THIS OVER THE PLAIN PYTHON CALLS FROM DAY 5: the previous version
of api/moderation.py called run_policy_agent(), then
run_toxicity_agent(), then run_fraud_agent() sequentially — three
Gemini calls, one after another. Independent nodes in a LangGraph
graph run CONCURRENTLY (verified: three 1-second nodes finish in ~1
second total here, not 3) — for a review, that's roughly a 3x latency
reduction on the slowest part of the whole moderation request, for
free, just by expressing the same three calls as a graph instead of
sequential statements.
"""

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import aggregator_node, fraud_node, policy_node, toxicity_node
from app.graph.state import ModerationState


def _build_listing_graph():
    graph = StateGraph(ModerationState)
    graph.add_node("policy", policy_node)
    graph.add_node("toxicity", toxicity_node)
    graph.add_node("aggregator", aggregator_node)

    graph.add_edge(START, "policy")
    graph.add_edge(START, "toxicity")
    graph.add_edge("policy", "aggregator")
    graph.add_edge("toxicity", "aggregator")
    graph.add_edge("aggregator", END)

    return graph.compile()


def _build_review_graph():
    graph = StateGraph(ModerationState)
    graph.add_node("policy", policy_node)
    graph.add_node("toxicity", toxicity_node)
    graph.add_node("fraud", fraud_node)
    graph.add_node("aggregator", aggregator_node)

    graph.add_edge(START, "policy")
    graph.add_edge(START, "toxicity")
    graph.add_edge(START, "fraud")
    graph.add_edge("policy", "aggregator")
    graph.add_edge("toxicity", "aggregator")
    graph.add_edge("fraud", "aggregator")
    graph.add_edge("aggregator", END)

    return graph.compile()


# Compiled once at import time — compilation validates the graph
# structure (no missing nodes, no cycles), so a build-time error here
# beats a request-time surprise.
listing_graph = _build_listing_graph()
review_graph = _build_review_graph()
