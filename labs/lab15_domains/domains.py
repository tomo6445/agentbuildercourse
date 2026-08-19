"""
Lab 15 — eight domains as reference architectures, two of them implemented.

The architectures barely vary. What varies is the failure each domain punishes,
so each entry names it and each implementation defends against it specifically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Domain:
    key: str
    name: str
    architecture: str
    bites_you: str
    controls: list = field(default_factory=list)


DOMAINS = [
    Domain("software", "Software engineering",
           "autonomous agent · file and shell tools · checkpointing · test-gated loop",
           "verification: 'it compiles' is not 'it works'",
           ["tests are the loop's success criterion, not a step in it",
            "the agent cannot modify the tests it is graded by",
            "isolated worktree", "checkpoint per turn"]),
    Domain("research", "Research and analysis",
           "orchestrator-workers · wide parallel search · synthesis with citations",
           "source quality: agents drift to SEO content farms",
           ["source quality scored in the rubric", "prefer primary sources",
            "a citation per claim, asserted in evals", "surface conflicts"]),
    Domain("bi", "Data and BI",
           "routing plus SQL tools · read-only credentials · validation before execution",
           "schema hallucination and silent wrong answers",
           ["read-only credentials", "schema as a resource", "query validation",
            "sanity checks against known aggregates", "show the query with the answer"]),
    Domain("support", "Customer operations",
           "routing workflow with an escalation ladder · policy retrieval",
           "confident wrongness at scale",
           ["tight scope", "aggressive escalation", "citation to policy",
            "abstention rewarded in evals"]),
    Domain("documents", "Document processing",
           "prompt chaining plus evaluator-optimiser · per-field confidence",
           "the long tail and silent truncation",
           ["per-field confidence", "human review queue for low confidence",
            "never truncate silently", "sample the tail when building evals"]),
    Domain("devops", "DevOps / SRE",
           "narrow high-privilege tools · dry-run first · approval on mutations",
           "blast radius; the lethal trifecta lives here by default",
           ["dry-run by default, apply is a separate gated mode",
            "approval on every mutation", "exhaustive durable audit",
            "narrow tools: restart_service(name), not bash"]),
    Domain("crm", "Sales and CRM",
           "MCP-heavy integration · memory for account context · write validation",
           "data hygiene and PII",
           ["validate writes against schema and existing records", "dedupe first",
            "never overwrite a human-authored field — append",
            "redaction hook on every result"]),
    Domain("scheduled", "Personal / internal automation",
           "scheduled agents · narrow scope · self-reporting",
           "unattended failure nobody notices for three weeks",
           ["report every run, so silence is the alarm",
            "assert on outputs, not exit codes", "dead-man's switch",
            "hard budget cap"]),
]

BY_KEY = {d.key: d for d in DOMAINS}


# ==========================================================================
# implementation 1 — BI: refuse to return a silently wrong number
# ==========================================================================

WRITE_SQL = re.compile(r"\b(insert|update|delete|drop|alter|truncate|grant|create)\b",
                       re.I)


class UnsafeQuery(Exception):
    pass


def run_query(sql: str, rows: list, *, schema: dict,
              expectations: dict | None = None) -> dict:
    """Execute a read-only query and refuse to return a number nobody can check."""
    if WRITE_SQL.search(sql):
        raise UnsafeQuery("only SELECT statements are permitted; the agent holds "
                          "read-only credentials")

    # Schema hallucination errors loudly here rather than returning a wrong join.
    referenced = set(re.findall(r"\b(\w+)\.(\w+)\b", sql))
    for table, column in referenced:
        if table in schema and column not in schema[table]:
            raise UnsafeQuery(
                f"{table}.{column} does not exist. Columns on {table}: "
                f"{', '.join(sorted(schema[table]))}"
            )

    warnings = []
    exp = expectations or {}
    if "min_rows" in exp and len(rows) < exp["min_rows"]:
        warnings.append(f"returned {len(rows)} rows, expected at least "
                        f"{exp['min_rows']} — check the join")
    if "total_within" in exp and rows:
        actual = sum(r[exp["total_column"]] for r in rows)
        low, high = exp["total_within"]
        if not low <= actual <= high:
            warnings.append(f"total {actual:,.0f} is outside the expected range "
                            f"{low:,.0f}-{high:,.0f}")

    # The query goes back with the answer, always. A number without its query is
    # a number nobody can check.
    return {"sql": sql, "rows": rows, "warnings": warnings,
            "trustworthy": not warnings}


# ==========================================================================
# implementation 2 — scheduled: make silence impossible
# ==========================================================================

@dataclass
class RunRecord:
    status: str              # ok | assertion_failed | budget | crashed
    detail: str = ""
    rows: int = 0
    usd: float = 0.0


class DeadMansSwitch:
    """No run in N hours pages someone. The whole point of an unattended agent
    is that nobody is watching, so failure detection cannot depend on watching."""

    def __init__(self, max_silence_hours: float = 26.0):
        self.max_silence_hours = max_silence_hours
        self.last_report_hours = 0.0

    def report(self, at_hours: float) -> None:
        self.last_report_hours = at_hours

    def overdue(self, now_hours: float) -> bool:
        return now_hours - self.last_report_hours > self.max_silence_hours


def scheduled_run(work, *, budget_usd: float = 2.0, now_hours: float = 0.0,
                  switch: DeadMansSwitch | None = None) -> RunRecord:
    """Report every outcome, including success. Assert on outputs, not exit codes."""
    try:
        result = work()
    except Exception as exc:                                  # noqa: BLE001
        record = RunRecord("crashed", repr(exc))
    else:
        if result["usd"] > budget_usd:
            record = RunRecord("budget", f"${result['usd']:.2f} over "
                                         f"${budget_usd:.2f}", usd=result["usd"])
        elif result["rows"] == 0:
            # Exit code 0 is not success.
            record = RunRecord("assertion_failed", "produced no rows",
                               usd=result["usd"])
        elif result.get("freshness_hours", 0) >= 24:
            record = RunRecord("assertion_failed", "source data was stale",
                               rows=result["rows"], usd=result["usd"])
        else:
            record = RunRecord("ok", "", result["rows"], result["usd"])

    if switch:
        switch.report(now_hours)                # every outcome reports
    return record
