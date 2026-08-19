# Lab 2 — Tool surgery

Eight CRM tools, a frozen 20-task eval set, and one rule: **only the tool layer
may change.**

```bash
cp starter/tools.py tools.py                      # take the lab (45% baseline)
python -m lab02_tool_surgery.harness              # see what is failing
python -m lab02_tool_surgery.harness --compare    # grade against the baseline
python -m lab02_tool_surgery.review               # the peer-review summary
git checkout labs/lab02_tool_surgery/tools.py     # restore the reference
```

## The gate

| | baseline | target | reference rewrite |
|---|---|---|---|
| pass rate | 45% | ≥85% | 100% |
| definition tokens/turn | 2,570 | below baseline | 1,620 (−37%) |

Both numbers must move, in opposite directions. Accuracy bought with a
thousand-word description is not a fix.

## How it is graded offline

`surrogate.py` simulates the parts of model behaviour that tool design controls:

- **selection** — matching the request against name and description, so vague or
  near-duplicate descriptions cause misselection
- **argument filling** — undescribed parameters get guessed at, closed sets typed
  as free strings get plausible-but-wrong values, opaque ids with no stated
  origin get invented
- **recovery** — an empty result is reported as "does not exist" unless the
  description says empty is not an error; a failure is retried unless the error
  says it is permanent

It is a **simulator, not a model.** It can tell you your tools are not failing in
the specific mechanical ways M2 describes. It cannot tell you they are good.
That is what the live run and a human reading transcripts are for:

```bash
pip install -e "labs[live]" && pytest labs/lab02_tool_surgery --live
```

One consequence worth naming: because selection is keyword matching, the exercise
rewards descriptions containing the words a user would actually use. That is a
simplification of how the real model selects — but it is a simplification in the
direction of the real lesson, which is that your description is read by someone
who only has the words you gave them.
