"""
Cost modelling (M12).

Prices change. They live in one table here so that when they move you edit one
file, and so the labs never hard-code a number into an assertion. Check the
current published rates before quoting any figure this module produces.
"""

from __future__ import annotations

from dataclasses import dataclass

# Per million tokens. Verify against current published pricing before using
# these numbers for anything that matters.
PRICES = {
    "claude-opus-5":    {"input": 5.00,  "output": 25.00},
    "claude-sonnet-5":  {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00,  "output": 5.00},
    "claude-fable-5":   {"input": 10.00, "output": 50.00},
    "scripted":         {"input": 3.00,  "output": 15.00},   # the offline default
}

# Cache reads are roughly a tenth of the input price; writing the cache costs a
# little more than a normal input token. Ratios, so they survive a price change.
CACHE_READ_RATIO = 0.10
CACHE_WRITE_RATIO = 1.25


def price_of(model: str) -> dict:
    if model not in PRICES:
        # Unknown models fall back to a mid-tier price rather than crashing a
        # cost dashboard. The lab prints a warning; production should not guess.
        return PRICES["claude-sonnet-5"]
    return PRICES[model]


def turn_cost(usage, model: str = "scripted") -> float:
    """Cost of one turn in USD, accounting for cache reads and writes."""
    p = price_of(model)
    fresh_in = getattr(usage, "input_tokens", 0)
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0)

    return (
        fresh_in * p["input"]
        + cache_read * p["input"] * CACHE_READ_RATIO
        + cache_write * p["input"] * CACHE_WRITE_RATIO
        + out * p["output"]
    ) / 1e6


@dataclass
class Budget:
    """A cap the loop can enforce, rather than one you hope holds (M1, M12).

    Both limits are real: turns are a proxy, dollars are the thing you care
    about. Whichever trips first stops the run.
    """

    max_turns: int = 10
    max_usd: float = 0.50
    turns: int = 0
    usd: float = 0.0

    def charge(self, usage, model: str = "scripted") -> float:
        self.turns += 1
        cost = turn_cost(usage, model)
        self.usd += cost
        return cost

    @property
    def exhausted(self) -> bool:
        return self.turns >= self.max_turns or self.usd >= self.max_usd

    @property
    def reason(self) -> str:
        if self.turns >= self.max_turns:
            return f"turn cap reached ({self.turns}/{self.max_turns})"
        if self.usd >= self.max_usd:
            return f"budget reached (${self.usd:.4f}/${self.max_usd:.2f})"
        return ""


def project(*, tasks_per_day: int, turns_per_task: int, stable_prefix_tokens: int,
            growth_per_turn: int, output_per_turn: int,
            model: str = "claude-sonnet-5", cached: bool = True,
            subagents: int = 0) -> dict:
    """Project cost per task, day and month, and name the dominant term (M12).

    The point of this function is the `history` term: on turn n you re-send the
    whole transcript, so history accumulates as n(n-1)/2 — quadratic in turn
    count, not linear. That is why halving turns beats halving the price.
    """
    p = price_of(model)
    n = max(1, turns_per_task)

    prefix_tokens = stable_prefix_tokens * n
    history_tokens = growth_per_turn * (n * (n - 1) // 2)
    output_tokens = output_per_turn * n

    if cached:
        prefix_cost = (
            stable_prefix_tokens * p["input"] * CACHE_WRITE_RATIO
            + stable_prefix_tokens * (n - 1) * p["input"] * CACHE_READ_RATIO
        ) / 1e6
    else:
        prefix_cost = prefix_tokens * p["input"] / 1e6

    history_cost = history_tokens * p["input"] / 1e6
    output_cost = output_tokens * p["output"] / 1e6

    multiplier = 1 + subagents * 0.85
    terms = {
        "stable_prefix": prefix_cost * multiplier,
        "resent_history": history_cost * multiplier,
        "output": output_cost * multiplier,
    }
    per_task = sum(terms.values())

    return {
        "per_task": per_task,
        "per_day": per_task * tasks_per_day,
        "per_month": per_task * tasks_per_day * 30,
        "input_tokens_per_task": prefix_tokens + history_tokens,
        "terms": terms,
        "dominant_term": max(terms, key=terms.get),
        "cached": cached,
        "model": model,
    }
