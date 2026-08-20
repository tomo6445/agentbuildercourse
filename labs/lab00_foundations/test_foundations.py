"""
The foundations gate.

Two jobs: confirm the worked answers are correct, and confirm the checker is
*kind* — because a beginner who meets a stack trace on day three concludes they
cannot do this, and they are wrong.
"""

import io
import contextlib

import pytest

from . import check as checker
from . import solutions


# ------------------------------------------------------- the worked answers

def test_f2_answers():
    assert solutions.MY_NAME
    assert solutions.GREETING == "Hello, Ada. Welcome."


@pytest.mark.parametrize("temp,want", [(4, True), (9, True), (10, False), (20, False)])
def test_is_cold(temp, want):
    assert solutions.is_cold(temp) is want


@pytest.mark.parametrize("start,want", [(3, [3, 2, 1]), (1, [1]), (0, [])])
def test_count_down_terminates(start, want):
    assert solutions.count_down(start) == want


def test_total_tokens():
    assert solutions.total_tokens(
        [{"name": "a", "tokens": 100}, {"name": "b", "tokens": 250}]) == 350
    assert solutions.total_tokens([]) == 0


def test_describe_converts_the_number_to_text():
    assert solutions.describe({"name": "Ada", "age": 36}) == "Ada is 36 years old"


def test_cost_of():
    assert solutions.cost_of(1_000_000, 5.00) == 5.0
    assert solutions.cost_of(500, 5.00) == 0.0025


def test_ask_claude_sends_the_right_shape():
    fake = checker.FakeClient()
    reply = solutions.ask_claude(fake, "What is the capital of Norway?")

    assert reply == "Oslo is the capital of Norway."
    sent = fake.messages.calls[0]
    assert sent["model"] == "claude-opus-5"
    assert sent["max_tokens"] > 0
    assert sent["messages"] == [
        {"role": "user", "content": "What is the capital of Norway?"}
    ], "the question must be passed through, not hard-coded"


def test_call_cost():
    assert solutions.call_cost(checker._FakeUsage()) == pytest.approx(0.0175)


# ------------------------------------------------------- the checker itself

def run_check(module, monkeypatch, module_under_test, offline=True):
    """Run a check against a given module and capture what the student sees."""
    monkeypatch.setattr(checker, "load_exercises", lambda r: module_under_test)
    args = type("A", (), {"offline": offline})()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = checker.CHECKS[module](args)
    return code, out.getvalue()


def test_the_solutions_pass_every_check(monkeypatch):
    for module in ("f2", "f3", "f4"):
        code, output = run_check(module, monkeypatch, solutions)
        assert code == 0, f"{module} failed:\n{output}"
        assert "All " in output and "passed" in output


def test_an_unfinished_file_fails_but_kindly(monkeypatch):
    from . import exercises
    code, output = run_check("f3", monkeypatch, exercises)

    assert code == 1, "the starter file must not pass"
    assert "Traceback" not in output, "a beginner must never see a stack trace here"
    assert "gave nothing back" in output, "say what happened in plain words"
    assert "return" in output, "say what to do about it"
    assert "Look at:" in output, "say where to look"
    assert "Nothing here is a trick" in output, "and do not leave them feeling stupid"


def test_one_message_per_function_not_one_per_example(monkeypatch):
    """Four identical failures for one mistake is the wall of text we avoid."""
    from . import exercises
    _, output = run_check("f3", monkeypatch, exercises)
    # Count the failure markers, not the words: each failure is printed once
    # inline and once again in the closing summary, which is intentional.
    markers = output.count(checker.CROSS)
    assert markers == 5, (
        f"expected one failure line per unfinished function (5), got {markers}:\n"
        + output
    )


def test_a_syntax_error_is_explained_rather_than_dumped(monkeypatch, tmp_path):
    """The most common beginner failure of all: a missing quote or colon."""
    results = checker.Results()

    def raiser(r):
        try:
            compile("def broken(:\n    pass\n", "exercises.py", "exec")
        except SyntaxError as exc:
            r.fail(f"Your exercises.py has a typing mistake on line {exc.lineno}.",
                   "Python calls this a SyntaxError. It usually means a missing "
                   "quote\nmark, a missing bracket, or a missing colon.",
                   f"exercises.py, line {exc.lineno}")
        return None

    monkeypatch.setattr(checker, "load_exercises", raiser)
    args = type("A", (), {"offline": True})()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = checker.CHECKS["f3"](args)
    text = out.getvalue()

    assert code == 1
    assert "typing mistake" in text
    assert "missing" in text
    assert "Traceback" not in text


def test_f4_offline_costs_nothing(monkeypatch):
    code, output = run_check("f4", monkeypatch, solutions, offline=True)
    assert code == 0
    assert "cost nothing" in output
    assert "API key" not in output, "offline must not demand a key"
