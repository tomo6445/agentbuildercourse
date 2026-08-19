"""The Observatory must render a real trace, not just a hand-made fixture."""

from agentcourse.trace import Trace

from .render import demo_trace, render


def test_renders_a_real_run():
    trace = demo_trace()
    html = render(trace)

    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    # every turn appears as a card
    assert html.count('class="turn ') == len(trace.turns)
    # the summary carries the numbers the course cares about
    for probe in ["outcome", "model turns", "tool calls", "input tokens",
                  "cache reads", "cost"]:
        assert probe in html
    # tool spans render with names and durations
    assert "get_weather" in html and "send_email" in html
    assert "stop: tool_use" in html and "stop: end_turn" in html


def test_renders_a_trace_loaded_from_disk(tmp_path):
    path = demo_trace().to_json(tmp_path / "t.json")
    html = render(Trace.from_json(path))
    assert "get_weather" in html


def test_is_self_contained():
    """No external CSS, JS, fonts or images: it must open from a file:// path."""
    html = render(demo_trace())
    for forbidden in ["http://", "https://", "<script", "<img"]:
        assert forbidden not in html, f"page reaches outside itself: {forbidden}"


def test_cli_writes_a_file(tmp_path):
    from .render import main
    out = tmp_path / "obs.html"
    assert main(["--demo", "-o", str(out)]) == 0
    assert out.exists() and out.stat().st_size > 2000
