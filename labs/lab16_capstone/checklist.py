"""
Lab 16 — the capstone stage checklist.

    python -m lab16_capstone.checklist            # check ./capstone
    python -m lab16_capstone.checklist --path .

Run it from day one, not day thirteen. It is deliberately a poor way to discover
on day thirteen that stage 2 was never committed.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

STAGES = [
    ("01", "Problem definition", 0.10, ["PROBLEM.md"]),
    ("02", "Eval-first design", 0.20, ["evals/cases.json", "evals/rubric.md",
                                       "evals/judge_validation.json"]),
    ("03", "Architecture", 0.15, ["ARCHITECTURE.md", "decisions/"]),
    ("04", "Build", 0.20, ["agent/"]),
    ("05", "Harden", 0.15, ["THREAT_MODEL.md", "security/redteam_results.md"]),
    ("06", "Instrument", 0.10, ["observability/", "FAILURE_TAXONOMY.md"]),
    ("07", "Ship and defend", 0.10, ["DEMO.md"]),
]

DECISION_FIELDS = ("Decision", "Alternatives considered", "Reason",
                   "What would reverse this")


@dataclass
class StageResult:
    number: str
    name: str
    weight: float
    present: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing


def check_eval_first(root: Path) -> list:
    """The rule that makes stage 2 mean anything: at least 30 cases, three
    tiers, trajectory assertions, and a validated judge."""
    notes = []
    cases_path = root / "evals" / "cases.json"
    if not cases_path.exists():
        return ["evals/cases.json missing — this is the heaviest-weighted stage"]

    try:
        cases = json.loads(cases_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"evals/cases.json is not valid JSON: {exc}"]

    if len(cases) < 30:
        notes.append(f"{len(cases)} cases; at least 30 are required")
    tiers = {c.get("tier") for c in cases}
    if not {"easy", "realistic", "hard"} <= tiers:
        notes.append(f"tiers present: {sorted(t for t in tiers if t)}; "
                     f"all three are required")
    if not any(c.get("must_call") or c.get("must_not_call") for c in cases):
        notes.append("no trajectory assertions — outcome-only evaluation passes "
                     "the agent that succeeded by luck")
    if not any("not available" in str(c.get("must_contain", "")).lower()
               or c.get("expects_abstention") for c in cases):
        notes.append("no case rewards abstention — you will optimise honesty out")

    judge = root / "evals" / "judge_validation.json"
    if judge.exists():
        try:
            data = json.loads(judge.read_text())
            kappa = data.get("kappa")
            if kappa is None:
                notes.append("judge_validation.json has no kappa; raw agreement "
                             "is the number that lies")
            elif kappa < 0.6:
                notes.append(f"judge kappa {kappa} is below 0.6 — fix the rubric, "
                             f"never the reference labels")
        except json.JSONDecodeError:
            notes.append("judge_validation.json is not valid JSON")
    return notes


def check_decisions(root: Path) -> list:
    notes = []
    folder = root / "decisions"
    if not folder.exists():
        return ["decisions/ missing"]
    entries = sorted(folder.glob("*.md"))
    if len(entries) < 5:
        notes.append(f"{len(entries)} Decision Log entries; the architecture "
                     f"stage lists six decisions to record")
    for entry in entries:
        text = entry.read_text()
        missing = [f for f in DECISION_FIELDS if f.lower() not in text.lower()]
        if missing:
            notes.append(f"{entry.name} lacks: {', '.join(missing)}")
    return notes


def check_cost_gate(root: Path) -> list:
    for path in (root / ".github" / "workflows").glob("*.yml"):
        text = path.read_text()
        if "max-usd-per-task" in text or "max_usd_per_task" in text:
            return []
    return ["no per-task cost ceiling enforced in CI — the ceiling set at "
            "stage 1 has to be a gate, not an intention"]


def check_failure_demo(root: Path) -> list:
    demo = root / "DEMO.md"
    if not demo.exists():
        return ["DEMO.md missing"]
    text = demo.read_text().lower()
    if not re.search(r"graceful|degrade|fault|failure demo", text):
        return ["DEMO.md does not describe the required graceful-failure "
                "demonstration under a fault you did not choose"]
    return []


def run(root: Path) -> tuple[list, list]:
    root = Path(root)
    results, blockers = [], []

    for number, name, weight, required in STAGES:
        result = StageResult(number, name, weight)
        for rel in required:
            path = root / rel
            exists = path.is_dir() if rel.endswith("/") else path.exists()
            (result.present if exists else result.missing).append(rel)
        if number == "02":
            result.notes = check_eval_first(root)
        elif number == "03":
            result.notes = check_decisions(root)
        elif number == "07":
            result.notes = check_failure_demo(root)
        results.append(result)

    blockers += check_cost_gate(root)

    # The ordering rule: stage 2 must exist before stage 4 has content.
    agent_dir = root / "agent"
    cases = root / "evals" / "cases.json"
    if agent_dir.exists() and any(agent_dir.rglob("*.py")) and not cases.exists():
        blockers.append("agent code exists but evals/cases.json does not — the "
                        "eval suite is committed BEFORE the agent, and the order "
                        "is the point")
    return results, blockers


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="capstone")
    args = ap.parse_args(argv)
    root = Path(args.path)

    if not root.exists():
        print(f"{root} does not exist. Start with:\n"
              f"  mkdir -p {root}/evals {root}/decisions\n"
              f"  {root}/PROBLEM.md   <- stage 1, today")
        return 1

    results, blockers = run(root)
    earned = sum(r.weight for r in results if r.complete and not r.notes)

    for r in results:
        mark = "OK  " if r.complete and not r.notes else "TODO"
        print(f"{mark} {r.number} {r.name:<24} weight {r.weight:.0%}")
        for m in r.missing:
            print(f"       missing: {m}")
        for n in r.notes:
            print(f"       {n}")

    for b in blockers:
        print(f"BLOCKER {b}")

    print(f"\nstages complete: {earned:.0%} of the weighted total")
    return 0 if earned == 1.0 and not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
