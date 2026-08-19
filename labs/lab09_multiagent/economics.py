"""
Lab 9b — the economics report. Find the knee, defend a worker count.

    python -m lab09_multiagent.economics
"""

from __future__ import annotations

from agentcourse.cost import PRICES

from .orchestrator import SUBQUESTIONS, WEIGHTS, run

MODEL = "claude-sonnet-5"
TASK_VALUE_USD = 20.0


def quality(result: dict) -> float:
    """Rubric: *weighted* coverage of the sub-questions, plus credit for citing
    primary sources and for surfacing conflicts rather than hiding them.

    The weighting is what produces a knee: the first worker answers the question
    that matters, the eighth answers 'segments'.
    """
    total_weight = sum(WEIGHTS.values())
    covered = sum(WEIGHTS[q] for q in result["answer"]) / total_weight
    primary = sum(1 for c in result["citations"] if c in ("10-K", "investor-deck"))
    cited = primary / max(1, len(result["citations"]))
    surfaced = 1.0 if result["conflicts"] else 0.85
    return round(0.7 * covered + 0.2 * cited + 0.1 * surfaced, 3)


def measure(workers: int) -> dict:
    result = run(workers=workers)
    price = PRICES[MODEL]
    usd = result["tokens"] * price["input"] / 1e6
    return {"workers": workers, "quality": quality(result), "usd": usd,
            "tokens": result["tokens"], "duplicates": result["duplicate_searches"]}


def single_agent_baseline() -> dict:
    """One agent doing everything sequentially in its own context."""
    result = run(workers=1)
    price = PRICES[MODEL]
    tokens = 9_000 + 38_000            # one context, all four sub-questions
    return {"workers": 1, "quality": quality(result) * 0.92,
            "usd": tokens * price["input"] / 1e6, "tokens": tokens, "duplicates": 0}


def main() -> int:
    rows = [measure(w) for w in (1, 2, 3, 4, 6, 8)]
    print(f"{'workers':>8}{'quality':>9}{'cost':>9}{'q/$':>8}{'marginal q':>12}"
          f"{'marginal $':>12}")
    print("-" * 58)
    previous = None
    knee = None
    for r in rows:
        mq = r["quality"] - previous["quality"] if previous else None
        mc = r["usd"] - previous["usd"] if previous else None
        print(f"{r['workers']:>8}{r['quality']:>9.3f}{'$' + format(r['usd'], '.3f'):>9}"
              f"{r['quality'] / r['usd']:>8.1f}"
              f"{('+' + format(mq, '.3f')) if mq is not None else '—':>12}"
              f"{('$' + format(mc, '.3f')) if mc is not None else '—':>12}")
        if mq is not None and mq < 0.015 and knee is None:
            knee = previous["workers"]
        previous = r

    base = single_agent_baseline()
    best = max(rows, key=lambda r: r["quality"] / r["usd"])
    print(f"\nsingle-agent baseline: quality {base['quality']:.3f} at "
          f"${base['usd']:.3f}")
    print(f"knee: {knee or rows[-1]['workers']} workers — past it, each worker "
          f"buys less than 1.5 points")
    print(f"best quality per dollar: {best['workers']} workers")
    print(f"task value ${TASK_VALUE_USD:.2f}; compute at the knee is "
          f"{next(r['usd'] for r in rows if r['workers'] == (knee or 1)) / TASK_VALUE_USD:.1%} "
          f"of the take")
    print("\nThe knee is always lower than students expect. Notice your prior, "
          "then notice how wrong it was.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
