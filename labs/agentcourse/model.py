"""
A model you can test against.

The labs need agent loops to be exercised deterministically, offline, and for
free. `ScriptedModel` mimics the shape of a Messages API response closely enough
that the loop you write here is the loop you would write against the real API —
same content blocks, same stop reasons, same usage fields.

`LiveModel` is the real thing, behind the same interface, so any lab can be run
against Claude by swapping one object.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

# --------------------------------------------------------------------------
# content blocks — deliberately mirroring the wire format
# --------------------------------------------------------------------------


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class Response:
    content: list
    stop_reason: str
    usage: Usage = field(default_factory=Usage)
    model: str = "scripted"

    @property
    def tool_uses(self) -> list:
        return [b for b in self.content if b.type == "tool_use"]

    @property
    def text(self) -> str:
        return "".join(b.text for b in self.content if b.type == "text")


# --------------------------------------------------------------------------
# script builders
# --------------------------------------------------------------------------


def say(text: str, stop: str = "end_turn") -> dict:
    """A turn that produces text and stops."""
    return {"text": text, "calls": [], "stop": stop}


def call(name: str, **args) -> dict:
    """A turn that requests a single tool call."""
    return {"text": None, "calls": [(name, args)], "stop": "tool_use"}


def parallel(*calls: tuple) -> dict:
    """A turn requesting several tool calls at once.

    Pass tuples of (name, args_dict) — this is the shape that catches loops
    which only handle one tool_use block per turn.
    """
    return {"text": None, "calls": list(calls), "stop": "tool_use"}


def truncated(text: str) -> dict:
    """A turn cut off by max_tokens. Loops that branch on block presence
    rather than stop_reason mishandle this one."""
    return {"text": text, "calls": [], "stop": "max_tokens"}


def paused() -> dict:
    """A turn paused by a long-running server-side tool."""
    return {"text": None, "calls": [], "stop": "pause_turn"}


# --------------------------------------------------------------------------
# the scripted model
# --------------------------------------------------------------------------


class ScriptExhausted(RuntimeError):
    """The loop asked for more turns than the script provides.

    Nearly always means the loop failed to terminate, which is exactly the bug
    the M1 tests are looking for.
    """


class ScriptedModel:
    """A deterministic stand-in for the Messages API.

    Drive it either with a fixed list of turns::

        model = ScriptedModel([call("get_weather", city="Oslo"), say("It's 4C.")])

    or with a policy that inspects the conversation and decides::

        def policy(messages, tools):
            if any_tool_result_contains(messages, "error"):
                return say("I couldn't do that.")
            return call("retry_thing")

        model = ScriptedModel(policy=policy)
    """

    def __init__(
        self,
        script: Iterable[dict] | None = None,
        policy: Callable[[list, list], dict] | None = None,
        *,
        loop_forever: bool = False,
    ):
        if script is None and policy is None:
            raise ValueError("provide either a script or a policy")
        self.script = list(script or [])
        self.policy = policy
        self.loop_forever = loop_forever
        self.calls: list[dict] = []      # every request the loop made, for assertions
        self._n = 0

    # -- the interface a loop talks to ------------------------------------

    def create(self, *, messages, tools=None, system=None, model="scripted",
               max_tokens=16000, **kwargs) -> Response:
        self.calls.append({
            "messages": messages, "tools": tools or [],
            "system": system, "model": model, "kwargs": kwargs,
        })

        if self.policy is not None:
            turn = self.policy(messages, tools or [])
        elif self._n < len(self.script):
            turn = self.script[self._n]
        elif self.loop_forever and self.script:
            turn = self.script[-1]
        else:
            raise ScriptExhausted(
                f"script provides {len(self.script)} turns; the loop asked for "
                f"turn {self._n + 1}. If this is unexpected, your loop is not "
                f"terminating."
            )
        self._n += 1
        return self._render(turn, messages)

    # Alias so the object can stand in for `client.messages` as well.
    @property
    def messages(self):
        return self

    # -- rendering ---------------------------------------------------------

    def _render(self, turn: dict, messages: list) -> Response:
        blocks: list = []
        if turn.get("text"):
            blocks.append(TextBlock(text=turn["text"]))
        for i, (name, args) in enumerate(turn.get("calls", [])):
            blocks.append(ToolUseBlock(
                id=f"toolu_{self._n:02d}{i:02d}", name=name, input=dict(args),
            ))
        return Response(
            content=blocks,
            stop_reason=turn.get("stop", "end_turn"),
            usage=Usage(
                input_tokens=estimate_tokens(messages),
                output_tokens=sum(estimate_tokens_of_block(b) for b in blocks),
            ),
        )

    # -- helpers for assertions -------------------------------------------

    @property
    def turns_taken(self) -> int:
        return self._n

    def tools_offered(self) -> list:
        """Tool names the loop passed on its most recent request."""
        if not self.calls:
            return []
        return [t["name"] for t in self.calls[-1]["tools"]]


# --------------------------------------------------------------------------
# token estimation — good enough to compare designs, not a tokenizer
# --------------------------------------------------------------------------

CHARS_PER_TOKEN = 3.6


def estimate_tokens(obj: Any) -> int:
    """A rough, stable token estimate.

    Deliberately not a real tokenizer: the labs compare designs against each
    other, and for that a consistent proxy is enough. For real numbers, use the
    token counting endpoint.
    """
    if obj is None:
        return 0
    if isinstance(obj, str):
        return max(1, int(len(obj) / CHARS_PER_TOKEN))
    return max(1, int(len(json.dumps(obj, default=str)) / CHARS_PER_TOKEN))


def estimate_tokens_of_block(block) -> int:
    if getattr(block, "type", None) == "text":
        return estimate_tokens(block.text)
    return estimate_tokens({"name": block.name, "input": block.input})


# --------------------------------------------------------------------------
# the real model, behind the same interface
# --------------------------------------------------------------------------


class LiveModel:
    """The real Messages API, shaped like ScriptedModel.

    Any lab can be pointed at Claude by constructing this instead. Requires
    `pip install -e "labs[live]"` and credentials (ANTHROPIC_API_KEY, or a
    profile from `ant auth login`).
    """

    def __init__(self, model: str = "claude-opus-5", client=None):
        if client is None:
            try:
                import anthropic
            except ImportError as exc:                       # pragma: no cover
                raise ImportError(
                    'the live model needs the SDK: pip install -e "labs[live]"'
                ) from exc
            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.calls: list[dict] = []

    def create(self, *, messages, tools=None, system=None, model=None,
               max_tokens=16000, **kwargs) -> Response:
        request = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            **kwargs,
        }
        if tools:
            request["tools"] = tools
        if system:
            request["system"] = system
        self.calls.append(request)

        raw = self.client.messages.create(**request)
        return Response(
            content=[_adapt(b) for b in raw.content],
            stop_reason=raw.stop_reason,
            usage=Usage(
                input_tokens=raw.usage.input_tokens,
                output_tokens=raw.usage.output_tokens,
                cache_creation_input_tokens=getattr(
                    raw.usage, "cache_creation_input_tokens", 0) or 0,
                cache_read_input_tokens=getattr(
                    raw.usage, "cache_read_input_tokens", 0) or 0,
            ),
            model=raw.model,
        )

    @property
    def messages(self):
        return self


def _adapt(block):
    """Map an SDK content block onto the lab's dataclasses."""
    if block.type == "tool_use":
        return ToolUseBlock(id=block.id, name=block.name, input=dict(block.input))
    if block.type == "text":
        return TextBlock(text=block.text)
    return TextBlock(text=f"[{block.type} block]")


def default_model():
    """A live model when credentials are present, else a clear error.

    Used by the optional `--live` variants of the labs.
    """
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RuntimeError(
            "no credentials found. Set ANTHROPIC_API_KEY, or run `ant auth login`, "
            "or use ScriptedModel for offline work."
        )
    return LiveModel()
