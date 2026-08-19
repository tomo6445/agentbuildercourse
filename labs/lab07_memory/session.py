"""
Lab 7 — the multi-session agent.

A task spanning several sessions while the harness kills the process at
arbitrary points. The protocol is the whole design:

    check memory first, record continuously, assume interruption.

`record at the end` loses exactly the runs where memory would have mattered —
the ones that did not finish.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from .store import MemoryStore

# The work: twelve steps, each establishing one fact.
STEPS = [f"step-{i:02d}" for i in range(12)]

PROTOCOL = """You have a memory directory that persists across sessions.

ALWAYS begin by viewing /memories. Do not re-explore anything already recorded.

Record continuously, not at the end:
  - the goal, once, at the start
  - each fact you establish, with its source
  - what remains to be done

Assume you will be interrupted at any moment. Anything not written down is lost.
"""


@dataclass
class SessionOutcome:
    completed_steps: list = field(default_factory=list)
    reexplored: list = field(default_factory=list)
    killed_after: int | None = None


class Killed(Exception):
    """The harness killed the process mid-session."""


def run_session(store: MemoryStore, *, kill_after: int | None = None) -> SessionOutcome:
    """One session: read what is known, do the next steps, record as you go."""
    outcome = SessionOutcome(killed_after=kill_after)

    # 1. Check memory FIRST.
    listing = store.view("")
    done = {line.split("  ")[0].replace("progress/", "").replace(".md", "")
            for line in listing.splitlines() if line.startswith("progress/")}

    worked = 0
    for step in STEPS:
        if step in done:
            continue
        if kill_after is not None and worked >= kill_after:
            raise Killed(f"process killed after {worked} steps")

        # 2. Record immediately, not at the end of the session.
        store.write(f"progress/{step}.md",
                    f"# {step}\nEstablished: value for {step}\nSource: ledger row {step}\n")
        outcome.completed_steps.append(step)
        if step in done:
            outcome.reexplored.append(step)
        worked += 1

    return outcome


def run_task(root: Path, *, kills: list, seed: int = 20260819) -> dict:
    """Run the task across sessions, killing the process where told.

    Returns what the graders care about: did it finish, did it repeat work, and
    did memory stay inside its budget.
    """
    rng = random.Random(seed)
    store = MemoryStore(root)
    store.write("goal.md", "# Goal\nReconcile the twelve ledger steps.\n")

    sessions, reexplored = 0, []
    for kill_after in kills + [None]:
        sessions += 1
        try:
            outcome = run_session(store, kill_after=kill_after)
            reexplored += outcome.reexplored
        except Killed:
            continue

        done = {p.name.replace(".md", "") for p in (root / "progress").glob("*.md")}
        if done >= set(STEPS):
            break

    done = {p.name.replace(".md", "") for p in (root / "progress").glob("*.md")}
    return {
        "sessions": sessions,
        "completed": sorted(done),
        "finished": done >= set(STEPS),
        "reexplored": reexplored,
        "bytes": store.total_bytes(),
        "files": store.file_count(),
    }
