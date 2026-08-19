"""
The reference agent loop.

This is what you build by hand in Lab 1. Later labs import it so they can focus
on their own subject rather than re-implementing the loop each time — but the
shape is deliberately identical to the M1 lesson, including the parts people
skip: branching on stop_reason, returning all parallel results in one message,
errors as results, and a cap that actually stops things.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .cost import Budget, turn_cost
from .tools import ToolRegistry
from .trace import ToolSpan, Trace, TurnRecord


@dataclass
class AgentRun:
    output: str = ""
    turns: int = 0
    usd: float = 0.0
    tools_called: list = field(default_factory=list)
    outcome: str = "ok"                 # ok | turn_cap | budget | oscillation | error
    detail: str = ""
    trace: Trace | None = None
    messages: list = field(default_factory=list)


class AgentLoop:
    """A tool-using agent loop with a budget, a trace and a no-progress detector."""

    def __init__(self, model, registry: ToolRegistry, *, system: str = "",
                 budget: Budget | None = None, model_name: str = "scripted",
                 detect_oscillation: bool = True,
                 on_turn: Callable | None = None):
        self.model = model
        self.registry = registry
        self.system = system
        self.budget = budget or Budget()
        self.model_name = model_name
        self.detect_oscillation = detect_oscillation
        self.on_turn = on_turn          # hook point: validation, redaction, audit (M5)

    def run(self, prompt: str, messages: list | None = None) -> AgentRun:
        messages = list(messages or []) + [{"role": "user", "content": prompt}]
        trace = Trace(task=prompt)
        run = AgentRun(trace=trace, messages=messages)
        seen_signatures: set = set()

        while True:
            if self.budget.exhausted:
                return self._stop(run, trace, "turn_cap" if
                                  self.budget.turns >= self.budget.max_turns else "budget",
                                  self.budget.reason)

            started = time.perf_counter()
            response = self.model.create(
                messages=messages,
                tools=self.registry.definitions,
                system=self.system,
                model=self.model_name,
            )
            latency = (time.perf_counter() - started) * 1000
            cost = self.budget.charge(response.usage, self.model_name)
            run.usd += cost
            run.turns += 1

            record = trace.add(TurnRecord(
                index=len(trace.turns),
                role="assistant",
                blocks=[_describe(b) for b in response.content],
                stop_reason=response.stop_reason,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_read_tokens=response.usage.cache_read_input_tokens,
                latency_ms=latency,
                usd=cost,
            ))
            if self.on_turn:
                self.on_turn(record, response)

            # A paused server-side tool is not an answer: re-send to resume.
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue

            # Branch on stop_reason, not on whether blocks happen to be present:
            # a max_tokens truncation has no tool_use blocks and is not a result.
            if response.stop_reason != "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                run.output = response.text
                if response.stop_reason == "max_tokens":
                    return self._stop(run, trace, "error",
                                      "response truncated at max_tokens")
                return self._stop(run, trace, "ok", "")

            messages.append({"role": "assistant", "content": response.content})

            results, spans = [], []
            for block in response.tool_uses:
                run.tools_called.append(block.name)
                t0 = time.perf_counter()
                result = self.registry.execute(block)
                span = ToolSpan(
                    name=block.name,
                    arguments=block.input,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    ok=not result.get("is_error"),
                    result_bytes=len(str(result.get("content", ""))),
                    error=result.get("content") if result.get("is_error") else None,
                )
                spans.append(span)
                results.append(result)

                if self.detect_oscillation:
                    if span.signature in seen_signatures:
                        record.tool_spans = spans
                        # All results still go back, so the transcript stays valid.
                        messages.append({"role": "user", "content": results})
                        return self._stop(
                            run, trace, "oscillation",
                            f"repeated call with identical arguments: {block.name}",
                        )
                    seen_signatures.add(span.signature)

            record.tool_spans = spans
            trace.add(TurnRecord(
                index=len(trace.turns), role="tool_result",
                blocks=[{"tool_use_id": r["tool_use_id"],
                         "is_error": bool(r.get("is_error"))} for r in results],
            ))

            # Every result goes back in ONE user message. Splitting them is
            # accepted by the API and quietly suppresses parallel tool use.
            messages.append({"role": "user", "content": results})

    # -- helpers -----------------------------------------------------------

    def _stop(self, run: AgentRun, trace: Trace, outcome: str, detail: str) -> AgentRun:
        run.outcome, run.detail = outcome, detail
        if outcome != "ok" and not run.output:
            run.output = f"Stopped: {detail}"
        trace.finish(outcome, detail)
        return run


def _describe(block) -> dict:
    """A trace-safe summary of a content block: shape, not contents (M10)."""
    if block.type == "tool_use":
        return {"type": "tool_use", "name": block.name, "input": block.input}
    return {"type": "text", "chars": len(block.text)}
