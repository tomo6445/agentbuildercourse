"""
Lab 12b — chaos, and the three things that stop a retry storm.

Jittered backoff, a circuit breaker, and a budget guard. You need all three:
backoff spreads the retries, the breaker stops calling a service that is down,
and the guard bounds the damage when both are wrong.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


class Down(Exception):
    """The dependency failed."""


class BudgetBlown(Exception):
    """The guard stopped the run. Cheaper than the alternative."""


def backoff_delay(attempt: int, *, base: float = 1.0, cap: float = 60.0,
                  rng: random.Random | None = None) -> float:
    """Exponential with FULL jitter.

    Without the jitter, every client that failed together retries together, and
    you have re-created the original spike on a timer.
    """
    rng = rng or random
    return rng.uniform(0, min(cap, base * 2 ** attempt))


class CircuitBreaker:
    """Stop calling a service that is down. Retrying a hard-down dependency is
    load you are generating against yourself."""

    def __init__(self, threshold: int = 5, recovery_s: float = 30.0):
        self.threshold, self.recovery_s = threshold, recovery_s
        self.failures, self.opened_at = 0, None

    def allow(self, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        if self.opened_at is not None and now - self.opened_at > self.recovery_s:
            self.opened_at, self.failures = None, 0      # half-open: try one
        return self.opened_at is None

    def record(self, ok: bool, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        if ok:
            self.failures, self.opened_at = 0, None
            return
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = now

    @property
    def state(self) -> str:
        return "open" if self.opened_at is not None else "closed"


@dataclass
class FaultProxy:
    """Injects the faults a real dependency produces."""

    timeout_rate: float = 0.0
    error_rate: float = 0.0
    malformed_rate: float = 0.0
    rate_limit_after: int | None = None
    seed: int = 20260819
    calls: int = 0
    _rng: random.Random = field(default=None, repr=False)

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    def call(self) -> str:
        self.calls += 1
        if self.rate_limit_after and self.calls > self.rate_limit_after:
            raise Down("429 rate limited")
        roll = self._rng.random()
        if roll < self.timeout_rate:
            raise Down("timeout")
        if roll < self.timeout_rate + self.error_rate:
            raise Down("500")
        if roll < self.timeout_rate + self.error_rate + self.malformed_rate:
            return "{not json"
        return '{"ok": true}'


@dataclass
class RunResult:
    completed: bool
    attempts: int = 0
    delays: list = field(default_factory=list)
    aborted_by: str = ""


def resilient_call(proxy: FaultProxy, breaker: CircuitBreaker, *,
                   max_attempts: int = 6, budget_attempts: int = 20,
                   spent: list | None = None,
                   rng: random.Random | None = None,
                   clock: float = 0.0) -> RunResult:
    """One task, retried properly."""
    rng = rng or random.Random(7)
    spent = spent if spent is not None else []
    result = RunResult(False)

    for attempt in range(max_attempts):
        if len(spent) >= budget_attempts:
            result.aborted_by = "budget guard"
            return result
        if not breaker.allow(now=clock):
            result.aborted_by = "circuit breaker"
            return result

        result.attempts += 1
        spent.append(1)
        try:
            payload = proxy.call()
            if not payload.startswith('{"'):
                raise Down("malformed payload")
        except Down:
            breaker.record(False, now=clock)
            delay = backoff_delay(attempt, rng=rng)
            result.delays.append(delay)
            clock += delay
            continue
        breaker.record(True, now=clock)
        result.completed = True
        return result

    result.aborted_by = "max attempts"
    return result


def run_chaos(tasks: int = 100, **fault_kwargs) -> dict:
    """The chaos suite: many tasks through a faulty dependency."""
    completed, aborts = 0, {}
    spent: list = []
    for i in range(tasks):
        proxy = FaultProxy(seed=20260819 + i, **fault_kwargs)
        breaker = CircuitBreaker()
        r = resilient_call(proxy, breaker, rng=random.Random(i), spent=[])
        if r.completed:
            completed += 1
        else:
            aborts[r.aborted_by] = aborts.get(r.aborted_by, 0) + 1
        spent.append(r.attempts)
    return {
        "completion_rate": completed / tasks,
        "mean_attempts": sum(spent) / tasks,
        "aborts": aborts,
    }


def main() -> int:
    for name, kwargs in (
        ("timeouts 20%", {"timeout_rate": 0.2}),
        ("500s 25%", {"error_rate": 0.25}),
        ("malformed 15%", {"malformed_rate": 0.15}),
        ("mixed", {"timeout_rate": 0.15, "error_rate": 0.15, "malformed_rate": 0.1}),
        ("429 sustained", {"rate_limit_after": 0}),
        ("hard down", {"error_rate": 1.0}),
    ):
        r = run_chaos(**kwargs)
        print(f"{name:<16} completion {r['completion_rate']:>5.0%}  "
              f"mean attempts {r['mean_attempts']:>4.1f}  aborts {r['aborts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
