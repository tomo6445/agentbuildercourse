"""
The foundations checker.

Its job is to be *kind*. A beginner who sees a stack trace on their third day
concludes they are not cut out for this, and they are wrong. So every failure
here is a sentence in plain English that says what was expected, what happened,
and where to look.

    python3 -m lab00_foundations.check f2
    python3 -m lab00_foundations.check f3
    python3 -m lab00_foundations.check f4 [--offline]
"""

from __future__ import annotations

import argparse
import os
import platform
import sys

TICK, CROSS, INFO = "  [ok]  ", "  [--]  ", "  [ ]   "


class Results:
    def __init__(self):
        self.passed, self.failed = 0, []

    def ok(self, message: str) -> None:
        self.passed += 1
        print(TICK + message)

    def fail(self, message: str, hint: str = "", where: str = "") -> None:
        self.failed.append(message)
        print(CROSS + message)
        if hint:
            for line in hint.strip().splitlines():
                print("         " + line.strip())
        if where:
            print("         Look at: " + where)
        print()

    def note(self, message: str) -> None:
        print(INFO + message)

    def report(self, name: str) -> int:
        total = self.passed + len(self.failed)
        print()
        if not self.failed:
            print(f"  All {total} checks passed. {name} is done — move on.")
            return 0
        print(f"  {self.passed} of {total} passed. Still to fix:")
        for f in self.failed:
            print(f"    - {f}")
        print()
        print("  Nothing here is a trick. Re-read the section it came from and")
        print("  try again — this is exactly what the loop of programming is.")
        return 1


def load_exercises(r: Results):
    """Import the student's file, turning the usual failures into advice."""
    try:
        from . import exercises
        return exercises
    except SyntaxError as exc:
        r.fail(
            f"Your exercises.py has a typing mistake on line {exc.lineno}.",
            "Python calls this a SyntaxError. It usually means a missing quote\n"
            "mark, a missing bracket, or a missing colon at the end of a line\n"
            "like 'def something():' or 'if x > 3:'.\n"
            f"Python said: {exc.msg}",
            f"exercises.py, line {exc.lineno}",
        )
        return None
    except Exception as exc:                                   # noqa: BLE001
        r.fail(f"Could not read your exercises.py: {type(exc).__name__}: {exc}")
        return None


def expect_all(r: Results, label: str, fn, cases, hint="", where=""):
    """Check several examples of one function, but report at most ONE failure.

    A beginner who has not written the function yet should see one clear thing
    to fix, not the same message four times.
    """
    if fn is None:
        r.fail(f"{label} — the function is missing entirely.",
               "Check you have not deleted or renamed it.", where)
        return

    for args, want in cases:
        try:
            got = fn(*args)
        except TypeError as exc:
            r.fail(f"{label} — the function did not accept the values given to it.",
                   f"Python said: {exc}\n"
                   "Check the names in the brackets after 'def' match what the\n"
                   "instructions describe.", where)
            return
        except Exception as exc:                               # noqa: BLE001
            call = f"{getattr(fn, '__name__', 'it')}({', '.join(repr(a) for a in args)})"
            r.fail(f"{label} — {call} stopped with an error: "
                   f"{type(exc).__name__}: {exc}", hint, where)
            return

        if got is None and want is not None:
            r.fail(f"{label} — the function gave nothing back.",
                   "It probably still says 'pass', or it is missing a 'return'\n"
                   "line. Calculating a value is not enough; you have to return it.",
                   where)
            return

        if got != want:
            call = f"{getattr(fn, '__name__', 'it')}({', '.join(repr(a) for a in args)})"
            r.fail(f"{label} — {call} should be {want!r}, but gave {got!r}.",
                   hint, where)
            return

    r.ok(label)


def expect(r: Results, label: str, fn, args, want, hint="", where=""):
    """Call one of the student's functions and compare with what was asked for."""
    if fn is None:
        r.fail(f"{label} — the function is missing entirely.",
               "Check you have not deleted or renamed it.", where)
        return
    try:
        got = fn(*args)
    except TypeError as exc:
        r.fail(f"{label} — the function did not accept the values given to it.",
               f"Python said: {exc}\n"
               "Check the names in the brackets after 'def' match what the\n"
               "instructions describe.", where)
        return
    except Exception as exc:                                   # noqa: BLE001
        r.fail(f"{label} — the function stopped with an error: "
               f"{type(exc).__name__}: {exc}", hint, where)
        return

    if got is None:
        r.fail(f"{label} — the function gave nothing back.",
               "It probably still says 'pass', or it is missing a 'return'\n"
               "line. Calculating a value is not enough; you have to return it.",
               where)
        return

    if got != want:
        r.fail(f"{label} — expected {want!r}, got {got!r}.", hint, where)
        return

    r.ok(f"{label}")


# ===========================================================================
# F2
# ===========================================================================

def check_f2(args) -> int:
    r = Results()
    print("\nF2 — your first program\n")

    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 10):
        r.ok(f"Python {major}.{minor} is installed ({platform.system()}).")
    else:
        r.fail(f"Python {major}.{minor} is too old for this course.",
               "You need 3.10 or newer. Install it from python.org, then close\n"
               "this terminal, open a new one, and run 'python3 --version'.")

    ex = load_exercises(r)
    if ex is None:
        return r.report("F2")

    name = getattr(ex, "MY_NAME", "")
    if not isinstance(name, str) or not name.strip():
        r.fail("MY_NAME does not have your name in it yet.",
               "Put your name between the quote marks, like:\n"
               '  MY_NAME = "Ada"',
               "exercises.py, near the top")
    else:
        r.ok(f"MY_NAME holds {name!r}.")

    greeting = getattr(ex, "GREETING", "")
    if isinstance(name, str) and name.strip():
        want = "Hello, " + name + ". Welcome."
        if greeting == want:
            r.ok("GREETING is built correctly from MY_NAME.")
        elif not greeting:
            r.fail("GREETING is still empty.",
                   "Build it out of MY_NAME using +, for example:\n"
                   '  GREETING = "Hello, " + MY_NAME + ". Welcome."',
                   "exercises.py, near the top")
        elif want.replace(" ", "") == greeting.replace(" ", ""):
            r.fail("GREETING is nearly right — the spacing is off.",
                   f"Expected exactly: {want!r}\n"
                   f"You have:         {greeting!r}\n"
                   "Look for a missing space inside the quote marks.",
                   "exercises.py, near the top")
        else:
            r.fail(f"GREETING should be {want!r}, but it is {greeting!r}.",
                   "Join the pieces with + and keep the punctuation.",
                   "exercises.py, near the top")

    return r.report("F2")


# ===========================================================================
# F3
# ===========================================================================

def check_f3(args) -> int:
    r = Results()
    print("\nF3 — decisions, repetition, and holding data\n")

    ex = load_exercises(r)
    if ex is None:
        return r.report("F3")

    where = "exercises.py, the F3 section"

    expect_all(r, "is_cold decides correctly", getattr(ex, "is_cold", None),
               [((4,), True), ((20,), False), ((10,), False), ((9,), True)],
               "Below 10 is cold. Note that 10 itself is NOT below 10 —\n"
               "use < rather than <=.", where)

    expect_all(r, "count_down counts down with a while loop",
               getattr(ex, "count_down", None),
               [((3,), [3, 2, 1]), ((1,), [1]), ((0,), [])],
               "Start with an empty list, then use a while loop that appends\n"
               "and reduces the number each time around. When there is nothing\n"
               "to count, the loop body never runs and you return the empty list.",
               where)

    expect_all(r, "total_tokens adds up a list of dictionaries",
               getattr(ex, "total_tokens", None),
               [(([{"name": "a", "tokens": 100}, {"name": "b", "tokens": 250}],), 350),
                (([],), 0)],
               "Loop over the list. Each item is a dictionary, so look up its\n"
               'tokens with call["tokens"] and add it to a running total.\n'
               "Start the total at 0 so an empty list gives 0.", where)

    expect_all(r, "describe builds a sentence from a dictionary",
               getattr(ex, "describe", None),
               [(({"name": "Ada", "age": 36},), "Ada is 36 years old"),
                (({"name": "Grace", "age": 45},), "Grace is 45 years old")],
               'Look up person["name"] and person["age"]. The age is a number,\n'
               "so wrap it in str() before joining it with +.", where)

    expect_all(r, "cost_of works out a price", getattr(ex, "cost_of", None),
               [((1_000_000, 5.00), 5.0), ((500, 5.00), 0.0025)],
               "Divide the tokens by 1000000, then multiply by the price.", where)

    # The while loop is the point of the module, so say so on success.
    if not r.failed:
        r.note("")
        r.note("Look at your count_down again. A while loop that keeps going")
        r.note("until a condition goes false, doing work each time around — that")
        r.note("is the exact shape of the AI agent you build in Module 1.")

    return r.report("F3")


# ===========================================================================
# F4
# ===========================================================================

class _FakeUsage:
    input_tokens, output_tokens = 1000, 500


class _FakeBlock:
    type, text = "text", "Oslo is the capital of Norway."


class _FakeResponse:
    content = [_FakeBlock()]
    stop_reason = "end_turn"
    usage = _FakeUsage()


class _FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse()


class FakeClient:
    """Stands in for the real client so F4 can be checked without spending."""

    def __init__(self):
        self.messages = _FakeMessages()


def check_f4(args) -> int:
    r = Results()
    print("\nF4 — talking to Claude from your own code\n")

    ex = load_exercises(r)
    if ex is None:
        return r.report("F4")

    where = "exercises.py, the F4 section"

    expect_all(r, "call_cost works out what a call cost",
               getattr(ex, "call_cost", None), [((_FakeUsage(),), 0.0175)],
               "Multiply each token count by its price, add them, then divide\n"
               "by 1000000 because prices are per million tokens.", where)

    # --- ask_claude, against a fake client so it costs nothing ---
    fake = FakeClient()
    fn = getattr(ex, "ask_claude", None)
    if fn is None:
        r.fail("ask_claude is missing.", where=where)
    else:
        try:
            reply = fn(fake, "What is the capital of Norway?")
        except Exception as exc:                               # noqa: BLE001
            r.fail(f"ask_claude stopped with an error: {type(exc).__name__}: {exc}",
                   "Check you are using the `client` that was handed to you,\n"
                   "rather than creating a new one inside the function.", where)
            reply = None

        if reply is None:
            pass
        elif not isinstance(reply, str):
            r.fail(f"ask_claude returned a {type(reply).__name__}, not text.",
                   "You are probably returning the whole response. Dig the text\n"
                   "out of it: response.content[0].text", where)
        elif reply == _FakeBlock.text:
            r.ok("ask_claude sends the question and returns the reply text.")
        else:
            r.fail(f"ask_claude returned {reply!r}, which is not the reply text.",
                   "Return response.content[0].text", where)

        if fake.messages.calls:
            sent = fake.messages.calls[0]
            if sent.get("model"):
                r.ok(f"You asked for the model {sent['model']!r}.")
            else:
                r.fail("No model was given to messages.create().",
                       'Add model="claude-opus-5".', where)
            if sent.get("max_tokens"):
                r.ok(f"max_tokens is set to {sent['max_tokens']}.")
            else:
                r.fail("max_tokens was not set.",
                       "This is your safety limit on the length of the reply.\n"
                       "Add max_tokens=1000.", where)
            msgs = sent.get("messages")
            if (isinstance(msgs, list) and msgs
                    and isinstance(msgs[0], dict)
                    and msgs[0].get("role") == "user"
                    and "capital of Norway" in str(msgs[0].get("content", ""))):
                r.ok("The conversation is a list holding one user message.")
            else:
                r.fail(f"The messages value is not the right shape: {msgs!r}",
                       'It should be a list holding one dictionary:\n'
                       '  messages=[{"role": "user", "content": question}]\n'
                       "Note that the question is passed through, not typed in.",
                       where)
        elif fn is not None:
            r.fail("ask_claude never called client.messages.create().",
                   "That call is what actually sends the question.", where)

    # --- environment, only when a real call is wanted ---
    if args.offline:
        r.note("")
        r.note("Ran offline against a fake model, so this cost nothing.")
        r.note("Drop --offline when you are ready to make one real call.")
    else:
        key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if key:
            r.ok("Your API key is set in this terminal.")
        else:
            r.fail("No API key found in this terminal.",
                   "Set it with:\n"
                   '  export ANTHROPIC_API_KEY="sk-ant-..."     (Mac/Linux)\n'
                   '  $env:ANTHROPIC_API_KEY="sk-ant-..."       (Windows)\n'
                   "It only lasts until you close the window. Check it with\n"
                   "  echo $ANTHROPIC_API_KEY\n"
                   "Or run this checker with --offline to skip the real call.")

        try:
            import anthropic                                   # noqa: F401
            r.ok("The anthropic library is installed.")
        except ImportError:
            r.fail("The anthropic library is not installed.",
                   "Install it with:\n"
                   "  python3 -m pip install anthropic")

        if key and not r.failed:
            try:
                import anthropic
                real = anthropic.Anthropic()
                reply = ex.ask_claude(real, "Reply with exactly: ready")
                r.ok(f"A real call worked. Claude said: {str(reply).strip()[:60]}")
                r.note("That call cost a small fraction of a cent.")
            except Exception as exc:                           # noqa: BLE001
                r.fail(f"The real call failed: {type(exc).__name__}: {exc}",
                       "If this says AuthenticationError, the key is wrong or is\n"
                       "set in a different terminal window. If it mentions credit,\n"
                       "add a few dollars in the console.")

    return r.report("F4")


CHECKS = {"f2": check_f2, "f3": check_f3, "f4": check_f4}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check your foundations exercises.")
    ap.add_argument("module", choices=sorted(CHECKS), help="which module to check")
    ap.add_argument("--offline", action="store_true",
                    help="use a fake model instead of making a real API call")
    args = ap.parse_args(argv)
    return CHECKS[args.module](args)


if __name__ == "__main__":
    raise SystemExit(main())
