# Lab 1 — tinyagent

Build the agent loop by hand. No SDK, no framework.

```bash
cp starter/tinyagent.py tinyagent.py      # take the lab
pytest labs/lab01_tinyagent -q            # 12 failures
git checkout labs/lab01_tinyagent/tinyagent.py   # restore the reference
```

## The gate

Twelve assertions. Each is a bug that shows up in real hand-written loops:

| # | Assertion |
|---|---|
| 1 | A no-tool turn returns immediately |
| 2 | The full round trip, with a continuable message list |
| 3 | The assistant turn is echoed back verbatim, not reconstructed |
| 4 | Two `tool_use` blocks in one turn both execute |
| 5 | All results return in a *single* user message, ids matching |
| 6 | An unknown tool name is rejected gracefully, listing what exists |
| 7 | A raising tool becomes an `is_error` result, not a crash |
| 8 | Malformed arguments become a result showing the expected schema |
| 9 | A permanently-failing tool terminates on the turn cap, exactly |
| 10 | A tiny budget stops the loop before the turn cap |
| 11 | `max_tokens` is a truncation, not success; `pause_turn` resumes |
| 12 | The trace round-trips through JSON and the Observatory renders it |

Tests 4, 5, 9 and 11 are the ones that catch loops which look finished.

## Running against the real model

```bash
pip install -e "labs[live]"
export ANTHROPIC_API_KEY=...        # or: ant auth login
pytest labs/lab01_tinyagent -q --live
```
