"""
Lab 7 — a memory backend, and the security you own because you wrote it.

The memory tool is client-executed: the model issues commands and *your* handler
performs them. So the path validation, the size caps, the write-time filtering
and the provenance tagging are all yours. This file is that handler.

Two defences carry the module:

  `resolve()`  — decode, canonicalise, then confirm containment, in that order.
                 Checking containment on the raw string is the classic mistake,
                 and it misses symlinks entirely.

  `screen()`   — write-time validation. Memory poisoning is stored injection:
                 untrusted content becomes trusted memory in one hop, and the
                 damage lands days later in an unrelated task. Read-time
                 defences run after the bad data is already stored.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote


class MemoryError_(Exception):
    """Rejected. The model sees this as an error result and can try a legal path."""


# ==========================================================================
# path resolution
# ==========================================================================

DOT_ONLY = re.compile(r"^\.{2,}$")


def decode_fully(text: str, rounds: int = 4) -> str:
    """Percent-decode until stable. One pass is not enough: `%252e` decodes to
    `%2e` decodes to `.`."""
    for _ in range(rounds):
        nxt = unquote(text)
        if nxt == text:
            return text
        text = nxt
    raise MemoryError_("path is encoded too many times to be legitimate")


def resolve(root: Path, requested: str) -> Path:
    """Map a model-supplied path onto a real one, or refuse.

    Order matters and this is the order:
      1. reject what cannot be decoded safely (NUL bytes, endless encoding)
      2. decode repeatedly until stable
      3. normalise separators and whitespace
      4. reject absolute and home-relative paths
      5. resolve fully — which collapses `..` AND follows symlinks
      6. only now, assert containment against the resolved root
    """
    root = Path(root).resolve()

    if "\0" in requested:
        raise MemoryError_("path contains a NUL byte")
    if not requested.strip():
        raise MemoryError_("empty path")

    decoded = decode_fully(requested).replace("\\", "/").strip()

    if decoded.startswith("~"):
        raise MemoryError_("home-relative paths are not permitted")
    if decoded.startswith("/"):
        raise MemoryError_("absolute paths are not permitted")

    for segment in decoded.split("/"):
        if DOT_ONLY.match(segment) and segment != "..":
            raise MemoryError_(f"dot-only segment {segment!r}")

    candidate = (root / decoded).resolve()

    # Containment is checked AFTER resolution, so a symlink inside the root
    # pointing out of it cannot slip through.
    if candidate != root and root not in candidate.parents:
        raise MemoryError_("path escapes the memory root")
    if candidate == root:
        raise MemoryError_("path resolves to the memory root itself")
    return candidate


# ==========================================================================
# write-time screening
# ==========================================================================

INSTRUCTION_SHAPES = [
    (re.compile(r"\b(?:always|never|from now on|in future sessions?|going forward)\b"
                r".{0,80}\b(?:send|forward|post|upload|email|export|copy)\b", re.I | re.S),
     "standing instruction to transmit data"),
    (re.compile(r"\b(?:note|reminder|instruction)s? (?:for|to) (?:future|later|the next) "
                r"(?:session|agent|run)s?\b", re.I),
     "text addressed to future sessions"),
    (re.compile(r"\b(?:ignore|disregard|override)\b.{0,40}"
                r"\b(?:previous|prior|earlier|above|system)\b", re.I),
     "instruction override"),
    (re.compile(r"\b(?:the )?(?:standard|correct|approved|official) (?:procedure|process|"
                r"endpoint|method) is\b", re.I),
     "asserts a procedure as established practice"),
    (re.compile(r"https?://(?!(?:internal|localhost)\b)[^\s]+", re.I),
     "external URL"),
    (re.compile(r"\b(?:sk-ant-[A-Za-z0-9_\-]{6,}|AKIA[0-9A-Z]{16})\b"),
     "credential material"),
]


@dataclass
class Screening:
    allowed: bool
    findings: list = field(default_factory=list)
    sanitised: str = ""


def screen(content: str, *, provenance: str = "agent") -> Screening:
    """Decide whether content may be written, and how.

    Content the agent derived itself is trusted. Content that came from an
    untrusted source — a fetched page, an inbound email, a ticket — is screened
    for instruction-shaped text and refused if it carries any.

    This is the control. Provenance tagging and audit support it; they do not
    replace it.
    """
    findings = [why for pattern, why in INSTRUCTION_SHAPES if pattern.search(content)]

    if provenance == "agent":
        # Even self-authored notes must not carry credentials.
        blocking = [f for f in findings if f == "credential material"]
        return Screening(not blocking, findings, content)

    if findings:
        return Screening(False, findings, "")

    return Screening(True, [], content)


# ==========================================================================
# the store
# ==========================================================================

@dataclass
class Entry:
    path: str
    bytes: int
    provenance: str
    written_at: float


class MemoryStore:
    """A memory directory with containment, caps, screening and an audit log."""

    def __init__(self, root: Path, *, max_total_bytes: int = 256_000,
                 max_file_bytes: int = 32_000, max_files: int = 200):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_total_bytes = max_total_bytes
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files
        self.audit: list = []

    # -- audit -------------------------------------------------------------

    def _record(self, op: str, path: str, ok: bool, detail: str = "",
                provenance: str = "agent") -> None:
        self.audit.append({"ts": time.time(), "op": op, "path": path, "ok": ok,
                           "detail": detail, "provenance": provenance})

    def audit_for(self, path: str) -> list:
        """Trace one file's history. When a poisoned note surfaces three
        sessions later, this is what tells you where it came from."""
        return [e for e in self.audit if e["path"] == path]

    # -- reads -------------------------------------------------------------

    def view(self, path: str = "", *, page: int = 1, per_page: int = 25) -> str:
        """List the directory, or read a file.

        Directory listings are paginated: `view` on 200 files is a context bomb.
        """
        if not path or path in (".", "/"):
            files = sorted(p for p in self.root.rglob("*") if p.is_file())
            total = len(files)
            start = (page - 1) * per_page
            window = files[start:start + per_page]
            lines = [f"{p.relative_to(self.root)}  ({p.stat().st_size}B)"
                     for p in window]
            more = ""
            if start + per_page < total:
                more = (f"\n[showing {start + 1}-{start + len(window)} of {total}; "
                        f"call again with page={page + 1}]")
            self._record("view", path or "/", True)
            return "\n".join(lines) + more if lines else "(memory is empty)"

        target = resolve(self.root, path)
        if not target.exists():
            self._record("view", path, False, "not found")
            return f"No file at {path}. Use view() with no path to list memory."
        self._record("view", path, True)
        return target.read_text()

    # -- writes ------------------------------------------------------------

    def write(self, path: str, content: str, *, provenance: str = "agent",
              source: str = "") -> str:
        target = resolve(self.root, path)          # raises on escape

        verdict = screen(content, provenance=provenance)
        if not verdict.allowed:
            self._record("write", path, False,
                         "screened: " + "; ".join(verdict.findings), provenance)
            raise MemoryError_(
                "Refused: content from an untrusted source contains "
                + "; ".join(verdict.findings)
                + ". Summarise the material in your own words and record the "
                  "finding, not the text."
            )

        payload = verdict.sanitised
        if provenance != "agent":
            payload = (f"<!-- provenance: {provenance} source: {source or 'unknown'} "
                       f"written: {time.strftime('%Y-%m-%d')} -->\n") + payload

        encoded = payload.encode()
        if len(encoded) > self.max_file_bytes:
            self._record("write", path, False, "file too large", provenance)
            raise MemoryError_(
                f"File exceeds {self.max_file_bytes} bytes. Split it into topic "
                f"files under a directory rather than growing one file."
            )
        if self.total_bytes() - self.size_of(target) + len(encoded) > self.max_total_bytes:
            self._record("write", path, False, "budget exhausted", provenance)
            raise MemoryError_(
                "Memory budget exhausted. Delete or compact old notes — check "
                "/memories for entries that are no longer relevant."
            )
        if not target.exists() and self.file_count() >= self.max_files:
            self._record("write", path, False, "too many files", provenance)
            raise MemoryError_(
                f"Memory holds {self.max_files} files already. Consolidate "
                f"related notes before adding more."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload)
        self._record("write", path, True, provenance=provenance)
        return f"wrote {len(encoded)} bytes to {path}"

    def delete(self, path: str) -> str:
        target = resolve(self.root, path)
        if not target.exists():
            return f"No file at {path}."
        target.unlink()
        self._record("delete", path, True)
        return f"deleted {path}"

    # -- hygiene -----------------------------------------------------------

    def total_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())

    def file_count(self) -> int:
        return sum(1 for p in self.root.rglob("*") if p.is_file())

    def size_of(self, path: Path) -> int:
        return path.stat().st_size if path.exists() else 0

    def entries(self) -> list:
        return [Entry(str(p.relative_to(self.root)), p.stat().st_size,
                      "unknown", p.stat().st_mtime)
                for p in sorted(self.root.rglob("*")) if p.is_file()]

    def prune_older_than(self, seconds: float) -> int:
        """Facts about a system change. A note from four months ago is not
        evidence about today."""
        cutoff, removed = time.time() - seconds, 0
        for p in list(self.root.rglob("*")):
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        return removed

    # -- the tool interface ------------------------------------------------

    def handle(self, command: dict) -> dict:
        """Dispatch one memory tool command, turning refusals into results."""
        op = command.get("command")
        try:
            if op == "view":
                return {"ok": True, "content": self.view(command.get("path", ""))}
            if op == "create":
                return {"ok": True, "content": self.write(
                    command["path"], command.get("file_text", ""),
                    provenance=command.get("provenance", "agent"),
                    source=command.get("source", ""))}
            if op == "delete":
                return {"ok": True, "content": self.delete(command["path"])}
            return {"ok": False, "content": f"Unknown command {op!r}. "
                                            f"Supported: view, create, delete."}
        except MemoryError_ as exc:
            return {"ok": False, "content": f"Error: {exc}"}
