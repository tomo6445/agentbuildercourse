"""
Lab 10 — read the trace, name the failure.

Three broken agents, one failure class each, and no source access. Everything
here works from trace *shape* — span names, argument hashes, result sizes,
token counts, stop reasons — so it is also the demonstration that you can
diagnose an agent without logging a word of the conversation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from agentcourse.trace import ToolSpan, Trace, TurnRecord


def arg_hash(arguments: dict) -> str:
    """Identity without contents. Two identical hashes on consecutive turns is
    an oscillation detector that reveals nothing (M10)."""
    blob = json.dumps(arguments, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


@dataclass
class Diagnosis:
    failure_class: str
    evidence: list = field(default_factory=list)
    confidence: str = "medium"


TAXONOMY = [
    "tool_misselection", "argument_malformation", "context_degradation",
    "goal_drift", "oscillation", "silent_truncation", "injection",
]


def diagnose(trace: Trace) -> Diagnosis:
    """Classify a trace against the taxonomy, using signatures rather than text."""
    spans = trace.tool_spans
    evidence: list = []

    # -- oscillation: a repeated (tool, args) pair with no state change --------
    seen: dict = {}
    for span in spans:
        key = (span.name, arg_hash(span.arguments))
        seen.setdefault(key, 0)
        seen[key] += 1
    repeats = {k: n for k, n in seen.items() if n > 1}
    if repeats:
        evidence.append(f"repeated (tool, args): {sorted(repeats)[0][0]} x"
                        f"{max(repeats.values())}")
        return Diagnosis("oscillation", evidence, "high")

    # -- silent truncation: a result sitting exactly on a limit ---------------
    for span in spans:
        if span.truncated:
            evidence.append(f"{span.name} reported truncation")
            return Diagnosis("silent_truncation", evidence, "high")
        if span.result_bytes and span.result_bytes % 1000 == 0 and span.result_bytes >= 4000:
            evidence.append(
                f"{span.name} returned exactly {span.result_bytes} bytes — a "
                f"result sitting on a round limit is a truncation until proven "
                f"otherwise"
            )
            return Diagnosis("silent_truncation", evidence, "medium")

    # -- goal drift: tool arguments migrating away from the stated goal --------
    goal_terms = set(trace.task.lower().split())
    overlaps = []
    for span in spans:
        terms = set(json.dumps(span.arguments, default=str).lower()
                    .replace('"', " ").replace(":", " ").split())
        overlaps.append(len(goal_terms & terms))
    if len(overlaps) >= 3 and overlaps[0] > 0 and overlaps[-1] == 0:
        evidence.append(f"goal-term overlap in tool arguments fell "
                        f"{overlaps[0]} -> 0 across {len(overlaps)} calls, with "
                        f"no errors anywhere")
        return Diagnosis("goal_drift", evidence, "high")

    # -- context degradation: occupancy climbing over the run -----------------
    occupancies = [t.context_tokens for t in trace.turns if t.context_tokens]
    if occupancies and max(occupancies) > 140_000 and occupancies[-1] == max(occupancies):
        evidence.append(f"context grew to {max(occupancies):,} tokens by the "
                        f"final turn")
        return Diagnosis("context_degradation", evidence, "medium")

    # -- argument malformation ------------------------------------------------
    errored = [s for s in spans if not s.ok]
    if errored and len({s.name for s in errored}) == 1:
        evidence.append(f"{errored[0].name} failed {len(errored)} times with "
                        f"argument errors")
        return Diagnosis("argument_malformation", evidence, "medium")

    return Diagnosis("no_failure_detected", ["nothing in the trace looks wrong"], "low")


# --------------------------------------------------------------------------
# the three broken agents
# --------------------------------------------------------------------------

def _trace(task: str, spans_per_turn: list, occupancy: list | None = None) -> Trace:
    trace = Trace(task=task)
    for i, spans in enumerate(spans_per_turn):
        trace.add(TurnRecord(
            index=i, role="assistant", stop_reason="tool_use",
            input_tokens=600 + i * 900, output_tokens=90,
            context_tokens=(occupancy[i] if occupancy else 0),
            tool_spans=spans, usd=0.004 * (i + 1),
        ))
    return trace.finish("ok")


def broken_a() -> Trace:
    """Task: summarise Q3 revenue. Ends up writing a competitor memo."""
    return _trace(
        "summarise Q3 revenue for the board",
        [
            [ToolSpan("search_docs", {"q": "Q3 revenue"}, 210, True, 2400)],
            [ToolSpan("search_docs", {"q": "competitor pricing"}, 240, True, 2900)],
            [ToolSpan("search_docs", {"q": "market share by vendor"}, 260, True, 3300)],
            [ToolSpan("search_docs", {"q": "vendor landscape analysis"}, 250, True, 3100)],
        ],
    )


def broken_b() -> Trace:
    """Two tools that each tell the model to go and use the other."""
    return _trace(
        "check stock for sku A1 and reserve it",
        [
            [ToolSpan("inventory_get", {"sku": "A1"}, 120, True, 900)],
            [ToolSpan("stock_verify", {"sku": "A1"}, 140, True, 950)],
            [ToolSpan("inventory_get", {"sku": "A1"}, 118, True, 900)],
        ],
    )


def broken_c() -> Trace:
    """A 48,000-token contract returned as 4,000 tokens, unmarked."""
    return _trace(
        "does the contract contain a termination clause",
        [
            [ToolSpan("read_file", {"path": "contract.pdf"}, 900, True, 16000)],
            [ToolSpan("summarise", {"section": "clauses"}, 300, True, 1200)],
        ],
    )


BROKEN = {"A": broken_a, "B": broken_b, "C": broken_c}
EXPECTED = {"A": "goal_drift", "B": "oscillation", "C": "silent_truncation"}


# --------------------------------------------------------------------------
# waterfall with cost attribution
# --------------------------------------------------------------------------

def waterfall(trace: Trace, children: list | None = None) -> list:
    """Rows for a subagent waterfall: who spent what, and where the clock went."""
    rows = [{
        "id": trace.trace_id, "parent": trace.parent_id, "label": trace.agent,
        "task": trace.task[:60], "usd": round(trace.total_usd, 5),
        "tokens": trace.total_input_tokens + trace.total_output_tokens,
        "depth": 0,
    }]
    for child in children or []:
        rows.append({
            "id": child.trace_id, "parent": trace.trace_id, "label": child.agent,
            "task": child.task[:60], "usd": round(child.total_usd, 5),
            "tokens": child.total_input_tokens + child.total_output_tokens,
            "depth": 1,
        })
    total = sum(r["usd"] for r in rows)
    for r in rows:
        r["share"] = round(r["usd"] / total, 3) if total else 0.0
    return rows


def privacy_safe_view(trace: Trace) -> list:
    """The posture that gets observability past a security review: shape, not
    contents. Everything a diagnosis needs is still here."""
    return [{
        "turn": t.index,
        "stop_reason": t.stop_reason,
        "input_tokens": t.input_tokens,
        "output_tokens": t.output_tokens,
        "cache_read_tokens": t.cache_read_tokens,
        "usd": t.usd,
        "tools": [{"name": s.name, "args_hash": arg_hash(s.arguments),
                   "ms": s.duration_ms, "bytes": s.result_bytes,
                   "ok": s.ok, "truncated": s.truncated}
                  for s in t.tool_spans],
    } for t in trace.turns]


def main() -> int:
    for name, build in BROKEN.items():
        trace = build()
        d = diagnose(trace)
        mark = "OK " if d.failure_class == EXPECTED[name] else "MISS"
        print(f"{mark} agent {name}: {d.failure_class} ({d.confidence})")
        for line in d.evidence:
            print(f"      {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
