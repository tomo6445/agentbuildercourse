"""
The trace record the Observatory reads.

Designed once, in M1, and extended for the rest of the course. Changing the
shape later is annoying, so the fields that matter later are here from the
start: cache metadata (M3, M12), stop reasons (M1, M10), context occupancy
(M3), and the parent link that makes subagent waterfalls possible (M9, M10).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ToolSpan:
    name: str
    arguments: dict
    duration_ms: float
    ok: bool
    result_bytes: int = 0
    truncated: bool = False
    error: str | None = None

    @property
    def signature(self) -> str:
        """(tool, args) identity — repeated signatures are the oscillation
        detector from M1, and it works without logging arguments (M10)."""
        return f"{self.name}:{json.dumps(self.arguments, sort_keys=True, default=str)}"


@dataclass
class TurnRecord:
    index: int
    role: str                                  # user | assistant | tool_result
    blocks: list = field(default_factory=list)
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    latency_ms: float = 0.0
    usd: float = 0.0
    context_tokens: int = 0                    # live window occupancy at this turn
    occupancy: dict = field(default_factory=dict)   # system/tools/history/results
    tool_spans: list = field(default_factory=list)


@dataclass
class Trace:
    task: str
    agent: str = "agent"
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_id: str | None = None               # set on subagent traces (M9)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    turns: list = field(default_factory=list)
    outcome: str = "running"                   # running | ok | turn_cap | budget | error
    outcome_detail: str = ""

    # -- recording ---------------------------------------------------------

    def add(self, record: TurnRecord) -> TurnRecord:
        self.turns.append(record)
        return record

    def finish(self, outcome: str, detail: str = "") -> "Trace":
        self.outcome, self.outcome_detail = outcome, detail
        self.ended_at = time.time()
        return self

    # -- reading -----------------------------------------------------------

    @property
    def total_usd(self) -> float:
        return sum(t.usd for t in self.turns)

    @property
    def total_input_tokens(self) -> int:
        return sum(t.input_tokens for t in self.turns)

    @property
    def total_output_tokens(self) -> int:
        return sum(t.output_tokens for t in self.turns)

    @property
    def model_turns(self) -> int:
        return sum(1 for t in self.turns if t.role == "assistant")

    @property
    def tool_spans(self) -> list:
        return [s for t in self.turns for s in t.tool_spans]

    @property
    def duration_ms(self) -> float:
        return ((self.ended_at or time.time()) - self.started_at) * 1000

    def repeated_signatures(self) -> list:
        """Tool signatures seen more than once — the oscillation signal (M10)."""
        seen, repeats = set(), []
        for span in self.tool_spans:
            sig = span.signature if hasattr(span, "signature") else ToolSpan(**span).signature
            if sig in seen:
                repeats.append(sig)
            seen.add(sig)
        return repeats

    # -- serialisation -----------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        return path

    @classmethod
    def from_json(cls, path: str | Path) -> "Trace":
        data = json.loads(Path(path).read_text())
        turns = [TurnRecord(**{**t, "tool_spans": [ToolSpan(**s) for s in t["tool_spans"]]})
                 for t in data.pop("turns", [])]
        return cls(turns=turns, **data)
