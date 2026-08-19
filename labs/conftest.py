"""Shared pytest configuration for every lab.

Labs run offline by default. Anything marked `live` needs a real API key and is
deselected unless you pass --live, so `pytest labs` is deterministic and free.
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--live", action="store_true", default=False,
        help="also run tests marked `live` against the real Claude API",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="needs --live and ANTHROPIC_API_KEY")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
