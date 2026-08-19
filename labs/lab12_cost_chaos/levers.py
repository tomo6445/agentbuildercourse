"""
Lab 12a — cut the bill by 60% without losing more than 3 points of accuracy.

Five levers, each with a real cost effect and a real accuracy cost. The tests
check both numbers, so buying one with the other fails.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from agentcourse.cost import PRICES, project

BASELINE_ACCURACY = 0.88


@dataclass(frozen=True)
class Config:
    """The knobs. Defaults are the un-optimised agent."""

    model: str = "claude-opus-5"
    caching: bool = False
    turns_per_task: int = 18
    stable_prefix_tokens: int = 9_000       # system + a sprawling tool surface
    growth_per_turn: int = 2_400            # whole tool results, unshaped
    output_per_turn: int = 420
    subagents: int = 3
    route_cheap_steps: bool = False

    def cost(self, tasks_per_day: int = 2000) -> dict:
        return project(
            tasks_per_day=tasks_per_day,
            turns_per_task=self.turns_per_task,
            stable_prefix_tokens=self.stable_prefix_tokens,
            growth_per_turn=self.growth_per_turn,
            output_per_turn=self.output_per_turn,
            model=self.model,
            cached=self.caching,
            subagents=self.subagents,
        )

    @property
    def accuracy(self) -> float:
        """What each lever costs in quality. Caching costs nothing, which is why
        it is always the first move."""
        acc = BASELINE_ACCURACY
        if self.model == "claude-sonnet-5":
            acc -= 0.012
        elif self.model == "claude-haiku-4-5":
            acc -= 0.070
        if self.route_cheap_steps:
            acc -= 0.008                    # a quality floor keeps this small
        if self.turns_per_task < 12:
            acc -= 0.004 * (12 - self.turns_per_task)
        if self.growth_per_turn < 900:
            acc -= 0.010                    # over-shaped returns start losing detail
        if self.subagents < 3:
            acc -= 0.006 * (3 - self.subagents)
        return round(acc, 4)


LEVERS = {
    "caching": lambda c: replace(c, caching=True),
    "consolidate_tools": lambda c: replace(c, stable_prefix_tokens=3_400),
    "shape_returns": lambda c: replace(c, growth_per_turn=1_100),
    "fewer_turns": lambda c: replace(c, turns_per_task=11),
    "route_cheap_steps": lambda c: replace(c, route_cheap_steps=True,
                                           output_per_turn=300),
    "fewer_workers": lambda c: replace(c, subagents=1),
}


def apply(config: Config, names: list) -> Config:
    for name in names:
        config = LEVERS[name](config)
    return config


def report(baseline: Config, tuned: Config, tasks_per_day: int = 2000) -> dict:
    b, t = baseline.cost(tasks_per_day), tuned.cost(tasks_per_day)
    return {
        "baseline_per_task": b["per_task"],
        "tuned_per_task": t["per_task"],
        "reduction": 1 - t["per_task"] / b["per_task"],
        "baseline_month": b["per_month"],
        "tuned_month": t["per_month"],
        "baseline_accuracy": baseline.accuracy,
        "tuned_accuracy": tuned.accuracy,
        "accuracy_drop": baseline.accuracy - tuned.accuracy,
        "dominant_before": b["dominant_term"],
        "dominant_after": t["dominant_term"],
    }


def main() -> int:
    base = Config()
    print(f"{'levers applied':<58}{'$/task':>9}{'cut':>7}{'acc':>8}")
    print("-" * 70)
    applied: list = []
    for name in ("caching", "consolidate_tools", "shape_returns", "fewer_turns",
                 "route_cheap_steps", "fewer_workers"):
        applied.append(name)
        tuned = apply(base, applied)
        r = report(base, tuned)
        print(f"{' + '.join(applied):<58}"
              f"{'$' + format(r['tuned_per_task'], '.4f'):>9}"
              f"{r['reduction']:>7.0%}{r['tuned_accuracy']:>8.1%}")

    final = report(base, apply(base, applied))
    print(f"\nbaseline ${final['baseline_per_task']:.4f}/task, "
          f"${final['baseline_month']:,.0f}/month")
    print(f"tuned    ${final['tuned_per_task']:.4f}/task, "
          f"${final['tuned_month']:,.0f}/month")
    print(f"dominant term: {final['dominant_before']} -> {final['dominant_after']}")
    print(f"accuracy {final['baseline_accuracy']:.1%} -> {final['tuned_accuracy']:.1%} "
          f"(down {final['accuracy_drop']:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
