"""
Lab 3 — benchmark the strategies across a 60-turn research workload.

    python -m lab03_context.benchmark
    python -m lab03_context.benchmark --turns 100 --quiz 20
"""

from __future__ import annotations

import argparse
import random

from agentcourse.cost import PRICES

from .strategies import STRATEGIES, Fact, StrategyResult, degradation

# A fact per turn, sized like a real tool result rather than a sentence.
FACT_TOKENS = 2600
QUIZ_SEED = 20260819


def workload(turns: int) -> list:
    return [Fact(turn=i, key=f"f{i:03d}",
                 text=f"finding {i}: revenue line {i} reconciles to source {i}",
                 tokens=FACT_TOKENS)
            for i in range(turns)]


def quiz_keys(turns: int, n: int) -> list:
    """A fixed sample, so runs are comparable. Spread across the whole task,
    because a quiz that only asks about recent turns measures nothing."""
    rng = random.Random(QUIZ_SEED)
    return sorted(rng.sample([f"f{i:03d}" for i in range(turns)], n))


def evaluate(name: str, turns: int, quiz: list, model: str = "claude-sonnet-5") -> StrategyResult:
    strategy = STRATEGIES[name]()
    total_input = 0
    for fact in workload(turns):
        strategy.observe(fact)
        total_input += strategy.context_tokens()      # re-sent every turn

    retained = strategy.retained_keys()
    recall = sum(k in retained for k in quiz) / len(quiz)
    ctx = strategy.context_tokens()
    accuracy = recall * degradation(ctx)

    hidden = getattr(strategy, "hidden_tokens", lambda: 0)()
    price = PRICES[model]
    usd = ((total_input + hidden) * price["input"]
           + turns * 400 * price["output"]) / 1e6

    return StrategyResult(
        name=name, recall=recall, accuracy=accuracy, context_tokens=ctx,
        total_input_tokens=total_input + hidden,
        extra_calls=strategy.extra_calls, usd=usd,
    )


def baseline_accuracy(turns: int = 10, quiz_n: int = 12) -> float:
    """Accuracy early in the task, before context is a problem. The gate is
    relative to this: hold 90% of it at turn 60."""
    quiz = quiz_keys(turns, min(quiz_n, turns))
    return evaluate("none", turns, quiz).accuracy


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=60)
    ap.add_argument("--quiz", type=int, default=12)
    ap.add_argument("--cost-ceiling", type=float, default=6.00)
    args = ap.parse_args(argv)

    quiz = quiz_keys(args.turns, args.quiz)
    base = baseline_accuracy()
    target = base * 0.90

    print(f"workload: {args.turns} turns, one {FACT_TOKENS:,}-token finding each")
    print(f"baseline accuracy at turn 10: {base:.0%}   gate: >= {target:.0%} "
          f"at turn {args.turns}, under ${args.cost_ceiling:.2f}\n")
    print(f"{'strategy':<12}{'recall':>8}{'accuracy':>10}{'context':>11}"
          f"{'input tok':>12}{'calls':>7}{'cost':>9}  gate")
    print("-" * 78)

    results = []
    for name in STRATEGIES:
        r = evaluate(name, args.turns, quiz)
        results.append(r)
        ok = r.accuracy >= target and r.usd <= args.cost_ceiling
        print(f"{r.name:<12}{r.recall:>7.0%}{r.accuracy:>10.0%}"
              f"{r.context_tokens:>11,}{r.total_input_tokens:>12,}"
              f"{r.extra_calls:>7}{'$' + format(r.usd, '.2f'):>9}"
              f"  {'PASS' if ok else 'fail'}")

    print()
    passing = [r for r in results if r.accuracy >= target and r.usd <= args.cost_ceiling]
    if passing:
        best = min(passing, key=lambda r: r.usd)
        print(f"Cheapest strategy meeting the gate: {best.name} "
              f"({best.accuracy:.0%} accuracy, ${best.usd:.2f}).")
    else:
        print("No strategy meets the gate. Tune the parameters, or widen the ceiling "
              "and say why in the Decision Log.")
    print("\nNote what 'none' shows: it retains every fact and still loses, because "
          "retention is not recall once occupancy climbs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
