from dataclasses import dataclass


@dataclass
class RuleDTO:
    """
    Plain-data stand-in for a PolicyRule row. Graph state should never
    hold live SQLAlchemy ORM objects tied to a request-scoped DB
    session — LangGraph runs independent nodes concurrently (see
    pipeline.py), and a shared session isn't safe to touch from
    multiple threads at once. Rules are fetched from the DB once,
    converted to this plain dataclass, and only then handed to the
    graph — nodes never see the DB session at all.

    Duck-typed to match what app/agents/policy_agent.py._format_rules
    actually reads (.category, .rule_text), so the same formatting
    function works whether it's given real PolicyRule rows or these.
    """

    category: str
    rule_text: str
