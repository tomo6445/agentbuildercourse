---
name: invoice-reconciliation
description: >
  Reconciles supplier invoices against purchase orders and delivery notes.
  Use when the user mentions invoice reconciliation, matching invoices to POs,
  three-way match, supplier payment discrepancies, or month-end AP close.
  Covers pulling the ledger export, running the match, and producing the
  exceptions report finance needs before payment runs.
---

# Invoice reconciliation

## When to use this
The user wants supplier invoices matched against purchase orders and delivery
notes, or is closing accounts payable for a period.

## Process
1. Confirm the period and the entity with the user.
2. Run `scripts/pull_ledger.py --period YYYY-MM` to produce `ledger.json`.
3. Run `scripts/three_way_match.py` and resolve every warning before continuing.
4. Draft the exceptions report using `reference/exceptions-format.md`.

## House rules
- Never net an over-billing against an under-billing across suppliers.
- Any variance over 2% goes to the exceptions report, not to a judgement call.

## Files
- `reference/exceptions-format.md` — the report layout finance expects
- `scripts/pull_ledger.py` — ledger extraction
- `scripts/three_way_match.py` — the match, and the checks finance runs
