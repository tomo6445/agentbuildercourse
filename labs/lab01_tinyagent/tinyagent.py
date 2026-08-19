"""
Lab 1 — tinyagent.

The agent loop, by hand. This file ships complete so the repository is green and
so you have a reference; to do the lab yourself, copy `starter/tinyagent.py`
over this file and make `test_tinyagent.py` pass.

    cp starter/tinyagent.py tinyagent.py     # take the lab
    git checkout tinyagent.py                # restore the reference

Twelve assertions define the gate. They are not arbitrary: each one is a bug
that shows up in real hand-written loops.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from agentcourse.cost import Budget, turn_cost
from agentcourse.trace import ToolSpan, Trace, TurnRecord

MAX_TURNS = 10


@dataclass
class Result:
    """What a run returns. `outcome` is why it stopped, which matters as much
    as the text — a turn-capped run is not a successful one."""

    output: str = ""
    outcome: str = "ok"            # ok | turn_cap | budget | truncated | error
    detail: str = ""
    turns: int = 0
    usd: float = 0.0
    tools_called: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    trace: Trace | None = None


def run(model, registry, prompt: str, *, system: str = "",
        budget: Budget | None = None, model_name: str = "scripted") -> Result:
    """Run an agent loop to completion.

    `model` exposes `.create(messages=, tools=, system=, model=)`.
    `registry` exposes `.definitions` and `.execute(block) -> tool_result dict`.
    """
    budget = budget or Budget(max_turns=MAX_TURNS)
    messages: list = [{"role": "user", "content": prompt}]
    trace = Trace(task=prompt)
    result = Result(messages=messages, trace=trace)

    while True:
        # 1. The cap is checked BEFORE the call, so an exhausted budget never
        #    buys one more turn.
        if budget.exhausted:
            return _stop(result, trace,
                         "turn_cap" if budget.turns >= budget.max_turns else "budget",
                         budget.reason)

        started = time.perf_counter()
        response = model.create(
            messages=messages,
            tools=registry.definitions,
            system=system,
            model=model_name,
        )
        latency_ms = (time.perf_counter() - started) * 1000

        cost = budget.charge(response.usage, model_name)
        result.usd += cost
        result.turns += 1

        record = trace.add(TurnRecord(
            index=len(trace.turns),
            role="assistant",
            blocks=[_describe(b) for b in response.content],
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=response.usage.cache_read_input_tokens,
            latency_ms=latency_ms,
            usd=cost,
        ))

        # 2. A paused server-side tool is not an answer. Echo the turn back to
        #    resume it, rather than reporting a half-finished response.
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        # 3. Branch on stop_reason, never on "are there tool_use blocks".
        #    A max_tokens truncation has no tool_use blocks and is not success.
        if response.stop_reason != "tool_use":
            # The final turn belongs in the transcript too, so `messages` is a
            # conversation a caller can resume rather than one ending on a
            # tool_result.
            messages.append({"role": "assistant", "content": response.content})
            result.output = _text_of(response)
            if response.stop_reason == "max_tokens":
                return _stop(result, trace, "truncated", "response hit max_tokens")
            return _stop(result, trace, "ok", "")

        # 4. The assistant turn goes back verbatim, tool_use blocks included.
        messages.append({"role": "assistant", "content": response.content})

        # 5. Execute EVERY requested call, not just the first.
        results, spans = [], []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result.tools_called.append(block.name)
            t0 = time.perf_counter()
            tool_result = registry.execute(block)      # never raises
            results.append(tool_result)
            spans.append(ToolSpan(
                name=block.name,
                arguments=block.input,
                duration_ms=(time.perf_counter() - t0) * 1000,
                ok=not tool_result.get("is_error"),
                result_bytes=len(str(tool_result.get("content", ""))),
                error=tool_result.get("content") if tool_result.get("is_error") else None,
            ))
        record.tool_spans = spans

        trace.add(TurnRecord(
            index=len(trace.turns),
            role="tool_result",
            blocks=[{"tool_use_id": r["tool_use_id"],
                     "is_error": bool(r.get("is_error"))} for r in results],
        ))

        # 6. All results return in ONE user message, each keyed to its
        #    tool_use_id. Splitting them across messages is accepted by the API
        #    and quietly trains the model out of parallel tool use.
        messages.append({"role": "user", "content": results})


def _stop(result: Result, trace: Trace, outcome: str, detail: str) -> Result:
    result.outcome, result.detail = outcome, detail
    if outcome != "ok" and not result.output:
        result.output = f"Stopped: {detail}"
    trace.finish(outcome, detail)
    return result


def _text_of(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


def _describe(block) -> dict:
    if block.type == "tool_use":
        return {"type": "tool_use", "name": block.name, "input": block.input}
    return {"type": "text", "chars": len(block.text)}
