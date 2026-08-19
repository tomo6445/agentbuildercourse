"""Deterministic three-way match. Precision matters more than judgement here,
which is exactly when a script beats instructions."""
import sys


def match(invoice, po, grn, tolerance=0.02):
    if grn is None:
        return "hold", "missing goods receipt note"
    variance = invoice["total"] - po["total"]
    if abs(variance) <= po["total"] * tolerance:
        return "approve", ""
    return "query", f"variance {variance:.2f} exceeds {tolerance:.0%}"


if __name__ == "__main__":
    print("run from the reconciliation skill", file=sys.stderr)
