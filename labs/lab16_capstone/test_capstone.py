"""The checklist has to actually catch the things it claims to catch."""

import json

import pytest

from .checklist import STAGES, check_cost_gate, check_decisions, check_eval_first, run


@pytest.fixture
def project(tmp_path):
    (tmp_path / "evals").mkdir()
    (tmp_path / "decisions").mkdir()
    (tmp_path / "agent").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    return tmp_path


def good_cases(n=30):
    cases = []
    for i in range(n):
        tier = ("easy", "realistic", "hard")[i % 3]
        cases.append({"id": f"c{i}", "prompt": "q", "tier": tier,
                      "must_call": ["lookup"], "must_contain": ["x"]})
    cases[0]["must_contain"] = ["not available"]
    return cases


def test_the_stage_weights_sum_to_one():
    assert sum(w for _, _, w, _ in STAGES) == pytest.approx(1.0)


def test_an_empty_project_reports_every_stage_outstanding(tmp_path):
    results, blockers = run(tmp_path)
    assert all(not r.complete for r in results)
    assert any("cost ceiling" in b for b in blockers)


def test_eval_suite_must_be_committed_before_the_agent(project):
    (project / "agent" / "main.py").write_text("# the agent\n")
    _, blockers = run(project)
    assert any("BEFORE the agent" in b for b in blockers), (
        "the ordering rule is the whole point of stage 2"
    )


def test_thirty_cases_across_three_tiers_are_required(project):
    (project / "evals" / "cases.json").write_text(json.dumps(good_cases(12)))
    notes = check_eval_first(project)
    assert any("at least 30" in n for n in notes)

    (project / "evals" / "cases.json").write_text(
        json.dumps([{"id": "c", "tier": "easy", "must_call": ["x"],
                     "must_contain": ["not available"]}] * 30))
    notes = check_eval_first(project)
    assert any("all three are required" in n for n in notes)


def test_trajectory_assertions_and_abstention_are_required(project):
    outcome_only = [{"id": f"c{i}", "tier": ("easy", "realistic", "hard")[i % 3],
                     "must_contain": ["x"]} for i in range(30)]
    (project / "evals" / "cases.json").write_text(json.dumps(outcome_only))
    notes = check_eval_first(project)
    assert any("trajectory assertions" in n for n in notes)
    assert any("abstention" in n for n in notes)


def test_a_judge_below_the_kappa_threshold_is_flagged(project):
    (project / "evals" / "cases.json").write_text(json.dumps(good_cases()))
    (project / "evals" / "judge_validation.json").write_text(
        json.dumps({"agreement": 0.84, "kappa": 0.31}))
    notes = check_eval_first(project)
    assert any("below 0.6" in n for n in notes)
    assert any("never the reference labels" in n for n in notes)


def test_decision_entries_need_the_reversal_field(project):
    (project / "decisions" / "001-autonomy.md").write_text(
        "# 001\n\n**Decision.** Single agent.\n\n**Alternatives considered.** "
        "Orchestrator.\n\n**Reason.** Cheaper.\n")
    notes = check_decisions(project)
    assert any("What would reverse this" in n for n in notes), (
        "the reversal field is what makes it a decision log rather than a "
        "justification"
    )


def test_the_cost_gate_must_be_enforced_in_ci(project):
    assert check_cost_gate(project), "no workflow yet"
    (project / ".github" / "workflows" / "ci.yml").write_text(
        "- run: python -m evals.run --max-usd-per-task 0.18\n")
    assert check_cost_gate(project) == []


def test_the_failure_demo_must_be_described(project):
    (project / "DEMO.md").write_text("Ten minute demo of the happy path.\n")
    results, _ = run(project)
    stage7 = next(r for r in results if r.number == "07")
    assert any("graceful-failure" in n for n in stage7.notes)

    (project / "DEMO.md").write_text(
        "Demo, then the graceful failure under a fault chosen by the panel.\n")
    results, _ = run(project)
    stage7 = next(r for r in results if r.number == "07")
    assert stage7.notes == []
