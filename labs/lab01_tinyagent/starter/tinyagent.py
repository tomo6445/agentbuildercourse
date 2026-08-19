"""
Lab 1 — tinyagent. STARTER.

    cp starter/tinyagent.py tinyagent.py
    pytest labs/lab01_tinyagent -q          # 12 failures. Make them pass.
    git checkout labs/lab01_tinyagent/tinyagent.py    # restore the reference

Read the errors in order — they are sequenced so each one teaches the next.
Do not read the reference until you have at least ten of them passing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from agentcourse.cost import Budget
from agentcourse.trace import ToolSpan, Trace, TurnRecord

MAX_TURNS = 10


@dataclass
class Result:
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

    `model.create(messages=, tools=, system=, model=)` returns a response with:
        .content       list of blocks; each has .type ('text' or 'tool_use')
                       text blocks have .text
                       tool_use blocks have .id, .name, .input
        .stop_reason   'end_turn' | 'tool_use' | 'max_tokens' | 'pause_turn'
        .usage         .input_tokens, .output_tokens, .cache_read_input_tokens

    `registry.definitions`          the list to pass as `tools`
    `registry.execute(block)`       runs one tool_use block and returns a
                                    tool_result dict. It never raises: failures
                                    come back with "is_error": True.

    `budget.charge(usage, model_name)` returns the cost of the turn and counts it.
    `budget.exhausted` / `budget.reason` tell you when and why to stop.
    """
    budget = budget or Budget(max_turns=MAX_TURNS)
    messages: list = [{"role": "user", "content": prompt}]
    trace = Trace(task=prompt)
    result = Result(messages=messages, trace=trace)

    while True:
        # TODO 1. Stop before calling the model if the budget is exhausted.
        #         Outcome is "turn_cap" if the turn limit tripped, else "budget".

        # TODO 2. Call the model with messages, registry.definitions, system.
        #         Charge the budget, count the turn, accumulate result.usd.

        # TODO 3. Record the turn on the trace (TurnRecord with role="assistant",
        #         stop_reason, token counts, latency, usd). Test 12 checks this.

        # TODO 4. Handle stop_reason == "pause_turn": append the assistant turn
        #         and continue, so the paused server tool resumes.

        # TODO 5. Handle every stop_reason that is NOT "tool_use": append the
        #         assistant turn, set result.output from the text blocks, and
        #         return. "max_tokens" is a truncation, not a success — outcome
        #         "truncated". Branch on stop_reason, not on block presence.

        # TODO 6. It IS a tool_use turn. Append the assistant turn VERBATIM
        #         (response.content, not a reconstruction).

        # TODO 7. Execute EVERY tool_use block in the turn, not just the first.
        #         Record each name on result.tools_called and build a ToolSpan.

        # TODO 8. Append ALL the tool_result blocks in a SINGLE user message,
        #         each keyed to its tool_use_id. Then loop.

        raise NotImplementedError("implement the loop")


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
