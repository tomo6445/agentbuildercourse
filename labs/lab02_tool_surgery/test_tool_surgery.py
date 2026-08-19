"""
The Lab 2 ship gate.

Two numbers, and they pull against each other: pass rate up, tokens down. You
cannot buy accuracy with a thousand-word description.
"""

import pytest

from .evalset import TASKS
from .harness import PASS_TARGET, evaluate, load


@pytest.fixture(scope="module")
def baseline():
    return evaluate(load("starter"))


@pytest.fixture(scope="module")
def mine():
    return evaluate(load("tools"))


def test_evalset_is_intact():
    """The eval set is frozen. If this fails, someone tuned the test."""
    assert len(TASKS) == 20
    assert len({t.id for t in TASKS}) == 20
    assert {t.expects_tool for t in TASKS} <= {
        "crm_search_customers", "crm_get_customer", "crm_list_tickets",
        "crm_add_note", "crm_update_ticket", "crm_get_billing",
        "crm_log_interaction",
    }


def test_the_harness_discriminates(baseline):
    """The flawed baseline must actually fail, or the exercise measures nothing."""
    assert baseline["pass_rate"] < 0.60
    assert "tool_misselection" in baseline["failures_by_class"]
    assert "error_thrash" in baseline["failures_by_class"]


def test_gate_pass_rate(mine):
    assert mine["pass_rate"] >= PASS_TARGET, (
        f"{mine['pass_rate']:.0%} < {PASS_TARGET:.0%}. Failures: "
        f"{mine['failures_by_class']}"
    )


def test_gate_token_reduction(mine, baseline):
    """Accuracy bought with tokens is not a fix."""
    assert mine["definition_tokens"] < baseline["definition_tokens"], (
        f"{mine['definition_tokens']:,} tokens is not below the baseline's "
        f"{baseline['definition_tokens']:,}"
    )


def test_rubric_closed_sets_have_enums():
    """Every closed-set parameter the eval set exercises must be an enum."""
    registry = load("tools")
    props = {t.name: t.input_schema["properties"] for t in registry}
    for task in TASKS:
        for param in task.closed_set_params:
            schema = props.get(task.expects_tool, {}).get(param)
            assert schema and schema.get("enum"), (
                f"{task.expects_tool}.{param} is a closed set with no enum"
            )


def test_rubric_every_parameter_is_described():
    registry = load("tools")
    for t in registry:
        for name, schema in t.input_schema["properties"].items():
            assert schema.get("description"), f"{t.name}.{name} has no description"


def test_rubric_descriptions_state_when_to_use():
    registry = load("tools")
    for t in registry:
        assert any(p in t.description.lower() for p in
                   ("use this", "use it when", "whenever")), (
            f"{t.name} never says when to reach for it"
        )


def test_rubric_failure_semantics_are_documented():
    """Empty is not an error; a permanent failure must say it is permanent."""
    registry = {t.name: t for t in load("tools")}
    search = registry["crm_search_customers"].description.lower()
    assert "empty" in search or "no match" in search

    billing = registry["crm_get_billing"].description.lower()
    assert any(p in billing for p in ("permanent", "stop retrying", "no call will succeed"))
