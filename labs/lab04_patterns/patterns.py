"""
Lab 4 — five workflow patterns and one agent, against the same problem.

Support-email triage. Every implementation takes the same input and returns the
same shape, so the only thing that varies is the architecture — which is what
makes the comparison table mean anything.

The measurements are simulated but the *structure* is real: each pattern makes
the model calls it would really make, so turn counts, token totals and the
resulting cost ordering reflect the architecture rather than a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CATEGORIES = ["billing", "technical", "account", "abuse", "other"]

# Signals a competent classifier keys on. Tickets carrying signals from more
# than one category are the ambiguous ones — where the patterns diverge.
SIGNALS = {
    "billing": ["invoice", "charge", "refund", "payment", "billed", "subscription", "price"],
    "technical": ["error", "crash", "timeout", "times out", "500", "broken", "bug",
                  "fails", "failing", "loading"],
    "account": ["password", "login", "sso", "seat", "permission", "access", "locked"],
    "abuse": ["spam", "phishing", "abuse", "harass", "fraud", "scam"],
}


@dataclass
class Ticket:
    id: str
    text: str
    gold: str
    escalate: bool = False


@dataclass
class Decision:
    category: str
    escalate: bool = False
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    notes: list = field(default_factory=list)


# --------------------------------------------------------------------------
# a stand-in classifier: accurate on clear signals, unreliable on ambiguity
# --------------------------------------------------------------------------

def _hits(text: str) -> dict:
    """Where each category's signals appear. Position matters: the thing a
    customer mentions first is usually the reason they wrote in."""
    lowered = text.lower()
    found: dict = {}
    for category, signals in SIGNALS.items():
        positions = []
        for signal in signals:
            m = re.search(rf"\b{re.escape(signal)}", lowered)
            if m:
                positions.append(m.start())
        if positions:
            found[category] = sorted(positions)
    return found


def _scores(text: str) -> dict:
    hits = _hits(text)
    return {c: len(hits.get(c, [])) for c in SIGNALS}


def classify(text: str, *, effort: str = "normal") -> tuple[str, float]:
    """Return (category, confidence).

    The cheap pass counts signals and breaks ties alphabetically, which is to
    say arbitrarily. The careful pass — a stronger prompt or a stronger model —
    breaks ties on *primary intent*: whichever category the customer raised
    first. That is the only difference, and it is the whole reason routing
    works: you buy the careful pass only where confidence is low.
    """
    hits = _hits(text)
    if not hits:
        return "other", 0.4

    counts = {c: len(p) for c, p in hits.items()}
    best = max(counts.values())
    winners = sorted([c for c, n in counts.items() if n == best])

    if len(winners) == 1:
        return winners[0], min(1.0, 0.6 + 0.2 * best)

    if effort == "careful":
        earliest = min(winners, key=lambda c: hits[c][0])
        return earliest, 0.75
    return winners[0], 0.45          # alphabetical: a coin flip with a straight face


def needs_escalation(text: str) -> bool:
    return bool(re.search(r"legal|lawyer|cancel|churn|breach|gdpr|urgent",
                          text, re.I))


# --------------------------------------------------------------------------
# the six implementations
# --------------------------------------------------------------------------

TOK_IN, TOK_OUT, MS = 900, 120, 420          # one model call, roughly


def single_call(ticket: Ticket) -> Decision:
    """The floor: one call, no orchestration. Everything else must beat this."""
    cat, _ = classify(ticket.text)
    return Decision(cat, needs_escalation(ticket.text), 1, TOK_IN, TOK_OUT, MS)


def prompt_chaining(ticket: Ticket) -> Decision:
    """Fixed steps: normalise, classify, then check escalation."""
    cleaned = re.sub(r"\s+", " ", ticket.text).strip()
    cat, _ = classify(cleaned)
    esc = needs_escalation(cleaned)
    return Decision(cat, esc, 3, TOK_IN * 3, TOK_OUT * 3, MS * 3,
                    ["normalise", "classify", "escalation check"])


def routing(ticket: Ticket) -> Decision:
    """Classify cheaply, then hand to a specialised handler.

    The pattern most teams should have used. The cheap pass handles the clear
    majority; only low-confidence tickets pay for the careful pass.
    """
    cat, confidence = classify(ticket.text)
    calls, tin, tout = 1, TOK_IN, TOK_OUT
    notes = [f"routed to {cat} (confidence {confidence:.2f})"]

    if confidence < 0.6:
        cat, confidence = classify(ticket.text, effort="careful")
        calls, tin, tout = calls + 1, tin + TOK_IN, tout + TOK_OUT
        notes.append(f"low confidence, careful pass -> {cat}")

    esc = needs_escalation(ticket.text)
    return Decision(cat, esc, calls, tin, tout, MS * calls, notes)


def parallel_voting(ticket: Ticket) -> Decision:
    """Three independent classifications, majority wins.

    Buys confidence on judgement calls, at three times the cost. Disagreement is
    itself a signal worth surfacing.
    """
    votes = [classify(ticket.text)[0],
             classify(ticket.text, effort="careful")[0],
             classify(ticket.text)[0]]
    winner = max(set(votes), key=votes.count)
    disagreed = len(set(votes)) > 1
    return Decision(winner, needs_escalation(ticket.text) or disagreed,
                    3, TOK_IN * 3, TOK_OUT * 3, MS,          # concurrent: one wall clock
                    [f"votes: {votes}"] + (["disagreement -> escalate"] if disagreed else []))


def orchestrator_workers(ticket: Ticket) -> Decision:
    """A lead decomposes, workers check each category, the lead synthesises.

    Genuinely more capable on hard input, and it pays five model calls for a
    decision one call usually gets right.
    """
    lead_calls = 2                                        # plan + synthesise
    worker_results = {c: _scores(ticket.text)[c] for c in SIGNALS}
    workers = len(worker_results)
    cat = max(worker_results, key=lambda c: (worker_results[c], -CATEGORIES.index(c)))
    if worker_results[cat] == 0:
        cat = "other"
    calls = lead_calls + workers
    return Decision(cat, needs_escalation(ticket.text), calls,
                    TOK_IN * calls, TOK_OUT * calls, MS * 3,
                    [f"{workers} workers, lead synthesis"])


def evaluator_optimiser(ticket: Ticket, max_rounds: int = 3) -> Decision:
    """Classify, critique, revise — capped, because the loop must terminate on
    a budget rather than on satisfaction."""
    cat, confidence = classify(ticket.text)
    calls, notes = 1, []
    for round_no in range(max_rounds):
        if confidence >= 0.6:
            break
        cat, confidence = classify(ticket.text, effort="careful")
        calls += 2                                        # critique + revise
        notes.append(f"round {round_no + 1}: revised to {cat}")
    return Decision(cat, needs_escalation(ticket.text), calls,
                    TOK_IN * calls, TOK_OUT * calls, MS * calls, notes)


def autonomous_agent(ticket: Ticket) -> Decision:
    """An open-ended loop: look things up until it decides it is done.

    Unpredictable step count, and on a task this well-bounded the extra turns
    mostly re-examine what the first turn already established.
    """
    calls, cat = 1, None
    confidence = 0.0
    while calls < 8:
        cat, confidence = classify(ticket.text, effort="careful" if calls > 1 else "normal")
        calls += 1
        if confidence >= 0.7:
            break
    return Decision(cat, needs_escalation(ticket.text), calls,
                    # A loop re-sends its transcript: input grows every turn.
                    sum(TOK_IN + 700 * i for i in range(calls)),
                    TOK_OUT * calls, MS * calls,
                    [f"{calls} turns before settling"])


PATTERNS = {
    "single_call": single_call,
    "prompt_chaining": prompt_chaining,
    "routing": routing,
    "parallel_voting": parallel_voting,
    "orchestrator_workers": orchestrator_workers,
    "evaluator_optimiser": evaluator_optimiser,
    "autonomous_agent": autonomous_agent,
}
