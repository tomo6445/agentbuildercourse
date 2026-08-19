"""
The Lab 10 gate: all three broken agents correctly root-caused from traces
alone, and the waterfall attributes cost accurately.
"""

import pytest

from agentcourse.trace import ToolSpan, Trace, TurnRecord

from .diagnose import (
    BROKEN, EXPECTED, TAXONOMY, arg_hash, diagnose, privacy_safe_view, waterfall,
)


@pytest.mark.parametrize("name", list(BROKEN))
def test_each_broken_agent_is_root_caused_from_the_trace_alone(name):
    d = diagnose(BROKEN[name]())
    assert d.failure_class == EXPECTED[name], d.evidence
    assert d.failure_class in TAXONOMY
    assert d.evidence, "a diagnosis without evidence is a guess"


def test_a_healthy_trace_is_not_diagnosed_with_something():
    """A classifier that always finds a failure is not a classifier."""
    healthy = Trace(task="look up the customer and send the summary")
    healthy.add(TurnRecord(index=0, role="assistant", stop_reason="tool_use",
                           context_tokens=9_000,
                           tool_spans=[ToolSpan("crm_search", {"q": "acme"}, 90, True, 640)]))
    healthy.add(TurnRecord(index=1, role="assistant", stop_reason="end_turn",
                           context_tokens=11_000,
                           tool_spans=[ToolSpan("send_summary", {"to": "acme"}, 80, True, 120)]))
    assert diagnose(healthy.finish("ok")).failure_class == "no_failure_detected"


def test_oscillation_is_detectable_without_reading_arguments():
    """The whole privacy-preserving posture in one assertion."""
    trace = BROKEN["B"]()
    view = privacy_safe_view(trace)

    blob = str(view)
    assert "A1" not in blob, "argument contents leaked into the trace view"
    assert "sku" not in blob

    hashes = [t["args_hash"] for turn in view for t in turn["tools"]]
    assert len(hashes) != len(set(hashes)), (
        "repeated hashes are what make oscillation visible with no contents"
    )


def test_arg_hash_is_stable_and_order_independent():
    assert arg_hash({"a": 1, "b": 2}) == arg_hash({"b": 2, "a": 1})
    assert arg_hash({"a": 1}) != arg_hash({"a": 2})


def test_privacy_safe_view_keeps_what_diagnosis_needs():
    view = privacy_safe_view(BROKEN["C"]())
    first = view[0]
    for field in ("stop_reason", "input_tokens", "output_tokens",
                  "cache_read_tokens", "usd", "tools"):
        assert field in first
    assert first["tools"][0]["bytes"] == 16000, "result size must survive"


def test_waterfall_attributes_cost_to_subagents():
    lead = Trace(task="research the vendor landscape", agent="lead")
    lead.add(TurnRecord(index=0, role="assistant", usd=0.02, input_tokens=9000))
    lead.finish("ok")

    workers = []
    for i in range(3):
        w = Trace(task=f"sub-question {i}", agent=f"worker-{i}", parent_id=lead.trace_id)
        w.add(TurnRecord(index=0, role="assistant", usd=0.05, input_tokens=42_000))
        workers.append(w.finish("ok"))

    rows = waterfall(lead, workers)
    assert len(rows) == 4
    assert all(r["parent"] == lead.trace_id for r in rows[1:])
    assert sum(r["usd"] for r in rows) == pytest.approx(0.17)
    assert sum(r["share"] for r in rows) == pytest.approx(1.0, abs=0.01)
    # The lead is the cheap part. That is the M9 arithmetic showing up in a UI.
    assert rows[0]["share"] < 0.2


def test_traces_round_trip_so_they_can_be_replayed(tmp_path):
    """A trace you cannot replay from is a log."""
    original = BROKEN["A"]()
    path = original.to_json(tmp_path / "t.json")
    restored = Trace.from_json(path)
    assert diagnose(restored).failure_class == diagnose(original).failure_class
