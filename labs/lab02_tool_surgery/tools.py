"""
Lab 2 — the CRM tool layer. THIS IS THE FILE YOU EDIT.

It ships rewritten, so the repository is green and you have a reference. To take
the lab:

    cp starter/tools.py tools.py       # the eight flawed tools, ~55% pass rate
    python -m lab02_tool_surgery.harness
    git checkout labs/lab02_tool_surgery/tools.py     # restore

One rule: **only this file may change.** The eval set, the harness and the
surrogate are frozen.

Notice what the rewrite actually did:
  - said *when* to use each tool, in the words a user would use
  - gave every parameter a description
  - closed every closed set with an enum
  - said where opaque ids come from
  - said that empty is not an error, and that the billing outage is permanent
  - deleted `crm_find_accounts`, a near-duplicate of `crm_search_customers`
    that was attracting its calls
  - consolidated the call-logging flow into one task-shaped tool

...and did all of it while *reducing* total definition tokens, because the
flawed descriptions were long and uninformative rather than short.
"""

from agentcourse import ToolError, ToolRegistry, tool

# A stand-in backend. The lab is about the interface, not the storage.
_CUSTOMERS = {
    "C-4471": {"name": "Acme Corp", "plan": "Enterprise", "status": "active"},
    "C-8890": {"name": "Northwind Ltd", "plan": "Team", "status": "trial"},
}
_TICKETS = {
    "T-9912": {"customer_id": "C-4471", "status": "open", "priority": "normal",
               "queue": "support", "subject": "Billing discrepancy"},
}


@tool(enum={"status": ["active", "churned", "trial", "any"]})
def crm_search_customers(query: str, status: str = "any", limit: int = 10) -> str:
    """Search for and find customers by name, email address or account number.

    Use this to look up any customer when you do not already have their
    customer_id — it is the only tool that accepts a name or an email, and every
    other crm_ tool needs the id this returns.

    Returns up to 20 matches, each with name, email, account_number,
    customer_id and status.

    An unmatched query returns an empty list, which is not an error: widen the
    query and try again rather than telling the user no such customer exists.

    Args:
        query: Free text — a company name, a person's name, an email address or
            an account number. Partial matches are supported.
        status: Filter by account status. Use 'any' unless the user asked to
            narrow it.
        limit: Maximum results to return, 1-20. Defaults to 10.
    """
    hits = [{"customer_id": cid, **c} for cid, c in _CUSTOMERS.items()
            if query.lower() in c["name"].lower()
            and status in ("any", c["status"])]
    return str(hits[:limit])


@tool
def crm_get_customer(customer_id: str) -> str:
    """Retrieve the full customer record: account details, plan and contacts.

    Use this when you need details about one known customer — their plan,
    renewal date, account owner, contract value or contacts.

    Returns the complete record. Returns a clear 'no such customer' message,
    not an error, if the id does not exist.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
    """
    if customer_id not in _CUSTOMERS:
        return f"No customer with id {customer_id}."
    return str(_CUSTOMERS[customer_id])


@tool(enum={"status": ["open", "pending_customer", "resolved", "closed", "any"]})
def crm_list_tickets(customer_id: str, status: str = "any", limit: int = 20) -> str:
    """List support tickets for a customer, most recent first.

    Use this whenever the user asks about tickets, cases, support history or
    open issues for a customer.

    Returns ticket_id, subject, status, priority, queue and created date. A
    customer with no tickets returns an empty list, which is not an error.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
        status: Filter by ticket status. Use 'any' for all tickets.
        limit: Maximum tickets to return, 1-50. Defaults to 20.
    """
    hits = [{"ticket_id": tid, **t} for tid, t in _TICKETS.items()
            if t["customer_id"] == customer_id and status in ("any", t["status"])]
    return str(hits[:limit])


@tool
def crm_add_note(customer_id: str, body: str) -> str:
    """Add a note, comment or log entry to a customer account record.

    Use this to record something about an account that is not a support ticket:
    a conversation, an internal observation, a renewal risk.

    Returns the note id and timestamp. Notes are append-only and cannot be
    edited or deleted once written.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
        body: The note text. Write it for a colleague reading it in six months,
            not for yourself today.
    """
    return f"note added to {customer_id} ({len(body)} chars)"


@tool(enum={
    "status": ["open", "pending_customer", "resolved", "closed"],
    "priority": ["low", "normal", "high", "urgent"],
    "queue": ["support", "billing", "engineering", "success"],
})
def crm_update_ticket(ticket_id: str, status: str = None, priority: str = None,
                      queue: str = None) -> str:
    """Update, change, escalate, reassign or close an existing support ticket.

    Use this for any change to a ticket: changing its status, raising or
    lowering its priority, moving it to another queue, or closing it.

    Supply only the fields you are changing. Returns the updated ticket.

    Args:
        ticket_id: The ticket_id returned by crm_list_tickets.
        status: New ticket status. Omit to leave unchanged.
        priority: New priority. 'urgent' pages the on-call engineer, so use it
            only when the user explicitly asked to escalate.
        queue: Queue to reassign the ticket to. Omit to leave unchanged.
    """
    if ticket_id not in _TICKETS:
        return f"No ticket with id {ticket_id}."
    return f"updated {ticket_id}"


@tool
def crm_get_billing(customer_id: str) -> str:
    """Retrieve billing history: invoices, payments and charges for a customer.

    Use this when the user asks what a customer has paid, about invoices, or
    about billing history.

    IMPORTANT: the billing service is undergoing a permanent migration and this
    tool is unavailable until it completes. No call will succeed. Tell the user
    billing data is temporarily unavailable and stop retrying — do not call this
    tool again in the same session.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
    """
    raise ToolError(
        "The billing service is migrating and is unavailable. No call will "
        "succeed this session — report this to the user and stop retrying."
    )


@tool(enum={"channel": ["phone", "email", "chat", "meeting"]})
def crm_log_interaction(customer_id: str, summary: str, channel: str = "phone",
                        open_ticket: bool = False) -> str:
    """Log or record a customer interaction — a call, meeting, chat or email —
    and optionally open a support ticket from it in one step.

    Use this after any conversation with a customer. It writes the account note
    and, when the interaction raised a problem, opens the ticket too, so you do
    not need to call crm_add_note and a ticket tool separately.

    Returns the note id and, when one was opened, the new ticket_id.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
        summary: What was discussed and what was agreed.
        channel: How the interaction happened.
        open_ticket: Set true when the interaction raised a problem needing
            follow-up. Opens a ticket in the support queue.
    """
    out = f"logged {channel} interaction for {customer_id}"
    if open_ticket:
        out += "; opened ticket T-9913"
    return out


def registry() -> ToolRegistry:
    return ToolRegistry(
        crm_search_customers,
        crm_get_customer,
        crm_list_tickets,
        crm_add_note,
        crm_update_ticket,
        crm_get_billing,
        crm_log_interaction,
    )
