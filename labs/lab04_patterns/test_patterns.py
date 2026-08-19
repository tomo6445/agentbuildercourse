"""The Lab 4 gate: all implementations pass, and the comparison table is real."""

import pytest

from .compare import measure
from .patterns import PATTERNS, classify
from .tickets import TICKETS


@pytest.fixture(scope="module")
def table():
    return {name: measure(name) for name in PATTERNS}


def test_all_patterns_implemented():
    assert set(PATTERNS) == {
        "single_call", "prompt_chaining", "routing", "parallel_voting",
        "orchestrator_workers", "evaluator_optimiser", "autonomous_agent",
    }
    for name, fn in PATTERNS.items():
        d = fn(TICKETS[0])
        assert d.category in {"billing", "technical", "account", "abuse", "other"}
        assert d.calls >= 1 and d.input_tokens > 0


def test_eval_set_has_hard_cases():
    """A set of only clear-signal tickets makes every architecture look the same."""
    assert len(TICKETS) == 40
    ambiguous = [t for t in TICKETS if t.id.startswith("a")]
    unsignalled = [t for t in TICKETS if t.id.startswith("n")]
    assert len(ambiguous) >= 10 and len(unsignalled) >= 6


def test_the_careful_pass_is_actually_better():
    """If the expensive path is not more accurate, the exercise measures noise."""
    cheap = sum(classify(t.text)[0] == t.gold for t in TICKETS)
    careful = sum(classify(t.text, effort="careful")[0] == t.gold for t in TICKETS)
    assert careful > cheap


def test_every_pattern_beats_random(table):
    for name, row in table.items():
        assert row["accuracy"] > 0.5, f"{name} is no better than guessing"


def test_routing_matches_the_agent_far_more_cheaply(table):
    """The headline finding, and the point of the whole lab."""
    routing, agent = table["routing"], table["autonomous_agent"]
    assert routing["accuracy"] >= agent["accuracy"]
    assert routing["usd_per_1k"] < agent["usd_per_1k"] / 3
    assert routing["p95_ms"] < agent["p95_ms"]


def test_autonomy_costs_more_than_it_returns_here(table):
    """Not a claim about agents in general — a measurement on this task."""
    agent = table["autonomous_agent"]
    cheaper_and_as_good = [
        n for n, r in table.items()
        if r["usd_per_1k"] < agent["usd_per_1k"] and r["accuracy"] >= agent["accuracy"]
    ]
    assert cheaper_and_as_good, "if nothing beats the agent, the memo writes itself"


def test_evaluator_optimiser_terminates(table):
    """The loop must stop on a budget, not on satisfaction."""
    assert table["evaluator_optimiser"]["calls_per_ticket"] <= 7


def test_comparison_table_is_complete(table):
    for row in table.values():
        for column in ("accuracy", "escalation_accuracy", "calls_per_ticket",
                       "p50_ms", "p95_ms", "usd_per_1k", "loc"):
            assert column in row and row[column] is not None
