"""
The Lab 14 gate: a measurable improvement, a skill that installs and works, and
a description that actually gets it retrieved.
"""

from pathlib import Path

import pytest

from .validator import lint_description, retrieval_match, validate

SKILL = Path(__file__).parent / "example_skill"

# The M14 autopsy, verbatim: same skill, two descriptions, 4% vs 90% invocation.
HUMAN_FACING = ("Comprehensive guidance for the invoice reconciliation workflow, "
                "incorporating best practices developed by the finance operations "
                "team.")
RETRIEVAL_FACING = (
    "Reconciles supplier invoices against purchase orders and delivery notes. "
    "Use when the user mentions invoice reconciliation, matching invoices to POs, "
    "three-way match, supplier payment discrepancies, or month-end AP close."
)

QUERIES = [
    "reconcile these supplier invoices against the POs",
    "can you do a three-way match for August",
    "we need the month-end AP close done",
    "there is a payment discrepancy with a supplier",
    "match invoices to purchase orders please",
]


def test_the_reference_skill_passes():
    report = validate(SKILL)
    assert report.blocking == [], [f.title for f in report.blocking]
    assert report.score >= 85


def test_a_description_written_for_humans_fails_the_lint():
    findings = lint_description(HUMAN_FACING)
    assert any(f.title == "No trigger phrasing" for f in findings), (
        "nothing tells the retriever when this applies"
    )
    assert any(f.severity == "high" for f in findings)


def test_the_rewrite_passes_without_changing_a_word_of_the_skill():
    assert not [f for f in lint_description(RETRIEVAL_FACING) if f.severity == "high"]


def test_the_rewrite_is_reached_by_how_people_actually_ask():
    """4% to 90% is a retrieval difference, not a content difference."""
    before = sum(retrieval_match(HUMAN_FACING, q) for q in QUERIES)
    after = sum(retrieval_match(RETRIEVAL_FACING, q) for q in QUERIES)
    assert before <= 1, "the human-facing description matches almost nothing"
    assert after >= 4, "the rewrite matches the phrasings users bring"


def test_progressive_disclosure_keeps_the_always_loaded_cost_small():
    report = validate(SKILL)
    assert report.always_loaded < 200, (
        "level 1 is resident for every request, so it multiplies by skill count"
    )
    assert report.l3_tokens > 0, "referenced files exist and are loaded on demand"
    assert report.l2_tokens < 3000


def test_fifty_skills_still_fit(tmp_path):
    """Unbounded capability at bounded context cost — the whole mechanism."""
    per_skill = validate(SKILL).always_loaded
    assert per_skill * 50 < 12_000, (
        f"{per_skill} tokens x 50 skills = {per_skill * 50:,}, which is no longer "
        f"bounded"
    )


def test_a_monolithic_skill_defeats_progressive_disclosure(tmp_path):
    """A 3,000-line SKILL.md loads in full the moment it is judged relevant."""
    big = tmp_path / "monolith"
    (big / "scripts").mkdir(parents=True)
    (big / "scripts" / "x.py").write_text("# script\n")
    (big / "SKILL.md").write_text(
        "---\nname: monolith\ndescription: >\n  Does the thing. Use when the user "
        "asks to generate a report or audit something.\n---\n\n"
        + ("Detailed procedure paragraph that could have lived in a reference "
           "file instead of the body. " * 400)
    )
    report = validate(big)
    assert any("body is large" in f.title for f in report.findings)
    assert any(f.severity == "high" for f in report.findings)


def test_a_skill_needs_at_least_three_files_and_a_script(tmp_path):
    thin = tmp_path / "thin"
    thin.mkdir()
    (thin / "SKILL.md").write_text(
        "---\nname: thin\ndescription: >\n  Generates the monthly report. Use when "
        "the user asks for a monthly report or month-end summary.\n---\n\nDo it.\n"
    )
    report = validate(thin)
    titles = [f.title for f in report.findings]
    assert "No bundled scripts" in titles
    assert "Fewer than three files" in titles


def test_missing_skill_md_is_reported_rather_than_crashing(tmp_path):
    report = validate(tmp_path / "nothing")
    assert report.blocking and report.blocking[0].title == "No SKILL.md"
