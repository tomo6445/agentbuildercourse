"""
Lab 8c — three injected regressions your suite must catch.

Each is a real failure shape, and each is invisible to an eval suite that checks
only the final answer:

  1. `trajectory`  — right answer, wrong route: it stopped calling the tool that
                     disambiguates and started guessing. Outcome-only evals pass it.
  2. `cost`        — same accuracy, four times the turns. An eval that reports
                     accuracy alone ships this.
  3. `abstention`  — it stopped saying "I don't know" and started inventing.
                     Accuracy on answerable cases is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agentcourse.evals import EvalCase, Report, run_suite


@dataclass
class FakeRun:
    output: str
    turns: int
    usd: float
    tools_called: list = field(default_factory=list)


CASES = [
    EvalCase("c1", "What was Q3 revenue?", tier="easy",
             must_contain=["2.1"], must_call=["lookup_figure"], max_turns=6,
             max_usd=0.05),
    EvalCase("c2", "What was Q3 revenue and the margin?", tier="realistic",
             must_contain=["2.1", "31"], must_call=["lookup_figure"], max_turns=6,
             max_usd=0.05),
    EvalCase("c3", "What was Q5 revenue?", tier="hard",
             must_contain=["not available"], must_not_contain=["$"],
             must_call=["lookup_figure"], max_turns=6, max_usd=0.05),
]


def healthy(prompt: str) -> FakeRun:
    if "Q5" in prompt:
        return FakeRun("Q5 is not a quarter; that data is not available.", 2, 0.01,
                       ["lookup_figure"])
    if "margin" in prompt:
        return FakeRun("Revenue $2.1B, margin 31%.", 3, 0.02,
                       ["lookup_figure", "lookup_figure"])
    return FakeRun("Revenue was $2.1B.", 2, 0.01, ["lookup_figure"])


def regression_trajectory(prompt: str) -> FakeRun:
    """Right answers, but it stopped calling the tool — it is guessing now."""
    run = healthy(prompt)
    run.tools_called = []
    return run


def regression_cost(prompt: str) -> FakeRun:
    """Same answers, four times the turns and the spend."""
    run = healthy(prompt)
    run.turns *= 5
    run.usd *= 6
    return run


def regression_abstention(prompt: str) -> FakeRun:
    """It stopped abstaining and started inventing. Answerable cases unaffected."""
    if "Q5" in prompt:
        return FakeRun("Q5 revenue was $2.4B.", 2, 0.01, ["lookup_figure"])
    return healthy(prompt)


AGENTS = {
    "healthy": healthy,
    "trajectory": regression_trajectory,
    "cost": regression_cost,
    "abstention": regression_abstention,
}


def evaluate(agent_name: str, repeats: int = 3) -> Report:
    return run_suite(CASES, AGENTS[agent_name], repeats=repeats)


def main() -> int:
    for name in AGENTS:
        report = evaluate(name)
        caught = "-" if name == "healthy" else ("CAUGHT" if report.pass_rate < 1 else "MISSED")
        print(f"{name:<12} pass {report.pass_rate:>4.0%}  mean turns "
              f"{report.mean_turns:>4.1f}  cost ${report.total_usd:.3f}  {caught}")
        for reason, count in report.failures_by_reason.items():
            print(f"             {reason} x{count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
