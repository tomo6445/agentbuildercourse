"""
Lab 13 — the autonomy ladder and the approval prompt.

Two claims from M13, made testable:

  1. A rung is chosen per ACTION CLASS, not per agent. One agent spans four.
  2. "Agent wants to run: bash / [Approve] [Deny]" is a rubber-stamp generator.
     Four fields make a decision possible, and the one everyone omits is the
     fourth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

RUNGS = [
    "suggest only",
    "approve each action",
    "approve risky actions",
    "act and notify",
    "act with undo",
    "fully autonomous",
]

REVERSIBILITY = {"none": 0, "costly": 1, "cheap": 2, "read_only": 3}
BLAST = {"none": 0, "self": 1, "customers": 2, "production": 3}


@dataclass
class ActionClass:
    name: str
    reversibility: str
    blast_radius: str
    volume_per_day: int = 10


def rung_for(action: ActionClass) -> int:
    """Reversibility and blast radius place an action on the ladder."""
    r, b = REVERSIBILITY[action.reversibility], BLAST[action.blast_radius]
    if r == 3 and b == 0:
        return 5                              # read-only: approving it teaches yes-clicking
    if r == 2:
        # Cheap, real undo dominates blast radius: that is exactly what earns
        # "act with undo", and it is why making an action reversible is usually
        # a better investment than gating it.
        return 4
    if r == 1 and b <= 2:
        return 2                              # tier it: small auto, large approved
    if r == 0 and b >= 2:
        return 1                              # irreversible and wide
    if r == 0:
        return 1
    return 3


def soften(action: ActionClass) -> ActionClass:
    """Turning an irreversible action into a reversible one is usually cheaper
    than gating it: a soft delete with retention moves a rung-2 action to rung-5.
    """
    if action.reversibility == "none":
        return ActionClass(f"{action.name} (soft, 30-day retention)",
                           "cheap", action.blast_radius, action.volume_per_day)
    return action


@dataclass
class ApprovalPrompt:
    action: str = ""            # concretely, not "bash"
    reason: str = ""            # what the agent believes this accomplishes
    blast_radius: str = ""      # what changes, for whom, reversibly or not
    alternative: str = ""       # what happens if you decline

    REQUIRED = ("action", "reason", "blast_radius", "alternative")

    def missing(self) -> list:
        return [f for f in self.REQUIRED if not getattr(self, f).strip()]

    @property
    def decidable(self) -> bool:
        return not self.missing()

    def render(self) -> str:
        if not self.decidable:
            return ("Agent wants to run: " + (self.action or "bash") +
                    "\n[Approve] [Deny]")
        return (f"ACTION      {self.action}\n"
                f"WHY         {self.reason}\n"
                f"IMPACT      {self.blast_radius}\n"
                f"IF DENIED   {self.alternative}\n"
                f"[Approve]  [Approve all of this kind]  [Deny]  [Edit]")


@dataclass
class FatigueModel:
    """Approval fatigue is a security failure mode, so measure it.

    Under about two seconds of median decision time the control is ceremonial:
    still on the architecture diagram, still producing an audit trail, no longer
    doing anything.
    """

    approvals_per_day: int
    seconds_per_decision: float = 9.0

    @property
    def median_decision_seconds(self) -> float:
        # Decision time collapses as volume rises.
        if self.approvals_per_day <= 5:
            return self.seconds_per_decision
        decay = min(0.85, (self.approvals_per_day - 5) / 60)
        return round(self.seconds_per_decision * (1 - decay), 2)

    @property
    def ceremonial(self) -> bool:
        return self.median_decision_seconds < 2.0

    def mitigations(self) -> list:
        out = []
        if self.approvals_per_day > 25:
            out.append("risk-tier so only genuinely risky actions interrupt")
            out.append("batch: one considered decision beats twelve reflexes")
            out.append("learn an allow-list from what has already been approved")
            out.append("scope grants by kind and session, not forever and everywhere")
        return out


def ladder_for_agent(actions: list) -> dict:
    """One agent, several rungs. Rating "the agent" is a category error."""
    return {a.name: rung_for(a) for a in actions}


CODING_AGENT = [
    ActionClass("read_file", "read_only", "none", 400),
    ActionClass("run_tests", "read_only", "none", 60),
    ActionClass("commit_to_branch", "cheap", "self", 20),
    ActionClass("force_push_main", "none", "production", 1),
    ActionClass("send_external_email", "none", "customers", 4),
]
