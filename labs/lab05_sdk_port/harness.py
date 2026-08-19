"""
Lab 5 — the harness pieces you adopt when you move off your hand-rolled loop.

Permissions, hooks and sessions, implemented in plain Python so you can see what
the abstraction is doing before you let a framework do it for you. Every piece
here maps to a line of your M1 loop.

The point of implementing them yourself is M5's central claim: a permission layer
is a *gate*, and a hook is a *policy*. Neither is a sandbox. The tests below
prove that on your own code, which is more persuasive than being told.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


# ==========================================================================
# permissions
# ==========================================================================

ALLOW, ASK, DENY = "allow", "ask", "deny"


@dataclass
class Rule:
    tool: str                      # tool name, or 'bash'
    pattern: str | None = None     # for bash, a regex over the command
    effect: str = ASK

    def matches(self, tool: str, args: dict) -> bool:
        if self.tool != tool:
            return False
        if self.pattern is None:
            return True
        command = str(args.get("command", ""))
        return re.search(self.pattern, command) is not None


class PermissionPolicy:
    """Allow / ask / deny per tool call.

    Rules are evaluated in order and the first match wins, with an explicit
    default. Note the shape of `explain()`: a policy you cannot explain to a
    reviewer is a policy nobody will trust.
    """

    def __init__(self, rules: list, default: str = ASK):
        self.rules = rules
        self.default = default
        self.decisions: list = []

    def check(self, tool: str, args: dict) -> tuple[str, str]:
        for rule in self.rules:
            if rule.matches(tool, args):
                reason = (f"rule {rule.tool}"
                          + (f"({rule.pattern})" if rule.pattern else "")
                          + f" -> {rule.effect}")
                self.decisions.append((tool, rule.effect, reason))
                return rule.effect, reason
        self.decisions.append((tool, self.default, "default"))
        return self.default, "no rule matched; default applied"

    def explain(self) -> str:
        lines = [f"{r.effect:>5}  {r.tool}" + (f"  {r.pattern}" if r.pattern else "")
                 for r in self.rules]
        lines.append(f"{self.default:>5}  (default)")
        return "\n".join(lines)


def default_policy() -> PermissionPolicy:
    """A policy denying network writes, as the lab requires.

    Read the deny rules and then read M11: every one of them is a claim that you
    enumerated the ways to express an action, and you did not. This is a gate.
    """
    return PermissionPolicy(
        rules=[
            Rule("read_file", effect=ALLOW),
            Rule("grep", effect=ALLOW),
            Rule("web_search", effect=ALLOW),
            Rule("bash", r"^\s*(ls|cat|head|tail|wc|grep|find)\b", ALLOW),
            Rule("bash", r"\b(curl|wget|nc|ssh|scp|rsync)\b", DENY),
            Rule("bash", r"\brm\s+-rf?\b", DENY),
            Rule("http_post", effect=DENY),
            Rule("send_email", effect=DENY),
            Rule("git_push", effect=DENY),
            Rule("write_file", effect=ASK),
        ],
        default=ASK,
    )


# ==========================================================================
# hooks
# ==========================================================================

class HookRejection(Exception):
    """A pre-tool hook refused the call. Becomes an error result, not a crash."""


class BudgetExceeded(Exception):
    """The cost ceiling was reached. Abort beats discovering it on the invoice."""


SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "[REDACTED:api-key]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED:aws-key]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "[REDACTED:private-key]"),
    (re.compile(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[REDACTED:email]"),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED:card]"),
]


def redact(text: str) -> str:
    """Strip secrets and PII from a tool result before it enters context.

    Doing it here also keeps them out of your traces, your logs and your eval
    fixtures — which is usually where they actually leak from.
    """
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def validate_path_within(root: str):
    """A pre-tool hook: refuse writes outside the working directory."""
    root_path = Path(root).resolve()

    def hook(tool: str, args: dict) -> dict:
        if tool not in ("write_file", "read_file"):
            return args
        target = (root_path / str(args.get("path", ""))).resolve()
        if target != root_path and root_path not in target.parents:
            raise HookRejection(
                f"path {args.get('path')!r} resolves outside {root_path}"
            )
        return args
    return hook


class CostCeiling:
    """Abort the run rather than discover the overage later."""

    def __init__(self, limit_usd: float):
        self.limit_usd, self.spent = limit_usd, 0.0

    def after_turn(self, usd: float) -> None:
        self.spent += usd
        if self.spent >= self.limit_usd:
            raise BudgetExceeded(
                f"session cost ${self.spent:.4f} reached the "
                f"${self.limit_usd:.2f} ceiling"
            )


class AuditLog:
    """Every call, argument and outcome, durably. Costs nothing; it is the
    difference between an incident you can explain and one you cannot."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.entries: list = []

    def record(self, tool: str, args: dict, effect: str, outcome: str) -> None:
        entry = {"ts": time.time(), "tool": tool, "args": args,
                 "effect": effect, "outcome": outcome}
        self.entries.append(entry)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")


# ==========================================================================
# sessions
# ==========================================================================

@dataclass
class Session:
    """Disk-persisted conversation state, resumable after the process dies.

    Checkpointing after every turn is what turns "the agent crashed at turn 30"
    from a lost hour into a resume.
    """

    session_id: str
    task: str = ""
    messages: list = field(default_factory=list)
    turn: int = 0
    usd: float = 0.0
    notes: dict = field(default_factory=dict)
    parent_id: str | None = None
    forked_at: int | None = None

    # -- persistence -------------------------------------------------------

    def save(self, root: Path) -> Path:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{self.session_id}.json"
        # Write-then-rename, so a crash mid-write cannot corrupt the checkpoint.
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, default=str))
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, root: Path, session_id: str) -> "Session":
        data = json.loads((Path(root) / f"{session_id}.json").read_text())
        return cls(**data)

    @classmethod
    def resume_or_start(cls, root: Path, session_id: str, task: str) -> "Session":
        try:
            return cls.load(root, session_id)
        except FileNotFoundError:
            return cls(session_id=session_id, task=task)

    # -- forking -----------------------------------------------------------

    def fork(self, at_turn: int, new_id: str) -> "Session":
        """Branch at a turn so you can change exactly one variable.

        This is the debugging superpower from M5: three forks and a root cause,
        instead of thirty re-runs and a hunch.
        """
        if at_turn > self.turn:
            raise ValueError(f"cannot fork at turn {at_turn}; session is at {self.turn}")
        # Each turn contributes an assistant message and (usually) a result.
        keep = [m for i, m in enumerate(self.messages) if i < at_turn * 2 + 1]
        return Session(
            session_id=new_id, task=self.task, messages=keep, turn=at_turn,
            usd=self.usd, notes=dict(self.notes),
            parent_id=self.session_id, forked_at=at_turn,
        )
