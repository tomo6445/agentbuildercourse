"""
Run the Lab 2 eval set against a tool layer and report what to fix.

    python -m lab02_tool_surgery.harness              # your tools.py
    python -m lab02_tool_surgery.harness --starter    # the flawed baseline
    python -m lab02_tool_surgery.harness --compare    # both, side by side
"""

from __future__ import annotations

import argparse
import importlib

from .evalset import TASKS
from .surrogate import simulate

PASS_TARGET = 0.85


def evaluate(registry) -> dict:
    outcomes = [(t, simulate(t, registry)) for t in TASKS]
    passed = sum(1 for _, o in outcomes if o.passed)
    by_class: dict = {}
    for t, o in outcomes:
        if not o.passed:
            by_class.setdefault(o.failure_class, []).append((t.id, o.reason))
    return {
        "pass_rate": passed / len(TASKS),
        "passed": passed,
        "total": len(TASKS),
        "definition_tokens": registry.definition_tokens,
        "tokens_per_task": sum(o.tokens for _, o in outcomes) / len(outcomes),
        "tool_count": len(registry),
        "failures_by_class": by_class,
        "outcomes": outcomes,
    }


def load(which: str):
    mod = importlib.import_module(
        f"lab02_tool_surgery.{'starter.tools' if which == 'starter' else 'tools'}"
    )
    return mod.registry()


def report(name: str, result: dict, verbose: bool = True) -> None:
    print(f"\n=== {name} ===")
    print(f"pass rate          {result['pass_rate']:.0%} "
          f"({result['passed']}/{result['total']})")
    print(f"tools              {result['tool_count']}")
    print(f"definition tokens  {result['definition_tokens']:,} per turn")
    print(f"tokens per task    {result['tokens_per_task']:,.0f}")
    if verbose and result["failures_by_class"]:
        print("\nfailures:")
        for cls, rows in sorted(result["failures_by_class"].items()):
            print(f"  {cls} ({len(rows)})")
            for tid, reason in rows:
                print(f"    {tid}  {reason}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--starter", action="store_true", help="grade the flawed baseline")
    ap.add_argument("--compare", action="store_true", help="grade both")
    args = ap.parse_args(argv)

    if args.compare:
        base = evaluate(load("starter"))
        fixed = evaluate(load("tools"))
        report("baseline (starter/tools.py)", base)
        report("yours (tools.py)", fixed)
        print(f"\ndelta: pass {base['pass_rate']:.0%} -> {fixed['pass_rate']:.0%}   "
              f"definition tokens {base['definition_tokens']:,} -> "
              f"{fixed['definition_tokens']:,} "
              f"({(fixed['definition_tokens'] / base['definition_tokens'] - 1):+.0%})")
        ok = (fixed["pass_rate"] >= PASS_TARGET
              and fixed["definition_tokens"] < base["definition_tokens"])
        print("GATE:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    which = "starter" if args.starter else "tools"
    result = evaluate(load(which))
    report(which, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
