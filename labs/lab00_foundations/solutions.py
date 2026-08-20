"""
Worked answers for the foundations exercises.

Look at these AFTER trying. Reading a solution feels like learning and mostly
is not — the understanding comes from the struggle, then the answer.

Each one is written the plainest way, not the cleverest way.
"""


MY_NAME = "Ada"
GREETING = "Hello, " + MY_NAME + ". Welcome."


def is_cold(temperature):
    """Below 10 is cold. Note 10 itself is not below 10."""
    if temperature < 10:
        return True
    else:
        return False
    # Once this is comfortable, know that `return temperature < 10` does the
    # same thing — the comparison is already True or False.


def count_down(start):
    """Count down using a while loop."""
    numbers = []
    current = start
    while current > 0:
        numbers.append(current)
        current = current - 1      # without this line, the loop never ends
    return numbers


def total_tokens(calls):
    """Add up the tokens across a list of dictionaries."""
    total = 0                      # start at 0 so an empty list gives 0
    for call in calls:
        total = total + call["tokens"]
    return total


def describe(person):
    """Build a sentence out of a dictionary."""
    return person["name"] + " is " + str(person["age"]) + " years old"


def cost_of(tokens, price_per_million):
    """Prices are per million tokens."""
    return (tokens / 1_000_000) * price_per_million


def ask_claude(client, question):
    """Send one question and return the reply text."""
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text


def call_cost(usage, price_in=5.00, price_out=25.00):
    """What one call cost, in dollars."""
    return (usage.input_tokens * price_in
            + usage.output_tokens * price_out) / 1_000_000
