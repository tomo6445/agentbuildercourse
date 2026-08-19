"""
Lab 4 — build the comparison table, then write the memo.

    python -m lab04_patterns.compare
"""

from __future__ import annotations

import inspect
import statistics
from pathlib import Path

from agentcourse.cost import PRICES

from .patterns import PATTERNS
from .tickets import TICKETS

MODEL = "claude-sonnet-5"


def measure(name: str) -> dict:
    fn = PATTERNS[name]
    decisions = [fn(t) for t in TICKETS]

    correct = sum(d.category == t.gold for d, t in zip(decisions, TICKETS))
    esc_correct = sum(d.escalate == t.escalate for d, t in zip(decisions, TICKETS))
    latencies = sorted(d.latency_ms for d in decisions)
    price = PRICES[MODEL]
    usd = sum(d.input_tokens * price["input"] + d.output_tokens * price["output"]
              for d in decisions) / 1e6

    return {
        "pattern": name,
        "accuracy": correct / len(TICKETS),
        "escalation_accuracy": esc_correct / len(TICKETS),
        "calls_per_ticket": statistics.mean(d.calls for d in decisions),
        "p50_ms": latencies[len(latencies) // 2],
        "p95_ms": latencies[int(len(latencies) * 0.95)],
        "usd_per_1k": usd / len(TICKETS) * 1000,
        "loc": len(inspect.getsource(fn).splitlines()),
    }


def main() -> int:
    rows = [measure(name) for name in PATTERNS]

    print(f"{'pattern':<22}{'acc':>6}{'esc':>6}{'calls':>7}{'p50':>7}{'p95':>7}"
          f"{'$/1k':>9}{'LOC':>5}")
    print("-" * 69)
    for r in rows:
        print(f"{r['pattern']:<22}{r['accuracy']:>6.0%}{r['escalation_accuracy']:>6.0%}"
              f"{r['calls_per_ticket']:>7.1f}{r['p50_ms']:>7.0f}{r['p95_ms']:>7.0f}"
              f"{'$' + format(r['usd_per_1k'], '.2f'):>9}{r['loc']:>5}")

    best_acc = max(rows, key=lambda r: r["accuracy"])
    agent = next(r for r in rows if r["pattern"] == "autonomous_agent")
    route = next(r for r in rows if r["pattern"] == "routing")

    print(f"\nBest accuracy: {best_acc['pattern']} ({best_acc['accuracy']:.0%})")
    print(f"Routing vs the agent: {route['accuracy']:.0%} at "
          f"${route['usd_per_1k']:.2f}/1k against {agent['accuracy']:.0%} at "
          f"${agent['usd_per_1k']:.2f}/1k "
          f"({agent['usd_per_1k'] / route['usd_per_1k']:.1f}x the cost).")

    memo = Path("MEMO.md")
    if not memo.exists():
        print(f"\nNow write {memo}: which pattern, what numbers support it, and "
              f"what evidence would change your mind. This is your first graded "
              f"Decision Log entry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
