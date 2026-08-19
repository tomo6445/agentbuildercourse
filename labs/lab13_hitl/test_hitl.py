"""The Lab 13 gate: the functional checklist, in tests."""

import pytest

from .approval import (
    CODING_AGENT, RUNGS, ActionClass, ApprovalPrompt, FatigueModel,
    ladder_for_agent, rung_for, soften,
)


def test_one_agent_spans_several_rungs():
    """Rating 'the agent' as semi-autonomous produces over- and under-gating
    at the same time."""
    ladder = ladder_for_agent(CODING_AGENT)
    assert ladder["read_file"] == 5, "approving reads teaches people to click yes"
    assert ladder["commit_to_branch"] == 4, "git makes undo cheap and real"
    assert ladder["force_push_main"] <= 1
    assert ladder["send_external_email"] <= 1
    assert len(set(ladder.values())) >= 3, "a single rung for the agent is the error"


def test_reversibility_and_blast_radius_place_the_action():
    assert rung_for(ActionClass("read", "read_only", "none")) == 5
    assert rung_for(ActionClass("migrate", "none", "production")) == 1
    assert rung_for(ActionClass("refund", "costly", "customers")) == 2


def test_making_an_action_reversible_beats_gating_it():
    """A soft delete with retention is usually a few hours of work and removes
    an approval from someone's day."""
    hard = ActionClass("delete_records", "none", "production", 12)
    assert rung_for(hard) <= 1
    assert rung_for(soften(hard)) >= 4


def test_the_default_prompt_is_a_rubber_stamp_generator():
    bare = ApprovalPrompt(action="bash")
    assert not bare.decidable
    assert set(bare.missing()) == {"reason", "blast_radius", "alternative"}
    assert "[Approve] [Deny]" in bare.render()


def test_the_missing_field_is_almost_always_the_alternative():
    """Action, reason and impact are usually present in some form. Without the
    cost of declining, approval degrades into assent."""
    typical = ApprovalPrompt(
        action="rm -rf ./build/cache (in /srv/app), 340 files",
        reason="Stale cache is shadowing the dependency bump",
        blast_radius="Generated files only. No source. Regenerated next build (~40s).",
    )
    assert typical.missing() == ["alternative"]
    assert not typical.decidable


def test_a_decidable_prompt_renders_all_four_fields():
    full = ApprovalPrompt(
        action="rm -rf ./build/cache (in /srv/app), 340 files",
        reason="Stale cache is shadowing the dependency bump",
        blast_radius="Generated files only. No source. Reversible.",
        alternative="Falls back to an incremental build, which may reproduce the error.",
    )
    assert full.decidable
    rendered = full.render()
    for label in ("ACTION", "WHY", "IMPACT", "IF DENIED"):
        assert label in rendered
    assert "Approve all of this kind" in rendered, "scoped grants, not unbounded ones"


def test_approval_fatigue_is_measurable_and_becomes_ceremonial():
    light = FatigueModel(approvals_per_day=4)
    assert not light.ceremonial and light.mitigations() == []

    heavy = FatigueModel(approvals_per_day=60)
    assert heavy.ceremonial, "60 approvals a day is not review"
    assert heavy.median_decision_seconds < 2.0
    assert any("risk-tier" in m for m in heavy.mitigations())
    assert any("batch" in m for m in heavy.mitigations())


def test_tiering_removes_most_approvals_without_removing_the_control():
    """The M13 autopsy's actual fix, rather than an approve-all button."""
    before = FatigueModel(approvals_per_day=60)
    everything_asked = [a for a in CODING_AGENT]
    only_risky = [a for a in CODING_AGENT if rung_for(a) <= 2]
    after = FatigueModel(approvals_per_day=sum(a.volume_per_day for a in only_risky))

    assert len(only_risky) < len(everything_asked)
    assert after.approvals_per_day < before.approvals_per_day * 0.2
    assert not after.ceremonial, "the remaining approvals get read"
