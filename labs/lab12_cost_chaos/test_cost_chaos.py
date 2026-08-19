"""
The Lab 12 gate: cut cost 60% within 3 points of accuracy, pass the chaos
suite at 95% completion, and survive a mid-task deployment.
"""

import random

import pytest

from agentcourse.cost import project

from .levers import BASELINE_ACCURACY, LEVERS, Config, apply, report
from .reliability import (
    BudgetBlown, CircuitBreaker, Down, FaultProxy, backoff_delay, resilient_call,
    run_chaos,
)


# ------------------------------------------------------------------- cost

def test_history_grows_quadratically_with_turn_count():
    """The fact that reorders every optimisation you might attempt."""
    ten = project(tasks_per_day=1, turns_per_task=10, stable_prefix_tokens=5000,
                  growth_per_turn=1500, output_per_turn=300, cached=True)
    twenty = project(tasks_per_day=1, turns_per_task=20, stable_prefix_tokens=5000,
                     growth_per_turn=1500, output_per_turn=300, cached=True)
    ratio = twenty["terms"]["resent_history"] / ten["terms"]["resent_history"]
    assert 3.5 < ratio < 4.5, f"doubling turns should ~quadruple history, got {ratio:.1f}x"


def test_the_dominant_term_is_resent_history():
    assert Config().cost()["dominant_term"] == "resent_history"


def test_caching_is_free_accuracy_wise_and_should_always_be_first():
    base = Config()
    cached = apply(base, ["caching"])
    r = report(base, cached)
    assert r["reduction"] > 0.15
    assert r["accuracy_drop"] == 0.0


def test_gate_sixty_percent_cut_within_three_points_of_accuracy():
    base = Config()
    tuned = apply(base, ["caching", "consolidate_tools", "shape_returns"])
    r = report(base, tuned)
    assert r["reduction"] >= 0.60, f"only cut {r['reduction']:.0%}"
    assert r["accuracy_drop"] <= 0.03, f"lost {r['accuracy_drop']:.1%} of accuracy"


def test_cost_cannot_be_bought_with_accuracy():
    """Dropping to the cheapest model hits the cost target and fails the gate."""
    base = Config()
    reckless = Config(model="claude-haiku-4-5", caching=True, subagents=0,
                      turns_per_task=6, growth_per_turn=500)
    r = report(base, reckless)
    assert r["reduction"] >= 0.60, "it is certainly cheap"
    assert r["accuracy_drop"] > 0.03, "and it must fail the accuracy tolerance"


def test_every_lever_actually_reduces_cost():
    base = Config()
    for name, lever in LEVERS.items():
        assert lever(base).cost()["per_task"] < base.cost()["per_task"], name


# ------------------------------------------------------------ reliability

def test_jitter_spreads_retries_instead_of_recreating_the_spike():
    """Without jitter, 200 clients that failed together retry together."""
    rng = random.Random(1)
    delays = [backoff_delay(2, rng=rng) for _ in range(200)]
    assert len(set(delays)) > 150, "delays must not cluster"
    assert max(delays) <= 4.0 and min(delays) >= 0.0


def test_backoff_grows_and_is_capped():
    rng = random.Random(2)
    early = max(backoff_delay(0, rng=rng) for _ in range(200))
    late = max(backoff_delay(8, rng=rng, cap=60) for _ in range(200))
    assert late > early
    assert backoff_delay(30, rng=rng, cap=60) <= 60


def test_circuit_breaker_opens_and_half_opens():
    breaker = CircuitBreaker(threshold=3, recovery_s=30)
    assert breaker.allow(now=0)
    for _ in range(3):
        breaker.record(False, now=0)
    assert breaker.state == "open"
    assert not breaker.allow(now=10), "still open inside the recovery window"
    assert breaker.allow(now=40), "half-open after recovery"
    breaker.record(True, now=41)
    assert breaker.state == "closed"


def test_a_hard_down_dependency_trips_the_breaker_rather_than_thrashing():
    r = run_chaos(tasks=50, error_rate=1.0)
    assert r["completion_rate"] == 0.0
    assert r["aborts"].get("circuit breaker", 0) > 0, (
        "retrying a hard-down dependency is load you generate against yourself"
    )
    assert r["mean_attempts"] < 8, "the breaker must bound the attempts"


def test_budget_guard_stops_a_run_regardless_of_what_retries_think():
    proxy = FaultProxy(error_rate=1.0)
    breaker = CircuitBreaker(threshold=99)          # deliberately never opens
    spent = [1] * 20
    result = resilient_call(proxy, breaker, budget_attempts=20, spent=spent)
    assert not result.completed
    assert result.aborted_by == "budget guard"


def test_gate_chaos_suite_reaches_95_percent_completion():
    for kwargs in ({"timeout_rate": 0.2}, {"error_rate": 0.25},
                   {"malformed_rate": 0.15},
                   {"timeout_rate": 0.15, "error_rate": 0.15, "malformed_rate": 0.1}):
        r = run_chaos(tasks=100, **kwargs)
        assert r["completion_rate"] >= 0.95, (kwargs, r)


def test_malformed_payloads_are_treated_as_failures_not_successes():
    proxy = FaultProxy(malformed_rate=1.0)
    result = resilient_call(proxy, CircuitBreaker(), max_attempts=3)
    assert not result.completed, "a malformed payload is not a result"


# ------------------------------------------- surviving a deploy mid-task

def test_in_flight_tasks_survive_a_rainbow_deployment(tmp_path):
    """A rolling deploy is invisible for a stateless service and a mass
    cancellation for a fleet of agents. Old versions must finish their work."""
    from lab05_sdk_port.harness import Session

    old_version_tasks = []
    for i in range(5):
        s = Session(f"task-{i}", task="long running")
        s.turn = 12
        s.messages = [{"role": "user", "content": "x"}] * 12
        s.save(tmp_path)
        old_version_tasks.append(s.session_id)

    # Deploy: new tasks go to v2; existing sessions keep running on v1.
    resumed = [Session.load(tmp_path, sid) for sid in old_version_tasks]
    assert all(s.turn == 12 for s in resumed), "in-flight work was lost"

    # Both versions must read the same session format for this to be possible.
    for s in resumed:
        s.turn += 1
        s.save(tmp_path)
    assert all(Session.load(tmp_path, sid).turn == 13 for sid in old_version_tasks)
