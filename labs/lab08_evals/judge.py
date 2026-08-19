"""
Lab 8 — LLM-as-judge, and validating it before you trust a number.

The judge here is deterministic so the lab is reproducible, and it is
deliberately built with the biases real judges have: it rewards fluency and
length, it punishes abstention, and it does not check source quality unless the
rubric tells it to. Fixing the rubric fixes the judge. Fixing the labels does
not — and the tests refuse to let you.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agentcourse.evals import cohens_kappa, validate_judge


@dataclass
class Rubric:
    """Dimensions the judge actually scores. Anything absent here is not
    measured, no matter how obvious it seems to you."""

    factual_accuracy: bool = True
    citations: bool = True
    completeness: bool = True
    source_quality: bool = False        # the dimension people forget
    reward_abstention: bool = False     # honesty must be rewarded explicitly
    length_independent: bool = False    # otherwise longer scores higher

    def describe(self) -> str:
        on = [k for k, v in self.__dict__.items() if v]
        return "scores: " + ", ".join(on)


JUNK_SOURCES = ("contentfarm", "seo-", "blogspam", "aggregator", "top10")
GOOD_SOURCES = ("10-K", "10-Q", "filing", "docs.", "annualreport", "p.")


@dataclass
class Output:
    id: str
    text: str
    human_label: int                    # the reference label, hand-assigned
    note: str = ""


def judge(output: Output, rubric: Rubric) -> int:
    """Return 1 (pass) or 0 (fail), with the biases a real judge has."""
    text = output.text
    lowered = text.lower()

    has_numbers = bool(re.search(r"\d", text))
    has_citation = bool(re.search(r"\[.*?\]|\(p\.\s*\d+\)|source:", lowered))
    junk_source = any(j in lowered for j in JUNK_SOURCES)
    abstains = bool(re.search(r"could not find|not available|no data|unable to locate",
                              lowered))
    words = len(text.split())

    if rubric.factual_accuracy and not has_numbers and not abstains:
        return 0
    if rubric.citations and not has_citation and not abstains:
        return 0
    if rubric.source_quality and junk_source:
        return 0
    if abstains:
        # Without an explicit instruction, a judge reads abstention as
        # incompleteness — and you train honesty out of your agent.
        return 1 if rubric.reward_abstention else 0
    if not rubric.length_independent and words > 25 and has_numbers:
        # Verbosity bias: long, fluent, number-bearing answers sail through
        # even when padded with irrelevance.
        return 1
    return 1 if has_numbers and has_citation else 0


# The validation set: hand-labelled BEFORE the judge was run, which is the only
# order that means anything.
OUTPUTS = [
    Output("o01", "Revenue grew 14% YoY to $2.1B [10-K p.34]. Margin fell 2pts on "
                  "freight costs [p.41].", 1, "accurate, cited, complete"),
    Output("o02", "Revenue grew strongly this year and margins were affected by "
                  "various factors.", 0, "no numbers, no citations"),
    Output("o03", "Revenue was $2.1B (+14%). Source: seo-financedigest aggregator "
                  "top10 summary.", 0, "right number, junk source"),
    Output("o04", "I could not find margin data in the filings, so I report revenue "
                  "only: $2.1B (+14%) [10-K p.34].", 1, "correct abstention"),
    Output("o05", "Revenue: $2.1B. Margin: 31%. Headcount: 4,400. Offices: 12. CEO "
                  "appointed 2019. Founded 2003. Listed 2011. HQ Boston. Segments 4.", 0,
           "padded with irrelevance, margin unsourced"),
    Output("o06", "Margin fell 2pts [p.41]; revenue $2.1B, +14% [10-K p.34]. Freight "
                  "was the driver [p.41].", 1, "same content, different order"),
    Output("o07", "Based on my analysis, revenue increased by approximately fourteen "
                  "percent year over year.", 0, "hedged, uncited"),
    Output("o08", "$2.1B revenue (+14% YoY) [p.34]; gross margin 31%, down 2pts "
                  "[p.41]; driver freight [p.41]. Confidence: high.", 1, "complete, cited"),
]


def run_validation(rubric: Rubric) -> dict:
    human = [o.human_label for o in OUTPUTS]
    machine = [judge(o, rubric) for o in OUTPUTS]
    result = validate_judge(human, machine)
    result["judge_labels"] = machine
    result["human_labels"] = human
    result["disagreements"] = [
        (o.id, o.note) for o, h, m in zip(OUTPUTS, human, machine) if h != m
    ]
    return result


NAIVE_RUBRIC = Rubric()
FIXED_RUBRIC = Rubric(source_quality=True, reward_abstention=True,
                      length_independent=True)


def main() -> int:
    for name, rubric in (("naive", NAIVE_RUBRIC), ("fixed", FIXED_RUBRIC)):
        r = run_validation(rubric)
        print(f"\n=== {name} rubric ===")
        print(rubric.describe())
        print(f"agreement {r['agreement']:.0%}   kappa {r['kappa']:.2f}   "
              f"usable {r['usable']}")
        print(f"false passes {r['false_pass']}  false fails {r['false_fail']}")
        print(f"bias: {r['bias']}")
        for oid, note in r["disagreements"]:
            print(f"  {oid}  {note}")
    print("\nRaw agreement is the number that lies: a judge that passes "
          "everything scores well on a mostly-passing set. Kappa is the one to "
          "read, and the direction of the errors tells you what to fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
