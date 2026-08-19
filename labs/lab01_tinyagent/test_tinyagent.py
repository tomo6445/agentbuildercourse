"""
The Lab 1 ship gate: twelve assertions.

Each one is a bug that shows up in real hand-written loops. Run with:

    pytest labs/lab01_tinyagent -q
"""

import pytest

from agentcourse import (
    Budget, ScriptedModel, ToolError, ToolRegistry, call, parallel, paused,
    say, tool, truncated,
)
from agentcourse.trace import Trace

from .tinyagent import run

# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


@tool
def get_weather(city: str) -> str:
    """Get current weather conditions for a city.

    Use this whenever the user asks about weather, temperature or conditions
    right now. Returns temperature in Celsius and a one-word sky description.

    Args:
        city: City name, e.g. 'Oslo'.
    """
    return f"{city}: 4C, light rain"


@tool
def crm_lookup(customer_id: str) -> str:
    """Look up a customer record by internal id.

    Use this after crm_search has given you a customer_id. Returns the
    customer's name, plan and status.

    Args:
        customer_id: The internal id returned by crm_search.
    """
    raise ToolError(
        "The CRM is unavailable for scheduled maintenance until 14:00 UTC. "
        "No lookup will succeed this session — report this and stop retrying."
    )


@tool
def divide(numerator: float, denominator: float) -> str:
    """Divide two numbers.

    Args:
        numerator: The number to divide.
        denominator: The number to divide by. Must not be zero.
    """
    return str(numerator / denominator)


@pytest.fixture
def registry():
    return ToolRegistry(get_weather, crm_lookup, divide)


# --------------------------------------------------------------------------
# 1-3: the basic round trip
# --------------------------------------------------------------------------


def test_01_single_turn_no_tools(registry):
    """A turn that stops with end_turn returns its text and exits immediately."""
    model = ScriptedModel([say("Hello. I have no tools to use here.")])
    result = run(model, registry, "hi")

    assert result.outcome == "ok"
    assert result.turns == 1
    assert "no tools" in result.output


def test_02_full_round_trip(registry):
    """user -> tool_use -> your executor -> tool_result -> end_turn."""
    model = ScriptedModel([
        call("get_weather", city="Oslo"),
        say("It is 4C and raining in Oslo."),
    ])
    result = run(model, registry, "weather in Oslo?")

    assert result.outcome == "ok"
    assert result.tools_called == ["get_weather"]
    assert "4C" in result.output
    # user, assistant(tool_use), user(tool_result) -> assistant(end_turn)
    assert len(result.messages) == 4
    assert result.messages[1]["role"] == "assistant"
    assert result.messages[2]["role"] == "user"


def test_03_assistant_turn_returned_verbatim(registry):
    """The assistant turn goes back as the API returned it, tool_use included.

    Re-serialising it by hand is a common shortcut that loses thinking blocks
    and breaks continuation on the real API.
    """
    model = ScriptedModel([call("get_weather", city="Oslo"), say("done")])
    result = run(model, registry, "weather?")

    assistant_turn = result.messages[1]["content"]
    assert isinstance(assistant_turn, list)
    assert any(getattr(b, "type", None) == "tool_use" for b in assistant_turn)


# --------------------------------------------------------------------------
# 4-5: parallel tool use
# --------------------------------------------------------------------------


def test_04_parallel_tool_calls_all_execute(registry):
    """Two tool_use blocks in ONE turn must both run.

    A loop that handles only content[0], or breaks after the first tool_use,
    passes every single-tool test and fails here.
    """
    model = ScriptedModel([
        parallel(("get_weather", {"city": "Oslo"}), ("get_weather", {"city": "Lisbon"})),
        say("Oslo 4C, Lisbon 4C."),
    ])
    result = run(model, registry, "weather in Oslo and Lisbon?")

    assert result.tools_called == ["get_weather", "get_weather"]
    assert result.turns == 2


def test_05_parallel_results_in_a_single_message(registry):
    """All tool_results go back in one user message, each with a matching id.

    Splitting them across messages is accepted by the API and quietly trains the
    model to stop making parallel calls.
    """
    model = ScriptedModel([
        parallel(("get_weather", {"city": "Oslo"}), ("get_weather", {"city": "Lisbon"})),
        say("done"),
    ])
    result = run(model, registry, "both please")

    tool_messages = [m for m in result.messages
                     if m["role"] == "user" and isinstance(m["content"], list)]
    assert len(tool_messages) == 1, "results were split across messages"

    blocks = tool_messages[0]["content"]
    assert len(blocks) == 2
    assert all(b["type"] == "tool_result" for b in blocks)

    requested = [b.id for b in result.messages[1]["content"] if b.type == "tool_use"]
    assert [b["tool_use_id"] for b in blocks] == requested, "ids do not match"


# --------------------------------------------------------------------------
# 6-8: errors are results, not exceptions
# --------------------------------------------------------------------------


def test_06_unknown_tool_is_handled_gracefully(registry):
    """A hallucinated tool name is ordinary model output. Your code rejects it.

    The error must also say what IS available, or the model retries identically.
    """
    model = ScriptedModel([
        call("get_forecast", city="Oslo"),
        say("I can only get current conditions, not a forecast."),
    ])
    result = run(model, registry, "10-day forecast?")

    assert result.outcome == "ok", "an unknown tool must not end the run"
    blocks = result.messages[2]["content"]
    assert blocks[0]["is_error"] is True
    assert "get_weather" in blocks[0]["content"], "error should list available tools"


def test_07_tool_exception_becomes_a_result(registry):
    """A raising tool returns is_error, it does not propagate out of the loop."""
    model = ScriptedModel([
        call("divide", numerator=1, denominator=0),
        say("That division is undefined."),
    ])
    result = run(model, registry, "1/0?")

    assert result.outcome == "ok"
    blocks = result.messages[2]["content"]
    assert blocks[0]["is_error"] is True
    assert "ZeroDivisionError" in blocks[0]["content"]


def test_08_malformed_arguments_become_a_result(registry):
    """Wrong arguments are the model's mistake to recover from, not a crash."""
    model = ScriptedModel([
        call("get_weather", town="Oslo"),        # wrong parameter name
        say("Let me try that again."),
    ])
    result = run(model, registry, "weather?")

    assert result.outcome == "ok"
    blocks = result.messages[2]["content"]
    assert blocks[0]["is_error"] is True
    assert "city" in blocks[0]["content"], "the error should show the expected schema"


# --------------------------------------------------------------------------
# 9-10: termination
# --------------------------------------------------------------------------


def test_09_terminates_under_a_permanently_failing_tool(registry):
    """The tool never recovers and the model never gives up. The cap must."""
    model = ScriptedModel([call("crm_lookup", customer_id="5512")], loop_forever=True)
    result = run(model, registry, "look up customer 5512",
                 budget=Budget(max_turns=5, max_usd=10.0))

    assert result.outcome == "turn_cap"
    assert result.turns == 5, "the cap must stop the loop exactly, not eventually"
    assert "turn cap" in result.detail


def test_10_budget_cap_stops_the_loop(registry):
    """Turns are a proxy; dollars are the real limit. A tiny budget stops early."""
    model = ScriptedModel([call("get_weather", city="Oslo")], loop_forever=True)
    result = run(model, registry, "weather",
                 budget=Budget(max_turns=100, max_usd=0.0005))

    assert result.outcome == "budget"
    assert result.turns < 100
    assert "budget" in result.detail


# --------------------------------------------------------------------------
# 11-12: stop reasons and the trace
# --------------------------------------------------------------------------


def test_11_stop_reasons_are_handled_by_reason_not_by_blocks(registry):
    """max_tokens is a truncation, not an answer; pause_turn resumes."""
    truncating = ScriptedModel([truncated("The three main causes are: first, the")])
    result = run(truncating, registry, "explain")
    assert result.outcome == "truncated", "a truncated response must not read as success"

    pausing = ScriptedModel([paused(), say("Finished after resuming.")])
    resumed = run(pausing, registry, "search the web")
    assert resumed.outcome == "ok"
    assert resumed.turns == 2, "pause_turn should resume rather than terminate"


def test_12_emits_a_renderable_trace(tmp_path, registry):
    """The Observatory reads this. Turn records, stop reasons, tokens, cost."""
    model = ScriptedModel([
        parallel(("get_weather", {"city": "Oslo"}), ("get_weather", {"city": "Lisbon"})),
        say("Oslo 4C, Lisbon 4C."),
    ])
    result = run(model, registry, "weather in both?")
    trace = result.trace

    assert trace.outcome == "ok"
    assert trace.model_turns == 2
    assert trace.total_input_tokens > 0
    assert trace.total_usd > 0
    assert [t.stop_reason for t in trace.turns if t.role == "assistant"] == \
        ["tool_use", "end_turn"]
    assert len(trace.tool_spans) == 2
    assert all(s.ok for s in trace.tool_spans)

    path = trace.to_json(tmp_path / "trace.json")
    assert Trace.from_json(path).model_turns == 2, "trace must round-trip through JSON"
