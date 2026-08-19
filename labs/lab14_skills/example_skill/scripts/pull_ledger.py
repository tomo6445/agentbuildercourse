"""Ledger extraction. Bundled because the export format is fiddly and stable."""


def pull(period: str) -> dict:
    return {"period": period, "rows": []}
