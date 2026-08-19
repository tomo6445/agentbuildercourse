"""
The Lab 3 ship gate: hold 90% of baseline accuracy at turn 60, under the
cost ceiling.
"""

import pytest

from .benchmark import baseline_accuracy, evaluate, quiz_keys
from .strategies import STRATEGIES, degradation

TURNS = 60
CEILING = 6.00


@pytest.fixture(scope="module")
def results():
    quiz = quiz_keys(TURNS, 12)
    return {name: evaluate(name, TURNS, quiz) for name in STRATEGIES}


@pytest.fixture(scope="module")
def target():
    return baseline_accuracy() * 0.90


def test_every_strategy_implements_the_interface():
    for name, cls in STRATEGIES.items():
        s = cls()
        assert hasattr(s, "observe") and hasattr(s, "retained_keys")
        assert hasattr(s, "context_tokens")
        assert s.name == name


def test_rot_is_a_gradient_not_a_cliff():
    """Recall falls away smoothly as occupancy rises. Nothing errors on the way."""
    curve = [degradation(int(f * 200_000)) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    assert curve == sorted(curve, reverse=True), "degradation must be monotonic"
    assert curve[0] == 1.0
    assert 0 < curve[-1] < 0.5
    assert len(set(curve)) > 2, "a cliff would only have two values"


def test_retaining_everything_is_not_recalling_everything(results, target):
    """The headline result: 'none' keeps every fact and still loses."""
    none = results["none"]
    assert none.recall == 1.0, "the naive strategy does retain every fact"
    assert none.accuracy < target, (
        "but at this occupancy it should not recall them — if this passes, the "
        "rot model is not doing anything and the lab teaches nothing"
    )


def test_strategies_meet_the_gate(results, target):
    for name in ("compaction", "notes", "subagent"):
        r = results[name]
        assert r.accuracy >= target, f"{name}: {r.accuracy:.0%} < {target:.0%}"
        assert r.usd <= CEILING, f"{name}: ${r.usd:.2f} over the ${CEILING:.2f} ceiling"


def test_the_naive_baseline_is_also_the_most_expensive(results):
    """Re-sending a growing transcript every turn is not a cheap default."""
    none = results["none"]
    for name in ("compaction", "notes", "subagent"):
        assert results[name].usd < none.usd


def test_subagent_isolation_costs_more_than_notes(results):
    """Context isolation is bought, not free — the M9 arithmetic in miniature.

    The orchestrator's window is the smallest of any strategy; the bill is not.
    """
    assert results["subagent"].context_tokens < results["notes"].context_tokens
    assert results["subagent"].usd > results["notes"].usd


def test_compaction_loses_facts_when_the_summary_budget_is_small():
    """The summarisation prompt IS the strategy: squeeze it and findings vanish
    with no error anywhere."""
    from .benchmark import workload
    tight = STRATEGIES["compaction"](summary_budget=100)
    for fact in workload(60):
        tight.observe(fact)
    assert len(tight.retained_keys()) < 60
