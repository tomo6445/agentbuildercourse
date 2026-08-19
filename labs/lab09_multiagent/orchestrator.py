"""
Lab 9 — an orchestrator with a configurable worker pool.

The interesting code is not the fan-out. It is `brief()`: delegation prompt
engineering is where multi-agent systems are actually built or lost, and nearly
every efficiency bug in one is a delegation bug that people try to fix in
orchestration code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A tiny corpus. Each source answers some sub-questions and not others, and two
# of them disagree — so synthesis has something real to adjudicate.
CORPUS = {
    "10-K":            {"revenue": "2.1B", "margin": "31%", "segments": "4",
                        "capex": "180M", "arr": "1.9B", "backlog": "310M",
                        "quality": "primary"},
    "press-release":   {"revenue": "2.15B", "regions": "5", "quality": "secondary"},
    "analyst-note":    {"margin": "30%", "outlook": "cautious", "churn": "6%",
                        "nrr": "112%", "quality": "secondary"},
    "seo-roundup":     {"revenue": "2.4B", "margin": "40%", "quality": "junk"},
    "investor-deck":   {"outlook": "positive", "headcount": "4400",
                        "regions": "6", "fte_cost": "142k", "quality": "primary"},
}

# Four rich sub-questions the sources actively disagree about, plus a tail of
# minor ones. The tail is what makes the quality curve saturate: the first
# worker answers the question everyone cares about, the eighth answers
# "segments".
SUBQUESTIONS = [
    "revenue", "margin", "outlook", "headcount",
    "segments", "regions", "capex", "churn",
    "arr", "nrr", "backlog", "fte_cost",
]

#: Diminishing importance, so coverage of the tail buys progressively less.
WEIGHTS = {q: 1.0 / (i + 1) for i, q in enumerate(SUBQUESTIONS)}

WORKER_CONTEXT_TOKENS = 42_000       # a whole worker loop, not one call
LEAD_TOKENS = 9_000


@dataclass
class Brief:
    """What a worker is told. Five fields, and the second one is the one that
    stops workers duplicating each other."""

    task: str
    scope_out: list = field(default_factory=list)     # what OTHERS are covering
    tools: list = field(default_factory=list)         # restricted per worker
    effort: str = "1-2 searches"
    output_contract: tuple = ("finding", "sources", "confidence")

    def render(self) -> str:
        return (
            f"TASK: {self.task}\n"
            f"SCOPE: {self.task} only. Do NOT investigate "
            f"{', '.join(self.scope_out) or 'anything else'} — other workers are "
            f"covering those. Note and move on if you encounter them.\n"
            f"TOOLS: {', '.join(self.tools)}. You may not write or send anything.\n"
            f"EFFORT: {self.effort}. Stop once you have a figure from a primary "
            f"source.\n"
            f"OUTPUT: JSON with keys {', '.join(self.output_contract)}."
        )


@dataclass
class Finding:
    subquestion: str
    value: str | None
    sources: list
    confidence: str
    searches: list = field(default_factory=list)
    failed: bool = False


def effort_for(kind: str) -> int:
    """Worker count is a decision computed from the task, not a constant.

    A fixed pool is how you get eight agents on a question one lookup answers.
    """
    return {"simple_fact": 1, "comparison": 3, "open_research": 8,
            "survey": 12}.get(kind, 1)


def plan(subquestions: list, workers: int, *, scoped: bool = True) -> list:
    """Split the work into briefs.

    With `scoped=False` every worker is told to 'research the company', which is
    the state most multi-agent systems ship in.
    """
    chosen = subquestions[:workers] if workers <= len(subquestions) else subquestions
    briefs = []
    for q in chosen:
        briefs.append(Brief(
            task=f"Find the {q}" if scoped else "Research the company",
            scope_out=[o for o in chosen if o != q] if scoped else [],
            tools=["search", "fetch_document"],
            effort="1-2 searches" if scoped else "as much as needed",
        ))
    return briefs


def worker(brief: Brief, *, scoped: bool = True) -> Finding:
    """Run one worker. An unscoped brief searches everything, every time."""
    target = re.sub(r"^Find the ", "", brief.task)
    searched = [target] if scoped else list(SUBQUESTIONS)

    candidates = [(name, doc) for name, doc in CORPUS.items() if target in doc]
    if not candidates:
        return Finding(target, None, [], "low", searched)

    # Prefer primary sources. A worker without this heuristic drifts to whatever
    # is easiest to extract from, which is usually the junk.
    ranked = sorted(candidates,
                    key=lambda kv: {"primary": 0, "secondary": 1, "junk": 2}[kv[1]["quality"]])
    name, doc = ranked[0]
    confidence = "high" if doc["quality"] == "primary" else "medium"
    return Finding(target, doc[target], [name], confidence, searched)


def synthesise(findings: list) -> dict:
    """The lead's hardest job.

    Conflicts get surfaced, not averaged. Citations survive the rewrite. And
    unanimity on a hard question is treated as a flag rather than corroboration.
    """
    answer, conflicts, citations = {}, [], []
    for f in findings:
        if f.failed or f.value is None:
            continue
        answer[f.subquestion] = f.value
        citations.extend(f.sources)

        # Did any other source disagree? Say so rather than picking quietly.
        others = {name: doc[f.subquestion] for name, doc in CORPUS.items()
                  if f.subquestion in doc and doc[f.subquestion] != f.value}
        if others:
            conflicts.append({
                "subquestion": f.subquestion, "reported": f.value,
                "sources": f.sources, "disagreeing": others,
            })

    return {
        "answer": answer,
        "citations": sorted(set(citations)),
        "conflicts": conflicts,
        "degraded": [f.subquestion for f in findings if f.failed],
    }


def run(kind: str = "open_research", *, workers: int | None = None,
        scoped: bool = True, failing_worker: str | None = None) -> dict:
    """One orchestrated run. Returns the answer and what it cost."""
    n = workers if workers is not None else effort_for(kind)
    briefs = plan(SUBQUESTIONS, n, scoped=scoped)

    findings, searches = [], []
    for brief in briefs:
        target = re.sub(r"^Find the ", "", brief.task)
        if failing_worker and target == failing_worker:
            # A dead worker degrades the answer; it must not kill the run.
            findings.append(Finding(target, None, [], "low", [], failed=True))
            continue
        f = worker(brief, scoped=scoped)
        findings.append(f)
        searches.extend(f.searches)

    result = synthesise(findings)
    result["workers"] = len(briefs)
    result["searches"] = searches
    result["duplicate_searches"] = len(searches) - len(set(searches))
    result["tokens"] = LEAD_TOKENS + len(briefs) * WORKER_CONTEXT_TOKENS
    return result
