"""
The evaluation harness (M8).

Outcome assertions and trajectory assertions, run N times per case because
agents are stochastic, reporting pass *rates* rather than pass/fail. A judge
protocol is included so labs can swap a scripted judge for a real one.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class EvalCase:
    id: str
    prompt: str
    tier: str = "realistic"                     # easy | realistic | hard

    # Outcome assertions
    must_contain: list = field(default_factory=list)
    must_not_contain: list = field(default_factory=list)
    judge_rubric: str | None = None

    # Trajectory assertions — these catch the agent that succeeded by luck
    must_call: list = field(default_factory=list)
    must_not_call: list = field(default_factory=list)
    max_turns: int = 15
    max_usd: float = 0.25


@dataclass
class CaseResult:
    case_id: str
    tier: str
    passed: bool
    failures: list = field(default_factory=list)
    turns: int = 0
    usd: float = 0.0
    tools_called: list = field(default_factory=list)
    output: str = ""


@dataclass
class Report:
    results: list = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return sum(r.passed for r in self.results) / len(self.results) if self.results else 0.0

    def rate_for_tier(self, tier: str) -> float:
        rows = [r for r in self.results if r.tier == tier]
        return sum(r.passed for r in rows) / len(rows) if rows else 0.0

    def rate_for_case(self, case_id: str) -> float:
        """Pass rate across repeats. A case that passes 2 of 5 times is failing,
        even though it is green sometimes."""
        rows = [r for r in self.results if r.case_id == case_id]
        return sum(r.passed for r in rows) / len(rows) if rows else 0.0

    @property
    def total_usd(self) -> float:
        return sum(r.usd for r in self.results)

    @property
    def mean_turns(self) -> float:
        return statistics.mean([r.turns for r in self.results]) if self.results else 0.0

    @property
    def turn_variance(self) -> float:
        """Variance matters: two agents with the same mean are not the same
        product if one of them is unpredictable (M8)."""
        turns = [r.turns for r in self.results]
        return statistics.pvariance(turns) if len(turns) > 1 else 0.0

    @property
    def failures_by_reason(self) -> dict:
        counts: dict = {}
        for r in self.results:
            for f in r.failures:
                key = f.split(":")[0]
                counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def summary(self) -> str:
        lines = [
            f"cases   {len({r.case_id for r in self.results})}"
            f"  runs {len(self.results)}",
            f"pass    {self.pass_rate:.0%}"
            f"   easy {self.rate_for_tier('easy'):.0%}"
            f"   realistic {self.rate_for_tier('realistic'):.0%}"
            f"   hard {self.rate_for_tier('hard'):.0%}",
            f"cost    ${self.total_usd:.4f} total",
            f"turns   mean {self.mean_turns:.1f}  variance {self.turn_variance:.1f}",
        ]
        if self.failures_by_reason:
            lines.append("failures " + ", ".join(
                f"{k}={v}" for k, v in self.failures_by_reason.items()))
        return "\n".join(lines)


def run_case(case: EvalCase, run_agent: Callable, judge: Callable | None = None) -> CaseResult:
    """Run one case once and apply every assertion.

    `run_agent(prompt)` must return an object with `.output`, `.turns`, `.usd`
    and `.tools_called` — the shape `agentcourse.loop.AgentRun` provides.
    """
    failures: list = []
    try:
        run = run_agent(case.prompt)
    except Exception as exc:                                  # noqa: BLE001
        return CaseResult(case.id, case.tier, False, [f"crash: {exc!r}"])

    text = (run.output or "").lower()

    for needle in case.must_contain:
        if needle.lower() not in text:
            failures.append(f"outcome: missing {needle!r}")
    for needle in case.must_not_contain:
        if needle.lower() in text:
            failures.append(f"outcome: contains forbidden {needle!r}")

    for name in case.must_call:
        if name not in run.tools_called:
            failures.append(f"trajectory: never called {name}")
    for name in case.must_not_call:
        if name in run.tools_called:
            failures.append(f"trajectory: called forbidden {name}")

    if run.turns > case.max_turns:
        failures.append(f"budget: {run.turns} turns exceeds {case.max_turns}")
    if run.usd > case.max_usd:
        failures.append(f"budget: ${run.usd:.4f} exceeds ${case.max_usd:.2f}")

    if case.judge_rubric and judge is not None:
        verdict = judge(case, run)
        if not verdict.get("passed"):
            failures.append(f"judge: {verdict.get('reason', 'failed rubric')}")

    return CaseResult(
        case_id=case.id, tier=case.tier, passed=not failures, failures=failures,
        turns=run.turns, usd=run.usd, tools_called=list(run.tools_called),
        output=run.output or "",
    )


def run_suite(cases, run_agent, judge=None, repeats: int = 1) -> Report:
    """Run every case `repeats` times. Repeats are not optional for a real
    suite: a single run of a stochastic system is noise."""
    report = Report()
    for case in cases:
        for _ in range(repeats):
            report.results.append(run_case(case, run_agent, judge))
    return report


# --------------------------------------------------------------------------
# judge validation (M8b)
# --------------------------------------------------------------------------


def cohens_kappa(a: list, b: list) -> float:
    """Agreement corrected for chance.

    Raw agreement lies on skewed sets: a judge that passes everything scores 80%
    on a set where 80% of cases pass. Kappa exposes that.
    """
    if len(a) != len(b) or not a:
        raise ValueError("label lists must be the same non-zero length")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    expected = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if expected == 1:
        return 0.0
    return (observed - expected) / (1 - expected)


def validate_judge(human_labels: list, judge_labels: list) -> dict:
    """Compare a judge against reference labels, and say which way it errs."""
    n = len(human_labels)
    agreement = sum(h == j for h, j in zip(human_labels, judge_labels)) / n
    false_pass = sum(1 for h, j in zip(human_labels, judge_labels) if j == 1 and h == 0)
    false_fail = sum(1 for h, j in zip(human_labels, judge_labels) if j == 0 and h == 1)
    kappa = cohens_kappa(human_labels, judge_labels)

    if false_pass > false_fail:
        bias = "over-passes: fluent, padded or badly-sourced answers slip through"
    elif false_fail > false_pass:
        bias = "over-fails: likely punishing abstention or brevity"
    else:
        bias = "no directional bias in this sample"

    return {
        "agreement": agreement,
        "kappa": kappa,
        "false_pass": false_pass,
        "false_fail": false_fail,
        "bias": bias,
        # Landis & Koch: >0.6 substantial. Pick your own threshold and defend it.
        "usable": kappa >= 0.6,
    }
