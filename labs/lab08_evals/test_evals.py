"""
The Lab 8 gate: the judge clears the agreement threshold, and the suite catches
all three injected regressions.
"""

import pytest

from agentcourse.evals import cohens_kappa

from .judge import FIXED_RUBRIC, NAIVE_RUBRIC, OUTPUTS, Rubric, run_validation
from .regressions import AGENTS, evaluate


# ------------------------------------------------------------------- judge

def test_raw_agreement_is_the_number_that_lies():
    """A judge that passes everything scores well on a mostly-passing set."""
    human = [o.human_label for o in OUTPUTS]
    always_pass = [1] * len(human)
    agreement = sum(h == j for h, j in zip(human, always_pass)) / len(human)
    assert agreement >= 0.5, "raw agreement looks respectable"
    assert cohens_kappa(human, always_pass) == 0.0, "kappa is not fooled"


def test_the_naive_rubric_fails_validation():
    r = run_validation(NAIVE_RUBRIC)
    assert not r["usable"], "if this passes, the lab has nothing to teach"
    assert r["kappa"] < 0.6
    flagged = {oid for oid, _ in r["disagreements"]}
    assert "o03" in flagged, "junk source should slip past a rubric that ignores it"
    assert "o04" in flagged, "abstention should be punished until it is rewarded"


def test_fixing_the_rubric_fixes_the_judge():
    r = run_validation(FIXED_RUBRIC)
    assert r["usable"] and r["kappa"] >= 0.6
    assert r["disagreements"] == []


def test_the_reference_labels_are_never_the_thing_you_change():
    """Adjusting labels to match the judge produces a suite that agrees with
    itself and nothing else. Guard the labels explicitly."""
    expected = [1, 0, 0, 1, 0, 1, 0, 1]
    assert [o.human_label for o in OUTPUTS] == expected, (
        "the reference labels changed — if a judge disagrees, fix the rubric"
    )


def test_source_quality_must_be_scored_explicitly():
    """Judges do not invent standards you did not write down."""
    without = run_validation(Rubric(source_quality=False, reward_abstention=True,
                                    length_independent=True))
    assert any(oid == "o03" for oid, _ in without["disagreements"])


# -------------------------------------------------------------- regressions

def test_healthy_agent_passes_its_own_suite():
    report = evaluate("healthy")
    assert report.pass_rate == 1.0, report.failures_by_reason


@pytest.mark.parametrize("name", ["trajectory", "cost", "abstention"])
def test_suite_catches_each_injected_regression(name):
    report = evaluate(name)
    assert report.pass_rate < 1.0, f"the {name} regression shipped undetected"


def test_trajectory_regression_is_invisible_to_outcome_only_evals():
    """The agent that succeeded by luck and will fail tomorrow."""
    report = evaluate("trajectory")
    reasons = report.failures_by_reason
    assert "trajectory" in reasons
    assert "outcome" not in reasons, (
        "every answer is still correct — only the route changed, which is "
        "precisely why outcome-only evaluation certifies this agent as fine"
    )


def test_cost_regression_is_invisible_to_accuracy_only_reporting():
    report = evaluate("cost")
    assert "budget" in report.failures_by_reason
    healthy = evaluate("healthy")
    assert report.mean_turns > healthy.mean_turns * 3


def test_reports_use_pass_rates_because_agents_are_stochastic():
    report = evaluate("healthy", repeats=5)
    assert len(report.results) == 15
    assert report.rate_for_case("c1") == 1.0
    assert report.rate_for_tier("hard") == 1.0
    assert report.turn_variance >= 0
