# Building AI Agents

**From zero to production.** Twenty modules, starting from no programming and no
AI experience at all.

Four foundation modules teach you what a language model actually is, get you
writing and running code, and walk you through your first call to Claude. Then
you build an AI agent by hand, and learn to test it, secure it, cost it, and
ship it.

Every technical term is defined the first time it appears — 39 definition boxes
across the twenty modules. Each module carries optional **Go deeper** sections
holding the advanced material, collapsed by default so they never get in the
way of a first read.

**[Read the course →](https://tomo6445.github.io/agentbuildercourse/)**

---

## Two halves

**The course site** — sixteen lesson pages with teaching prose, runnable code,
knowledge checks, and thirteen interactive instruments. Static HTML, no build
step to read it.

Hosted at **<https://tomo6445.github.io/agentbuildercourse/>**, or run it
locally — it works from a `file://` path with no server at all:

```bash
open docs/index.html          # or: python3 -m http.server -d docs
```

**The labs** — sixteen Python packages where every ship gate is a test.

```bash
pip install -e "labs[dev]"
pytest labs -q                # 187 tests, offline, no API key
```

---

## Start here

**Never programmed before?** Start at **F1 — What a language model actually is**.
It needs no software and no setup. Then work through F2–F4, which get you from
"what is a terminal" to a working call to Claude.

```bash
python3 -m lab00_foundations.check f2     # F2, F3, F4 each have a checker
```

The checker gives plain-language feedback, never a stack trace.

**Already code, and used an LLM API?** Skip to **M1 — The Loop**:

```bash
cp labs/lab01_tinyagent/starter/tinyagent.py labs/lab01_tinyagent/tinyagent.py
pytest labs/lab01_tinyagent -q            # twelve failures. Make them pass.
```

---

## The shape of it

| Phase | Modules | What it covers |
|---|---|---|
| **Foundations** | F1–F4 | What a model is, writing your first program, your first API call |
| **0 · Mechanics** | M1–M3 | The loop, tool design, context — all by hand, no frameworks |
| **1 · Building blocks** | M4–M6 | Choosing autonomy, the production harness, MCP |
| **2 · Making agents good** | M7–M9 | Memory, evaluation, multi-agent |
| **3 · Production** | M10–M13 | Observability, security, cost, the human interface |
| **4 · Applied** | M14–M16 | Skills and packaging, eight domains, the capstone |

63.5 hours. Skip Foundations if you already code and have used an LLM API.
Fourteen weeks as a cohort.

## Three pillars

**First principles before abstractions.** M1 is a small agent against the raw
API. Every later abstraction is mapped back to the line it replaces. Students who
understand the loop can debug any harness; students who only know a harness can
debug nothing.

**Informating, not just automating.** The spine is the Observatory — a trace
viewer built in M1 and extended for fifteen modules. By the end you aren't
guessing why an agent misbehaved; you're reading it.

**Ship gates, not quizzes.** Each module ends in a runnable suite the artifact
must pass. The M8 gate is "write the eval suite for M5's agent". The course eats
its own tail on purpose.

---

## Repository layout

```
content/        lesson sources (Markdown + course.py structure)
assets/         design system, front-end runtime, interactive widgets
tools/          build.py (content -> docs/), mdlite.py, verify_site.py
docs/           the generated site, committed so it just works
labs/           sixteen lab packages + the shared agentcourse library
```

### Working on the course

```bash
python3 tools/build.py            # regenerate docs/ from content/
python3 tools/build.py --check    # CI check: is docs/ stale?
python3 tools/verify_site.py      # 291 browser checks over the built site
python3 tools/verify_site.py --base https://tomo6445.github.io/agentbuildercourse
pytest labs -q                    # every ship gate
```

The build has **no dependencies** — a single `python3` invocation, no pip
install, no network. `docs/` is committed so the site works from a clone.

---

## Honesty about what runs offline

The labs run against a scripted model so the gates are deterministic, free, and
safe in CI. Most labs test real logic — path resolution, the MCP protocol
shapes, permission behaviour, trace diagnosis, injection screening, backoff and
circuit breaking. A few simulate model behaviour to make an exercise gradeable,
and `labs/README.md` says exactly which, and what each simulation cannot tell
you.

Every lab also runs against the real model with `--live`.

Prices live in one table (`labs/agentcourse/cost.py`) and are inputs rather than
constants. Check current published rates before quoting any figure this course
produces.

---

## Provenance

Built from a syllabus design document. Content on the Claude API surface — model
IDs, adaptive thinking, `output_config` effort, structured outputs, context
editing versus compaction, tool search, and the Tool Runner / Agent SDK /
Managed Agents distinction — was checked against current reference material
rather than written from recall.

Where a course claim is a measurement, the lab that produces it is cited in the
lesson, and the number in the lesson is the number the lab actually prints.
