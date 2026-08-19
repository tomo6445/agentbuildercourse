"""
Lab 14 — will this skill ever load, and what does it cost when it does?

Two things get measured: whether the description works as a *retrieval key*, and
whether progressive disclosure is actually being used or whether the whole skill
loads the moment it is judged relevant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from agentcourse.model import estimate_tokens

TRIGGER = re.compile(r"use (?:this|it) when|when the user|when you (?:need|are)|"
                     r"for when|whenever", re.I)
FIRST_PERSON = re.compile(r"\b(I|we|our|you should|please)\b")


@dataclass
class Finding:
    severity: str          # high | med | low | ok
    title: str
    detail: str


@dataclass
class SkillReport:
    findings: list = field(default_factory=list)
    score: int = 0
    l1_tokens: int = 0
    l2_tokens: int = 0
    l3_tokens: int = 0

    @property
    def blocking(self) -> list:
        return [f for f in self.findings if f.severity == "high"]

    @property
    def always_loaded(self) -> int:
        """Level 1 is resident for every request, whether or not the skill is
        used. This is the number that multiplies by your skill count."""
        return self.l1_tokens


def lint_description(description: str) -> list:
    f: list = []
    d = description.strip()

    if len(d) < 25:
        f.append(Finding("high", "Far too short",
                         "There is nothing here to match a user's phrasing against."))
    elif len(d) < 80:
        f.append(Finding("med", "Short",
                         "Two or three sentences: what it does, when to use it, "
                         "what it covers."))
    if len(d) > 700:
        f.append(Finding("low", "Long",
                         "Loaded on every request. Move detail into the body — "
                         "that is what progressive disclosure is for."))
    if not TRIGGER.search(d):
        f.append(Finding("high", "No trigger phrasing",
                         "Add an explicit 'Use when…' naming the words a user "
                         "would actually type. This single sentence is the "
                         "difference between 4% and 90% invocation."))
    if not re.search(r"\b\w*(report|invoice|migration|review|deploy|test|analy|"
                     r"summar|format|extract|generate|audit|draft|reconcil)\w*\b",
                     d, re.I):
        f.append(Finding("med", "No concrete domain nouns",
                         "Retrieval matches on specifics. Name the artefacts, "
                         "systems and verbs involved."))
    if FIRST_PERSON.search(d):
        f.append(Finding("low", "First or second person",
                         "Write it in the third person — it is read by a "
                         "retriever, not a colleague."))
    if len(d.split()) < 12:
        f.append(Finding("med", "Very few tokens to match on",
                         "Synonyms matter: someone saying 'month-end close' "
                         "should reach a skill that says 'monthly report'."))
    return f


def parse_skill(path: Path) -> dict:
    """Read a SKILL.md: frontmatter, body, and referenced files."""
    text = Path(path).read_text()
    meta: dict = {}
    body = text

    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        key = None
        for line in front.strip().splitlines():
            if re.match(r"^\s+", line) and key:
                meta[key] += " " + line.strip()
            elif ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                meta[key] = value.strip().lstrip(">").strip()

    referenced = re.findall(r"`([\w./-]+\.(?:md|py|sh|json|csv))`", body)
    return {"meta": meta, "body": body.strip(), "referenced": sorted(set(referenced))}


def validate(skill_dir: Path) -> SkillReport:
    skill_dir = Path(skill_dir)
    md = skill_dir / "SKILL.md"
    report = SkillReport()

    if not md.exists():
        report.findings.append(Finding("high", "No SKILL.md", "A skill is a folder "
                                       "with a SKILL.md at its root."))
        return report

    parsed = parse_skill(md)
    meta, body = parsed["meta"], parsed["body"]

    if "name" not in meta:
        report.findings.append(Finding("high", "No name in frontmatter", ""))
    description = meta.get("description", "")
    if not description:
        report.findings.append(Finding("high", "No description",
                                       "This is the retrieval key. Without it the "
                                       "skill never loads."))
    else:
        report.findings.extend(lint_description(description))

    # -- progressive disclosure ------------------------------------------
    report.l1_tokens = estimate_tokens(meta.get("name", "") + " " + description)
    report.l2_tokens = estimate_tokens(body)
    report.l3_tokens = sum(
        estimate_tokens((skill_dir / ref).read_text())
        for ref in parsed["referenced"] if (skill_dir / ref).exists()
    )

    if report.l2_tokens > 3000:
        report.findings.append(Finding(
            "high", "SKILL.md body is large",
            f"{report.l2_tokens:,} tokens load in full the moment the skill is "
            f"judged relevant. Keep the body to what is needed to decide and to "
            f"start; put detail in referenced files."))
    if not parsed["referenced"] and report.l2_tokens > 1200:
        report.findings.append(Finding(
            "med", "No referenced files",
            "Everything is in the body, so there is no level 3 and progressive "
            "disclosure is not doing anything."))

    scripts = list(skill_dir.glob("scripts/*"))
    if not scripts:
        report.findings.append(Finding(
            "low", "No bundled scripts",
            "Deterministic, precision-critical steps belong in code the agent "
            "runs, not in prose it interprets."))

    files = [p for p in skill_dir.rglob("*") if p.is_file()]
    if len(files) < 3:
        report.findings.append(Finding("med", "Fewer than three files",
                                       "The lab requires at least three."))

    if not report.findings:
        report.findings.append(Finding("ok", "Nothing flagged",
                                       "Now validate it the only way that counts: "
                                       "run the eval set and count how often it "
                                       "actually loads."))

    report.score = max(0, 100
                       - 30 * sum(f.severity == "high" for f in report.findings)
                       - 14 * sum(f.severity == "med" for f in report.findings)
                       - 5 * sum(f.severity == "low" for f in report.findings))
    return report


def retrieval_match(description: str, query: str) -> bool:
    """Would this description be reached by how the user actually phrased it?"""
    stop = {"the", "a", "an", "for", "of", "to", "my", "our", "this", "that", "and"}
    d = {w for w in re.findall(r"[a-z]+", description.lower()) if w not in stop}
    q = {w for w in re.findall(r"[a-z]+", query.lower()) if w not in stop}
    return len(d & q) >= 2
