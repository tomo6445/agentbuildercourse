# Exceptions report format

One row per exception, sorted by absolute variance descending.

| column | meaning |
| --- | --- |
| supplier | Legal entity name as it appears on the PO |
| po | Purchase order number |
| invoice | Supplier invoice number |
| variance | Invoice total minus PO total, in the PO currency |
| category | price / quantity / timing / missing_grn |
| action | hold / query / approve_with_note |

Rows with `category = missing_grn` always go to hold, regardless of variance.
