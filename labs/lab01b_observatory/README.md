# Lab 1b — Observatory v0

A trace viewer. The most important forty minutes in the course, and it looks
like the least important.

```bash
python -m lab01b_observatory.render --demo -o observatory.html
python -m lab01b_observatory.render my-trace.json -o observatory.html
```

You extend this for the rest of the course:

- **v1 (M3)** — context occupancy timeline, cache-hit indicator
- **v2 (M8)** — side-by-side eval run comparison with per-case deltas
- **v3 (M10)** — subagent waterfall with per-span cost attribution
- **v4 (M12)** — cost by tool, subagent and turn; per-tenant budgets

The page must stay self-contained — no CDN, no external fonts — so it opens
from a `file://` path on any machine. There is a test for that.
