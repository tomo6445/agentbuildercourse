"""The Lab 15 gate: two implementations pass their smoke tests, and every
domain brief names the failure it punishes."""

import pytest

from .domains import (
    BY_KEY, DOMAINS, DeadMansSwitch, RunRecord, UnsafeQuery, run_query,
    scheduled_run,
)

SCHEMA = {"orders": {"id", "customer_id", "total", "created_at"},
          "customers": {"id", "name", "region"}}
ROWS = [{"total": 1200}, {"total": 800}]


def test_all_eight_domains_documented_with_their_failure_mode():
    assert len(DOMAINS) == 8
    for d in DOMAINS:
        assert d.architecture and d.bites_you
        assert len(d.controls) >= 3, f"{d.key} needs controls, not just a warning"


def test_devops_names_the_trifecta():
    assert "trifecta" in BY_KEY["devops"].bites_you
    assert any("dry-run" in c for c in BY_KEY["devops"].controls)


def test_scheduled_domain_treats_alerting_as_the_design():
    assert any("silence is the alarm" in c for c in BY_KEY["scheduled"].controls)


# ------------------------------------------------------------------- BI

def test_write_statements_are_refused():
    for sql in ("DELETE FROM orders", "update orders set total = 0",
                "DROP TABLE customers"):
        with pytest.raises(UnsafeQuery):
            run_query(sql, [], schema=SCHEMA)


def test_schema_hallucination_errors_loudly():
    """A misremembered column must fail, not return a plausible wrong answer."""
    with pytest.raises(UnsafeQuery) as exc:
        run_query("SELECT orders.revenue FROM orders", [], schema=SCHEMA)
    assert "does not exist" in str(exc.value)
    assert "total" in str(exc.value), "say what the columns actually are"


def test_a_plausible_but_wrong_number_is_flagged_not_returned_quietly():
    """The characteristic BI failure: wrong join semantics, reasonable number."""
    result = run_query(
        "SELECT orders.total FROM orders JOIN customers ON customers.id = orders.id",
        ROWS, schema=SCHEMA,
        expectations={"min_rows": 50, "total_column": "total",
                      "total_within": (900_000, 1_100_000)},
    )
    assert not result["trustworthy"]
    assert any("check the join" in w for w in result["warnings"])
    assert any("outside the expected range" in w for w in result["warnings"])


def test_the_query_always_comes_back_with_the_answer():
    result = run_query("SELECT orders.total FROM orders", ROWS, schema=SCHEMA)
    assert result["sql"].startswith("SELECT")
    assert result["trustworthy"]


# ------------------------------------------------------------ scheduled

def test_exit_code_zero_is_not_success():
    record = scheduled_run(lambda: {"rows": 0, "usd": 0.02, "freshness_hours": 1})
    assert record.status == "assertion_failed"
    assert "no rows" in record.detail


def test_stale_source_data_fails_the_run():
    record = scheduled_run(lambda: {"rows": 500, "usd": 0.02, "freshness_hours": 40})
    assert record.status == "assertion_failed"
    assert "stale" in record.detail


def test_budget_overrun_is_distinct_from_a_crash():
    record = scheduled_run(lambda: {"rows": 500, "usd": 9.0, "freshness_hours": 1})
    assert record.status == "budget"


def test_a_crash_is_reported_rather_than_swallowed():
    def boom():
        raise RuntimeError("upstream gone")
    assert scheduled_run(boom).status == "crashed"


def test_every_outcome_reports_so_silence_is_the_alarm():
    switch = DeadMansSwitch(max_silence_hours=26)
    for hour, work in ((0, lambda: {"rows": 5, "usd": 0.01, "freshness_hours": 1}),
                       (24, lambda: {"rows": 0, "usd": 0.01, "freshness_hours": 1})):
        scheduled_run(work, now_hours=hour, switch=switch)
        assert not switch.overdue(hour)

    # Now nothing runs for two days: the switch is what notices.
    assert switch.overdue(24 + 30), "a silent agent must page someone"
