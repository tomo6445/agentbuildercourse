# Labs

Sixteen lab packages, one per module. Every ship gate in the course is a test in
here.

```bash
pip install -e "labs[dev]"
pytest labs -q                    # the whole course's gates
pytest labs/lab07_memory -q       # one module
```

## They run offline, on purpose

The base install has **no dependencies**. Labs run against `ScriptedModel`, which
mimics the Messages API wire format closely enough that the loop you write here
is the loop you would write live — same content blocks, same stop reasons, same
`usage` fields. That means the gates are deterministic, free, and safe in CI.

To run against the real model:

```bash
pip install -e "labs[live]"
export ANTHROPIC_API_KEY=...       # or: ant auth login
pytest labs -q --live
```

## What is simulated, and what that costs you

Being straight about this matters, because a lab that quietly pretends to
measure a model teaches the wrong confidence.

| Lab | Simulated | Honest limitation |
|---|---|---|
| 2 | A surrogate that scores tool definitions against the M2 rubric | It detects mechanical failures (missing enums, undescribed parameters, undocumented failure semantics). It cannot tell you your tools are *good*. |
| 3 | A context-rot curve | Reproduces the *shape* — gradual degradation with occupancy — not any model's actual curve. |
| 4 | A classifier whose cheap path breaks ties arbitrarily and whose careful path uses primary intent | The cost and latency ordering follows from the architecture; the absolute accuracies do not transfer. |
| 8 | A judge with the documented biases (verbosity, punishing abstention, ignoring source quality) | Deterministic so the exercise is reproducible. |
| 9 | Worker findings over a small corpus | The curve shape transfers; the knee does not — measure it on your own task. |

Labs 1, 5, 6, 7, 10, 11, 12, 13, 14, 15 and 16 test **real logic**: the agent
loop, path resolution, the MCP protocol shapes, permission and hook behaviour,
trace diagnosis, injection screening, backoff and circuit breaking, approval
design, skill validation, and the capstone checklist. Nothing is simulated there
because nothing needs to be.

## Taking a lab rather than reading it

Labs 1 and 2 ship complete so the repository is green and you have a reference.
To do them yourself:

```bash
cd labs/lab01_tinyagent && cp starter/tinyagent.py tinyagent.py
pytest labs/lab01_tinyagent -q            # 12 failures. Make them pass.
git checkout labs/lab01_tinyagent/tinyagent.py     # restore the reference
```

## The shared library

`agentcourse/` is what every lab builds on:

| Module | What it holds |
|---|---|
| `model.py` | `ScriptedModel`, `LiveModel`, content blocks, script builders |
| `tools.py` | `@tool` (schemas from docstrings), `ToolRegistry`, dispatch |
| `loop.py` | The reference agent loop with budget, trace and oscillation detection |
| `trace.py` | The record the Observatory reads |
| `cost.py` | Pricing in one table, `Budget`, and the quadratic-history projection |
| `evals.py` | Eval cases, pass *rates* rather than pass/fail, Cohen's kappa |

Prices in `cost.py` are inputs, not constants. Check current published rates
before quoting any figure the labs produce.
