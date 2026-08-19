"""The Lab 4 eval set: 40 support tickets, including the ambiguous ones.

A set of only clear-signal tickets makes every pattern look identical. The
ambiguous and no-signal cases are where the architectures separate, so a third
of the set is deliberately hard.
"""

from .patterns import Ticket

TICKETS = [
    # --- clear signal (20) --------------------------------------------------
    Ticket("k01", "I was charged twice for my invoice this month", "billing"),
    Ticket("k02", "Please refund the duplicate payment", "billing"),
    Ticket("k03", "My subscription price went up without warning", "billing"),
    Ticket("k04", "The invoice PDF has the wrong VAT number", "billing"),
    Ticket("k05", "The dashboard crashes with a 500 error on load", "technical"),
    Ticket("k06", "Export times out after 30 seconds every time", "technical"),
    Ticket("k07", "The chart is broken since yesterday's release", "technical"),
    Ticket("k08", "Webhooks fail with a timeout on large payloads", "technical"),
    Ticket("k09", "I cannot login, my password reset never arrives", "account"),
    Ticket("k10", "SSO access is locked for our whole team", "account"),
    Ticket("k11", "We need two more seats on the plan", "account"),
    Ticket("k12", "Permission denied opening the admin area", "account"),
    Ticket("k13", "Someone is sending phishing mail from your domain", "abuse"),
    Ticket("k14", "Report of harassment from another workspace member", "abuse"),
    Ticket("k15", "This looks like a scam invoice, is it from you?", "abuse", True),
    Ticket("k16", "Getting spam through the shared inbox feature", "abuse"),
    Ticket("k17", "Payment failed and the card was charged anyway", "billing"),
    Ticket("k18", "App crash on the iOS build, error on startup", "technical"),
    Ticket("k19", "Locked out after too many login attempts", "account"),
    Ticket("k20", "Fraudulent charge on our corporate card", "abuse", True),

    # --- ambiguous: signals from two categories (12) ------------------------
    Ticket("a01", "Charged for seats we cannot access due to a permission error",
           "account"),
    Ticket("a02", "Login broken after the invoice was paid, access denied",
           "account"),
    Ticket("a03", "The billing page crashes with a 500 when loading invoices",
           "technical"),
    Ticket("a04", "Password reset email went to spam and the charge failed",
           "account"),
    Ticket("a05", "Refund request because the export keeps failing", "billing", True),
    Ticket("a06", "SSO timeout means we are paying for unusable seats", "account"),
    Ticket("a07", "Subscription charge for a broken feature", "billing"),
    Ticket("a08", "Error 500 on the payment page during checkout", "technical"),
    Ticket("a09", "Someone with our old seat still has access after we were billed",
           "account", True),
    Ticket("a10", "Invoice shows a bug we reported months ago as billable", "billing"),
    Ticket("a11", "Cannot access the account and the subscription was cancelled",
           "account", True),
    Ticket("a12", "Locked out of our login, and we were double billed", "account"),

    # --- no clear signal (8) -------------------------------------------------
    Ticket("n01", "Hello, could someone call me back please", "other"),
    Ticket("n02", "Question about your roadmap for next year", "other"),
    Ticket("n03", "We are considering an enterprise agreement", "other", True),
    Ticket("n04", "Following up on my previous message", "other"),
    Ticket("n05", "Is there a way to do this differently?", "other"),
    Ticket("n06", "Thanks for the help last week", "other"),
    Ticket("n07", "Our lawyer would like to discuss the contract", "other", True),
    Ticket("n08", "Can you point me at the documentation", "other"),
]

assert len(TICKETS) == 40
