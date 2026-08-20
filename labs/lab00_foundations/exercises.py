"""
Foundations exercises — THIS IS THE FILE YOU EDIT.

Fill in each function where it says TODO, then run the checker:

    python3 -m lab00_foundations.check f2
    python3 -m lab00_foundations.check f3
    python3 -m lab00_foundations.check f4

The checker tells you in plain English what is wrong. It will not show you a
wall of red text. Work through them in order; each one only uses ideas from the
module it belongs to.

Nothing here is a trick. If something feels impossible, re-read the module
section it came from — the answer is in there.
"""

# ===========================================================================
# F2 — variables and printing
# ===========================================================================

# TODO (F2.1): put your own name here, as text, in quote marks.
MY_NAME = ""

# TODO (F2.2): build a greeting using MY_NAME and the + sign, so that if your
# name were Ada, GREETING would be exactly: "Hello, Ada. Welcome."
GREETING = ""


# ===========================================================================
# F3 — decisions, loops, lists, dictionaries, functions
# ===========================================================================

def is_cold(temperature):
    """Return True when it is below 10 degrees, otherwise False.

    Example: is_cold(4) -> True,  is_cold(20) -> False
    """
    # TODO (F3.1): use an if/else, or return the comparison directly.
    pass


def count_down(start):
    """Return a list counting down from `start` to 1.

    Example: count_down(3) -> [3, 2, 1]
             count_down(0) -> []

    Use a WHILE loop. This is the exercise that matters most in this module:
    it is the same shape as the agent loop in Module 1.
    """
    # TODO (F3.2): start with an empty list, append inside a while loop, and
    # make sure something inside the loop changes the condition — or it will
    # never stop. (Ctrl + C stops a runaway program.)
    pass


def total_tokens(calls):
    """Add up the "tokens" value of every call in a list of dictionaries.

    Example:
        total_tokens([{"name": "a", "tokens": 100},
                      {"name": "b", "tokens": 250}])  ->  350
        total_tokens([]) -> 0
    """
    # TODO (F3.3): loop over the list, look up "tokens" in each dictionary,
    # and add it to a running total.
    pass


def describe(person):
    """Return "<name> is <age> years old" using a dictionary.

    Example: describe({"name": "Ada", "age": 36}) -> "Ada is 36 years old"

    Remember: str() turns a number into text so you can join it with +.
    """
    # TODO (F3.4)
    pass


def cost_of(tokens, price_per_million):
    """Return the cost of a number of tokens, in dollars.

    Example: cost_of(1_000_000, 5.00) -> 5.0
             cost_of(500, 5.00)       -> 0.0025
    """
    # TODO (F3.5): divide by a million, then multiply by the price.
    pass


# ===========================================================================
# F4 — your first API call
# ===========================================================================

def ask_claude(client, question):
    """Send `question` to Claude and return the reply as plain text.

    `client` is handed to you — do NOT create your own inside this function,
    because the checker passes in a fake one when you run with --offline.

    You need to:
      1. call client.messages.create(...) with model, max_tokens and messages
      2. dig the text out of the reply and return it

    The messages value is a list holding one dictionary, with the keys
    "role" and "content". Model: "claude-opus-5". max_tokens: 1000 is plenty.
    """
    # TODO (F4.1)
    pass


def call_cost(usage, price_in=5.00, price_out=25.00):
    """Return what one call cost, in dollars.

    `usage` has .input_tokens and .output_tokens. Prices are per MILLION
    tokens — check the current published rates before trusting these defaults.

    Example: 1000 in and 500 out at these prices -> 0.0175
    """
    # TODO (F4.2)
    pass
