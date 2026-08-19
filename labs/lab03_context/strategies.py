"""
Lab 3 — the three long-horizon context strategies behind one interface.

The workload is a research agent that discovers a fact per turn and is asked
about a sample of them at turn 60. What varies is what survives into the context
window, and what that costs.

The rot model is the part worth understanding. It is not "the window overflowed":
recall degrades *gradually* as occupancy rises, because attention is spread over
more material. A strategy that retains everything therefore does not recall
everything — which is the whole M3 lesson, and the reason the naive baseline
loses to a strategy that retains less.

This is a simulation with a deliberately simple rot curve. It reproduces the
*shape* of the real effect so you can reason about the trade-off; it is not a
prediction of any particular model's behaviour. Run `--live` for that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WINDOW = 200_000

# What one fact costs once it has been summarised into a running summary.
SUMMARY_LINE_TOKENS = 25

# Occupancy below ROT_FLOOR is comfortable; above it, recall falls away. Real
# curves vary by model and task — the point is that there IS a curve, not a cliff.
ROT_FLOOR = 0.25
ROT_CEILING = 0.85


def degradation(context_tokens: int) -> float:
    """Attention available for any one fact, as occupancy rises. 1.0 -> 0.35."""
    occupancy = context_tokens / WINDOW
    if occupancy <= ROT_FLOOR:
        return 1.0
    if occupancy >= ROT_CEILING:
        return 0.35
    span = (occupancy - ROT_FLOOR) / (ROT_CEILING - ROT_FLOOR)
    return 1.0 - 0.65 * span


@dataclass
class Fact:
    turn: int
    key: str
    text: str
    tokens: int


@dataclass
class StrategyResult:
    name: str
    recall: float
    accuracy: float
    context_tokens: int
    total_input_tokens: int
    extra_calls: int
    usd: float


class ContextStrategy:
    """One interface, four implementations. Each sees every turn and decides
    what is carried forward."""

    name = "base"
    #: calls this strategy makes on top of the agent's own turns
    extra_calls = 0

    def __init__(self, system_tokens: int = 1200, tool_tokens: int = 3400):
        self.system_tokens = system_tokens
        self.tool_tokens = tool_tokens
        self.facts: list = []

    def observe(self, fact: Fact) -> None:
        raise NotImplementedError

    def retained_keys(self) -> set:
        """Which facts the model can still see at answer time."""
        raise NotImplementedError

    def context_tokens(self) -> int:
        raise NotImplementedError

    # -- shared -----------------------------------------------------------

    def base_tokens(self) -> int:
        return self.system_tokens + self.tool_tokens


class NoStrategy(ContextStrategy):
    """Append everything. Retains every fact, and pays for it in attention."""

    name = "none"

    def observe(self, fact: Fact) -> None:
        self.facts.append(fact)

    def retained_keys(self) -> set:
        return {f.key for f in self.facts}

    def context_tokens(self) -> int:
        return self.base_tokens() + sum(f.tokens for f in self.facts)


class Compaction(ContextStrategy):
    """Summarise everything older than the last N turns.

    The summarisation prompt is the strategy: a budget-limited summary keeps the
    most recent of the old facts and drops the rest. Facts that fall out are
    gone — the agent has no memory of ever having found them.
    """

    name = "compaction"

    def __init__(self, keep_recent: int = 10, summary_budget: int = 1500, **kw):
        super().__init__(**kw)
        self.keep_recent = keep_recent
        self.summary_budget = summary_budget
        self.compactions = 0

    def observe(self, fact: Fact) -> None:
        self.facts.append(fact)
        if len(self.facts) % self.keep_recent == 0:
            self.compactions += 1

    def _split(self):
        recent = self.facts[-self.keep_recent:]
        older = self.facts[:-self.keep_recent]
        # A fact summarised into a running summary is a line, not a tenth of
        # the raw tool result it came from.
        kept, spent = [], 0
        for f in reversed(older):
            cost = SUMMARY_LINE_TOKENS
            if spent + cost > self.summary_budget:
                break
            kept.append(f)
            spent += cost
        return recent, list(reversed(kept)), spent

    def retained_keys(self) -> set:
        recent, summarised, _ = self._split()
        return {f.key for f in recent} | {f.key for f in summarised}

    def context_tokens(self) -> int:
        recent, _, summary_tokens = self._split()
        return self.base_tokens() + sum(f.tokens for f in recent) + summary_tokens

    @property
    def extra_calls(self) -> int:
        return self.compactions


class Notes(ContextStrategy):
    """Write each finding to a notes file; carry the file, not the transcript.

    Cheap, legible, and it survives the process dying — which is why it is the
    foundation of memory in M7. Its failure mode is hygiene: notes that only
    grow become their own context problem, so there is a cap here too.
    """

    name = "notes"

    def __init__(self, keep_recent: int = 6, note_tokens: int = 14,
                 notes_budget: int = 1800, **kw):
        super().__init__(**kw)
        self.keep_recent = keep_recent
        self.note_tokens = note_tokens
        self.notes_budget = notes_budget

    def observe(self, fact: Fact) -> None:
        self.facts.append(fact)

    def _notes(self):
        capacity = self.notes_budget // self.note_tokens
        return self.facts[-capacity:] if capacity < len(self.facts) else self.facts

    def retained_keys(self) -> set:
        recent = self.facts[-self.keep_recent:]
        return {f.key for f in self._notes()} | {f.key for f in recent}

    def context_tokens(self) -> int:
        recent = self.facts[-self.keep_recent:]
        return (self.base_tokens()
                + sum(f.tokens for f in recent)
                + len(self._notes()) * self.note_tokens)

    @property
    def extra_calls(self) -> int:
        return 0        # notes are written by the agent's own turns


class SubagentIsolation(ContextStrategy):
    """Each chunk of exploration happens in a worker's own window; the
    orchestrator receives only the finding.

    Best accuracy per token of *orchestrator* context, and by far the most
    expensive overall — you are paying for a full context per worker (M9).
    """

    name = "subagent"

    def __init__(self, chunk: int = 8, finding_tokens: int = 90,
                 worker_context_tokens: int = 140_000, **kw):
        super().__init__(**kw)
        self.chunk = chunk
        self.finding_tokens = finding_tokens
        self.worker_context_tokens = worker_context_tokens

    def observe(self, fact: Fact) -> None:
        self.facts.append(fact)

    def retained_keys(self) -> set:
        # A finding summarising a chunk carries every fact in that chunk.
        return {f.key for f in self.facts}

    def context_tokens(self) -> int:
        findings = (len(self.facts) + self.chunk - 1) // self.chunk
        return self.base_tokens() + findings * self.finding_tokens

    @property
    def extra_calls(self) -> int:
        return (len(self.facts) + self.chunk - 1) // self.chunk

    def hidden_tokens(self) -> int:
        """Tokens burned inside workers — the cumulative input across a whole
        worker loop, not one call. Invisible in the orchestrator's context and
        extremely visible on the invoice."""
        return self.extra_calls * self.worker_context_tokens


STRATEGIES = {
    "none": NoStrategy,
    "compaction": Compaction,
    "notes": Notes,
    "subagent": SubagentIsolation,
}
