"""
Lab 1b — the Observatory.

Renders a trace JSON file to a standalone HTML page. You extend this in eleven
of the remaining fifteen modules, so the shape matters more than the styling:

    v0  (M1)   turn cards, tokens, cost, stop reasons, tool spans
    v1  (M3)   context occupancy timeline, cache-hit indicator
    v2  (M8)   side-by-side eval run comparison
    v3  (M10)  subagent waterfall with per-span cost
    v4  (M12)  cost attribution by tool, subagent and turn

Usage:

    python -m lab01b_observatory.render trace.json -o observatory.html
    python -m lab01b_observatory.render --demo -o observatory.html
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from agentcourse.trace import Trace

CSS = """
:root{--paper:#faf7f2;--paper2:#f2ece2;--ink:#1c1a17;--ink2:#5b554c;--ink3:#8a8377;
--rule:#ddd5c8;--rust:#a8452c;--teal:#1f5f5b;--gold:#8a6d1f;
--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;--serif:Georgia,serif}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 -apple-system,
Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 24px 70px}
h1{font-family:var(--serif);font-weight:400;font-size:30px;margin:0 0 6px}
.sub{font-family:var(--mono);font-size:11.5px;color:var(--ink3);letter-spacing:.06em;
text-transform:uppercase;margin-bottom:20px}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
border-top:1px solid var(--rule);border-left:1px solid var(--rule);margin-bottom:26px}
.summary div{padding:11px 13px;border-right:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.summary b{display:block;font-family:var(--mono);font-size:18px;font-weight:500}
.summary span{font-family:var(--mono);font-size:10px;letter-spacing:.1em;
text-transform:uppercase;color:var(--ink3)}
.summary .bad b{color:var(--rust)}
.summary .good b{color:var(--teal)}
.turn{border:1px solid var(--rule);border-left-width:3px;background:#fff;margin-bottom:10px}
.turn.assistant{border-left-color:var(--ink)}
.turn.tool_result{border-left-color:var(--gold)}
.turn.error{border-left-color:var(--rust)}
.turn header{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;padding:9px 13px;
border-bottom:1px solid var(--rule);background:var(--paper2);font-family:var(--mono);font-size:11px}
.turn header b{background:var(--ink);color:var(--paper);padding:2px 6px;font-weight:600}
.turn.tool_result header b{background:var(--gold)}
.turn header em{font-style:normal;color:var(--ink3)}
.turn header .stop{margin-left:auto;color:var(--rust)}
.turn .body{padding:11px 13px}
.blk{font-family:var(--mono);font-size:11.5px;background:var(--paper);border:1px solid var(--rule);
padding:7px 9px;margin-bottom:6px;white-space:pre-wrap;word-break:break-word;color:var(--ink2)}
.blk:last-child{margin-bottom:0}
.span{display:flex;gap:10px;align-items:center;font-family:var(--mono);font-size:11px;
padding:5px 9px;border:1px solid var(--rule);margin-bottom:5px;background:var(--paper)}
.span.err{border-color:var(--rust);background:#f7ece8}
.span .nm{font-weight:600;color:var(--ink)}
.span .ms{margin-left:auto;color:var(--ink3)}
.occ{display:flex;height:14px;border:1px solid var(--rule);margin-top:8px}
.occ i{display:block;height:100%}
.legend{font-family:var(--mono);font-size:10px;color:var(--ink3);margin-top:4px}
.cache{font-family:var(--mono);font-size:10px;padding:2px 6px;border:1px solid var(--rule)}
.cache.hit{background:#dce9e7;border-color:var(--teal);color:var(--teal)}
.cache.miss{background:#f0e0d9;border-color:var(--rust);color:var(--rust)}
footer{font-family:var(--mono);font-size:11px;color:var(--ink3);margin-top:30px;
border-top:1px solid var(--rule);padding-top:14px}
"""


def render(trace: Trace, title: str = "Observatory") -> str:
    """Render a trace to a self-contained HTML page."""
    outcome_tone = "good" if trace.outcome == "ok" else "bad"
    cache_total = sum(t.cache_read_tokens for t in trace.turns)

    cards = []
    for turn in trace.turns:
        cls = turn.role
        if any(b.get("is_error") for b in turn.blocks if isinstance(b, dict)):
            cls += " error"

        header = [f"<b>{html.escape(turn.role)}</b>",
                  f"<em>turn {turn.index}</em>"]
        if turn.input_tokens or turn.output_tokens:
            header.append(
                f"<em>{turn.input_tokens:,} in / {turn.output_tokens:,} out</em>")
        if turn.usd:
            header.append(f"<em>${turn.usd:.5f}</em>")
        if turn.latency_ms:
            header.append(f"<em>{turn.latency_ms:.0f}ms</em>")
        if turn.role == "assistant":
            cls_cache = "hit" if turn.cache_read_tokens else "miss"
            header.append(
                f'<span class="cache {cls_cache}">cache '
                f'{turn.cache_read_tokens:,}</span>')
        if turn.stop_reason:
            header.append(f'<span class="stop">stop: {turn.stop_reason}</span>')

        body = []
        for block in turn.blocks:
            body.append(f'<div class="blk">{html.escape(json.dumps(block, default=str))}</div>')
        for span in turn.tool_spans:
            err = "" if span.ok else " err"
            detail = html.escape(json.dumps(span.arguments, default=str))[:160]
            body.append(
                f'<div class="span{err}"><span class="nm">{html.escape(span.name)}</span>'
                f"<span>{detail}</span>"
                f'<span class="ms">{span.duration_ms:.0f}ms · {span.result_bytes}B'
                f'{" · ERROR" if not span.ok else ""}</span></div>'
            )

        # Context occupancy (v1, M3). Absent on a v0 trace, and that is fine.
        if turn.occupancy:
            total = sum(turn.occupancy.values()) or 1
            colours = {"system": "#1f5f5b", "tools": "#8a6d1f",
                       "history": "#a8452c", "results": "#c98a72"}
            bars = "".join(
                f'<i style="width:{v / total * 100:.1f}%;'
                f'background:{colours.get(k, "#8a8377")}"></i>'
                for k, v in turn.occupancy.items()
            )
            legend = " · ".join(f"{k} {v:,}" for k, v in turn.occupancy.items())
            body.append(f'<div class="occ">{bars}</div><div class="legend">{legend}</div>')

        cards.append(
            f'<article class="turn {cls}"><header>{"".join(header)}</header>'
            f'<div class="body">{"".join(body) or "<em>no blocks</em>"}</div></article>'
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — {html.escape(trace.trace_id)}</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>{html.escape(trace.task[:110])}</h1>
<div class="sub">{html.escape(trace.agent)} · trace {html.escape(trace.trace_id)}
{" · parent " + html.escape(trace.parent_id) if trace.parent_id else ""}</div>
<div class="summary">
  <div class="{outcome_tone}"><b>{html.escape(trace.outcome)}</b><span>outcome</span></div>
  <div><b>{trace.model_turns}</b><span>model turns</span></div>
  <div><b>{len(trace.tool_spans)}</b><span>tool calls</span></div>
  <div><b>{trace.total_input_tokens:,}</b><span>input tokens</span></div>
  <div><b>{trace.total_output_tokens:,}</b><span>output tokens</span></div>
  <div class="{'good' if cache_total else ''}"><b>{cache_total:,}</b><span>cache reads</span></div>
  <div><b>${trace.total_usd:.5f}</b><span>cost</span></div>
  <div><b>{trace.duration_ms:.0f}ms</b><span>wall clock</span></div>
</div>
{"".join(cards)}
<footer>{html.escape(trace.outcome_detail or "completed normally")}
{"<br>repeated tool signatures: " + str(len(trace.repeated_signatures())) if trace.repeated_signatures() else ""}
<br>Observatory v0 · extend this in M3, M8, M10 and M12.</footer>
</div></body></html>"""


def demo_trace() -> Trace:
    """A trace with everything the renderer knows how to show."""
    from agentcourse import AgentLoop, ScriptedModel, ToolRegistry, parallel, say, tool

    @tool
    def get_weather(city: str) -> str:
        """Get current conditions for a city.

        Use this when the user asks about weather right now. Returns temperature
        in Celsius and a one-word sky description.

        Args:
            city: City name, e.g. 'Oslo'.
        """
        return f"{city}: 4C, light rain"

    @tool
    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email.

        Use this only after the user has asked for something to be sent.
        Returns the message id.

        Args:
            to: Recipient address.
            subject: Subject line.
            body: Plain text body.
        """
        return "sent id=msg_88"

    model = ScriptedModel([
        parallel(("get_weather", {"city": "Oslo"}), ("get_weather", {"city": "Lisbon"})),
        {"text": None, "calls": [("send_email", {"to": "me", "subject": "Weather",
                                                 "body": "Oslo 4C; Lisbon 19C"})],
         "stop": "tool_use"},
        say("Oslo is 4C with light rain, Lisbon 19C and clear. Emailed."),
    ])
    run = AgentLoop(model, ToolRegistry(get_weather, send_email)).run(
        "What's the weather in Oslo and Lisbon? Email me the summary."
    )
    # Occupancy is a v1 (M3) field; populate it here so the demo shows the bar.
    for turn in run.trace.turns:
        if turn.role == "assistant":
            turn.occupancy = {"system": 320, "tools": 540,
                              "history": max(0, turn.input_tokens - 860),
                              "results": 0}
    return run.trace


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render an agent trace to HTML.")
    ap.add_argument("trace", nargs="?", help="path to a trace JSON file")
    ap.add_argument("-o", "--out", default="observatory.html")
    ap.add_argument("--demo", action="store_true",
                    help="render a generated demo trace instead of a file")
    args = ap.parse_args(argv)

    if args.demo:
        trace = demo_trace()
    elif args.trace:
        trace = Trace.from_json(args.trace)
    else:
        ap.error("give a trace file, or --demo")

    out = Path(args.out)
    out.write_text(render(trace), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes) — "
          f"{trace.model_turns} model turns, ${trace.total_usd:.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
