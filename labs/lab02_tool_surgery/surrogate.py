"""
A surrogate model whose success depends on tool quality.

Running Lab 2 against the real API costs money and is stochastic, which makes a
graded exercise awkward. This module simulates the parts of model behaviour that
tool design actually controls, deterministically and offline:

  - **selection** — the model picks a tool by matching the request against the
    name and description. Vague or near-duplicate descriptions cause misselection.
  - **argument filling** — a parameter with no description gets guessed at; a
    closed set typed as a free string gets a plausible-but-wrong value; an opaque
    id with no stated origin gets invented.
  - **recovery** — an empty result is reported as "does not exist" unless the
    description says empty is not an error; a failure is retried unless the error
    says it is permanent.

It is a simulator, not a model. It cannot tell you your tools are *good* — only
that they are not failing in the specific, mechanical ways M2 describes. The
same eval set runs against the real model with `--live`, which is the measurement
that counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "by", "with",
    "this", "that", "it", "is", "are", "be", "use", "used", "using", "when",
    "you", "your", "returns", "return", "gets", "get", "from", "as", "at",
}


def words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower())
            if w not in STOPWORDS and len(w) > 2}


@dataclass
class Outcome:
    passed: bool
    reason: str = ""
    failure_class: str = ""          # the M10 taxonomy
    tool_chosen: str | None = None
    tokens: int = 0
    turns: int = 2


@dataclass
class Task:
    """One eval case, with the tool-layer properties it exercises."""

    id: str
    prompt: str
    expects_tool: str
    #: keywords a competent description for the right tool would contain
    intent: list = field(default_factory=list)
    #: parameters the model must supply correctly
    needs_params: list = field(default_factory=list)
    #: parameters whose value comes from a closed set — needs an enum to get right
    closed_set_params: list = field(default_factory=list)
    #: parameters that are opaque ids — the description must say where they come from
    opaque_id_params: list = field(default_factory=list)
    #: this task's query legitimately matches nothing; the model must retry, not give up
    empty_result: bool = False
    #: the backing service is down permanently; the model must stop, not thrash
    permanent_failure: bool = False


def simulate(task: Task, registry) -> Outcome:
    """Run one task against a tool layer and report what the tool layer caused."""
    tools = {t.name: t for t in registry}
    tokens = registry.definition_tokens * 2 + 400      # definitions are re-sent per turn

    # --- 1. selection --------------------------------------------------
    intent = set(task.intent)
    scores = {}
    for name, t in tools.items():
        surface = words(name.replace("_", " ")) | words(t.description)
        scores[name] = len(intent & surface)

    best = max(scores.values()) if scores else 0
    winners = sorted(n for n, s in scores.items() if s == best)
    if best == 0:
        return Outcome(False, "no tool description matched the request",
                       "tool_misselection", None, tokens)
    if len(winners) > 1:
        # A tie is a real failure: near-duplicate descriptions attract each
        # other's calls. Resolve deterministically to the wrong one when the
        # expected tool is not alphabetically first.
        chosen = winners[0]
        if chosen != task.expects_tool:
            return Outcome(False,
                           f"ambiguous: {', '.join(winners)} score equally",
                           "tool_misselection", chosen, tokens)
    chosen = winners[0] if len(winners) == 1 else task.expects_tool
    if chosen != task.expects_tool:
        return Outcome(False, f"selected {chosen}, needed {task.expects_tool}",
                       "tool_misselection", chosen, tokens)

    tool = tools[chosen]
    props = tool.input_schema.get("properties", {})

    # --- 2. argument filling -------------------------------------------
    for param in task.needs_params:
        if param not in props:
            return Outcome(False, f"tool has no parameter '{param}'",
                           "argument_malformation", chosen, tokens)
        schema = props[param]
        if not schema.get("description"):
            return Outcome(False,
                           f"'{param}' has no description, so its value was guessed",
                           "argument_malformation", chosen, tokens)

    for param in task.closed_set_params:
        schema = props.get(param, {})
        if not schema.get("enum"):
            return Outcome(False,
                           f"'{param}' is a closed set typed as a free string; "
                           f"a plausible-but-invalid value was sent",
                           "argument_malformation", chosen, tokens)

    for param in task.opaque_id_params:
        schema = props.get(param, {})
        origin = re.search(r"returned by|from |obtain|retriev|search|look ?up",
                           schema.get("description", ""), re.I)
        if not origin:
            return Outcome(False,
                           f"'{param}' is an opaque id and nothing says where to "
                           f"get it, so one was invented",
                           "argument_malformation", chosen, tokens)

    # --- 3. recovery ----------------------------------------------------
    if task.empty_result:
        if not re.search(r"empty|no match|nothing match|not an error|no results",
                         tool.description, re.I):
            return Outcome(False,
                           "empty result reported to the user as 'does not exist' "
                           "instead of retried with a wider query",
                           "goal_drift", chosen, tokens)

    if task.permanent_failure:
        if not re.search(r"permanent|maintenance|will not succeed|stop retrying|"
                         r"do not retry|unavailable until", tool.description, re.I):
            return Outcome(False,
                           "permanent failure retried until the turn cap",
                           "error_thrash", chosen, tokens,
                           turns=10)

    return Outcome(True, "", "", chosen, tokens)
