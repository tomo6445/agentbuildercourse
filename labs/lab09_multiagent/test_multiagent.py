"""
The Lab 9 gate: beat the single-agent baseline on the rubric AND come in under
the cost-per-task ceiling. Quality alone is not a pass.
"""

import pytest

from .economics import TASK_VALUE_USD, measure, quality, single_agent_baseline
from .orchestrator import SUBQUESTIONS, Brief, effort_for, plan, run, synthesise

CEILING_USD = 0.60


# --------------------------------------------------------------- delegation

def test_scoping_stops_workers_duplicating_each_other():
    """The M9 autopsy: two subagents, same search, twice the bill.

    The fix is a line in the brief, not orchestration code.
    """
    scoped = run(workers=4, scoped=True)
    unscoped = run(workers=4, scoped=False)

    assert scoped["duplicate_searches"] == 0
    assert unscoped["duplicate_searches"] > 8, (
        "unscoped workers should each research everything"
    )
    assert len(unscoped["searches"]) > len(scoped["searches"]) * 3


def test_a_brief_names_what_other_workers_are_covering():
    brief = plan(SUBQUESTIONS, 3)[0]
    rendered = brief.render()
    assert "Do NOT investigate" in rendered
    assert "other workers are" in rendered
    assert "EFFORT:" in rendered and "OUTPUT:" in rendered
    assert "may not write or send" in rendered, "read-only workers, in configuration"


def test_worker_tools_are_restricted_in_configuration_not_by_request():
    for brief in plan(SUBQUESTIONS, 4):
        assert set(brief.tools) == {"search", "fetch_document"}
        assert "write_file" not in brief.tools and "send_email" not in brief.tools


def test_effort_scales_with_the_shape_of_the_task():
    """A fixed pool puts eight agents on a question one lookup answers."""
    assert effort_for("simple_fact") == 1
    assert effort_for("comparison") == 3
    assert effort_for("open_research") == 8
    assert effort_for("simple_fact") < effort_for("open_research")


# ---------------------------------------------------------------- synthesis

def test_citations_survive_synthesis():
    result = run(workers=4)
    assert result["citations"], "the lead dropped every attribution"
    assert "10-K" in result["citations"]


def test_conflicts_are_surfaced_not_averaged():
    """'Sources disagree' is a better answer than a confident average."""
    result = run(workers=4)
    revenue_conflict = [c for c in result["conflicts"] if c["subquestion"] == "revenue"]
    assert revenue_conflict, "the corpus disagrees about revenue and the lead hid it"
    assert "2.15B" in revenue_conflict[0]["disagreeing"].values()
    assert result["answer"]["revenue"] == "2.1B", "primary source should win"


def test_primary_sources_are_preferred_over_junk():
    """Without an explicit heuristic, agents drift to whatever is easiest to
    extract from — which is the content farm."""
    result = run(workers=4)
    assert "seo-roundup" not in result["citations"]


def test_a_failed_worker_degrades_the_answer_rather_than_killing_the_run():
    result = run(workers=4, failing_worker="margin")
    assert result["degraded"] == ["margin"]
    assert "revenue" in result["answer"], "the other workers still delivered"


# ---------------------------------------------------------------- economics

def test_the_quality_curve_has_a_knee():
    rows = [measure(w) for w in (1, 2, 3, 4, 6, 8)]
    marginals = [rows[i]["quality"] - rows[i - 1]["quality"] for i in range(1, len(rows))]
    assert marginals[0] > marginals[2], "quality must saturate, or there is no knee"
    assert marginals[-1] < 0.02, "the last worker should buy almost nothing"

    costs = [r["usd"] for r in rows]
    assert costs == sorted(costs), "cost must not saturate"


def test_multi_agent_beats_the_single_agent_baseline_on_quality():
    baseline = single_agent_baseline()
    best = measure(6)
    assert best["quality"] > baseline["quality"]


def test_and_costs_several_times_more(caplog):
    """Context isolation is bought, not free."""
    baseline = single_agent_baseline()
    assert measure(6)["usd"] > baseline["usd"] * 3


def test_gate_cost_per_task_ceiling():
    r = measure(4)
    assert r["usd"] <= CEILING_USD, f"${r['usd']:.3f} over the ceiling"
    assert r["usd"] < TASK_VALUE_USD * 0.25, "compute is eating the value"
