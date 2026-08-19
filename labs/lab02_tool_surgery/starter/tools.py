"""
Lab 2 — the CRM tool layer. STARTER: eight tools with real, specific flaws.

    cp starter/tools.py tools.py
    python -m lab02_tool_surgery.harness

These are not uniformly terrible — that would be an easy exercise. Most of them
are fine. A handful carry exactly the flaws M2 describes, and the boilerplate is
the kind of legal-sounding preamble that accumulates in a mature codebase:
expensive on every turn, informative to nobody.

Get to 85% or better while *reducing* total definition tokens. Only this file
may change.
"""

from agentcourse import ToolError, ToolRegistry, tool

_CUSTOMERS = {
    "C-4471": {"name": "Acme Corp", "plan": "Enterprise", "status": "active"},
    "C-8890": {"name": "Northwind Ltd", "plan": "Team", "status": "trial"},
}
_TICKETS = {
    "T-9912": {"customer_id": "C-4471", "status": "open", "priority": "normal",
               "queue": "support", "subject": "Billing discrepancy"},
}

@tool
def crm_search_customers(query: str, status: str = "any", limit: int = 10) -> str:
    """Search for and find customers by name, email address or account number.

    Use this to look up any customer when you do not already have their
    customer_id.

    This tool forms part of the CRM Integration Suite (CIS) and is exposed to
    automated agents operating against the customer data platform. All usage is
    subject to the data handling policies of the calling organisation and to the
    access permissions associated with the calling credential. Results may be
    filtered, redacted or truncated according to those permissions without
    further notice in the response payload. Rate limiting applies per credential
    per rolling minute. This interface is versioned; behaviour may change
    between minor releases in accordance with the platform deprecation policy.

    Args:
        query: Free text — a company name, a person's name, an email address or
            an account number. Partial matches are supported.
        status: Filter by account status.
        limit: Maximum results to return, 1-20. Defaults to 10.
    """
    hits = [{"customer_id": cid, **c} for cid, c in _CUSTOMERS.items()
            if query.lower() in c["name"].lower()]
    return str(hits[:limit])


@tool
def crm_find_accounts(term: str, kind: str = "all") -> str:
    """Find and search customer accounts by name, email address or number.

    Use this to look up a customer account when you do not have its id.

    This tool forms part of the CRM Integration Suite (CIS) and is exposed to
    automated agents operating against the customer data platform. All usage is
    subject to the data handling policies of the calling organisation and to the
    access permissions associated with the calling credential. Results may be
    filtered, redacted or truncated according to those permissions without
    further notice in the response payload. Rate limiting applies per credential
    per rolling minute. This interface is versioned; behaviour may change
    between minor releases in accordance with the platform deprecation policy.

    Args:
        term: Free text — a company name, a person's name, an email address or
            an account number. Partial matches are supported.
        kind: The kind of account to match.
    """
    return str([{"customer_id": cid, **c} for cid, c in _CUSTOMERS.items()])


@tool
def crm_get_customer(customer_id: str) -> str:
    """Retrieve the full customer record: account details, plan and contacts.

    Use this when you need details about one known customer — their plan,
    renewal date, account owner, contract value or contacts.

    This tool forms part of the CRM Integration Suite (CIS) and is exposed to
    automated agents operating against the customer data platform. All usage is
    subject to the data handling policies of the calling organisation and to the
    access permissions associated with the calling credential. Results may be
    filtered, redacted or truncated according to those permissions without
    further notice in the response payload. Rate limiting applies per credential
    per rolling minute. This interface is versioned; behaviour may change
    between minor releases in accordance with the platform deprecation policy.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
    """
    if customer_id not in _CUSTOMERS:
        raise ToolError("not found")
    return str(_CUSTOMERS[customer_id])


@tool(enum={"status": ["open", "pending_customer", "resolved", "closed", "any"]})
def crm_list_tickets(customer_id: str, status: str = "any", limit: int = 20) -> str:
    """List support tickets for a customer, most recent first.

    Use this whenever the user asks about tickets, cases, support history or
    open issues.

    This tool forms part of the CRM Integration Suite (CIS) and is exposed to
    automated agents operating against the customer data platform. All usage is
    subject to the data handling policies of the calling organisation and to the
    access permissions associated with the calling credential. Results may be
    filtered, redacted or truncated according to those permissions without
    further notice in the response payload. Rate limiting applies per credential
    per rolling minute. This interface is versioned; behaviour may change
    between minor releases in accordance with the platform deprecation policy.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
        status: Filter by ticket status.
        limit: Maximum tickets to return, 1-50. Defaults to 20.
    """
    return str([{"ticket_id": t, **v} for t, v in _TICKETS.items()
                if v["customer_id"] == customer_id][:limit])


@tool
def crm_add_note(customer_id: str, body: str) -> str:
    """Add a note, comment or log entry to a customer account record.

    Use this to record something about an account that is not a support ticket.

    This tool forms part of the CRM Integration Suite (CIS) and is exposed to
    automated agents operating against the customer data platform. All usage is
    subject to the data handling policies of the calling organisation and to the
    access permissions associated with the calling credential. Results may be
    filtered, redacted or truncated according to those permissions without
    further notice in the response payload. Rate limiting applies per credential
    per rolling minute. This interface is versioned; behaviour may change
    between minor releases in accordance with the platform deprecation policy.

    Args:
        customer_id: The customer identifier.
        body: The note text.
    """
    return f"note added to {customer_id}"


@tool(enum={
    "status": ["open", "pending_customer", "resolved", "closed"],
    "priority": ["low", "normal", "high", "urgent"],
    "queue": ["support", "billing", "engineering", "success"],
})
def crm_update_ticket(ticket_id: str, status: str = None, priority: str = None,
                      queue: str = None) -> str:
    """Update, change, escalate, reassign or close an existing support ticket.

    Use this for any change to a ticket.

    This tool forms part of the CRM Integration Suite (CIS) and is exposed to
    automated agents operating against the customer data platform. All usage is
    subject to the data handling policies of the calling organisation and to the
    access permissions associated with the calling credential. Results may be
    filtered, redacted or truncated according to those permissions without
    further notice in the response payload. Rate limiting applies per credential
    per rolling minute. This interface is versioned; behaviour may change
    between minor releases in accordance with the platform deprecation policy.

    Args:
        ticket_id: The ticket_id returned by crm_list_tickets.
        status: New ticket status.
        priority: New priority.
        queue: Queue to reassign the ticket to.
    """
    return f"updated {ticket_id}"


@tool
def crm_get_billing(customer_id: str) -> str:
    """Retrieve billing history: invoices, payments and charges for a customer.

    Use this when the user asks what a customer has paid, about invoices, or
    about billing history.

    This tool forms part of the CRM Integration Suite (CIS) and is exposed to
    automated agents operating against the customer data platform. All usage is
    subject to the data handling policies of the calling organisation and to the
    access permissions associated with the calling credential. Results may be
    filtered, redacted or truncated according to those permissions without
    further notice in the response payload. Rate limiting applies per credential
    per rolling minute. This interface is versioned; behaviour may change
    between minor releases in accordance with the platform deprecation policy.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
    """
    raise ToolError("500")


@tool(enum={"channel": ["phone", "email", "chat", "meeting"]})
def crm_log_interaction(customer_id: str, summary: str, channel: str = "phone",
                        open_ticket: bool = False) -> str:
    """Log or record a customer interaction — a call, meeting, chat or email —
    and optionally open a support ticket from it in one step.

    Use this after any conversation with a customer.

    This tool forms part of the CRM Integration Suite (CIS) and is exposed to
    automated agents operating against the customer data platform. All usage is
    subject to the data handling policies of the calling organisation and to the
    access permissions associated with the calling credential. Results may be
    filtered, redacted or truncated according to those permissions without
    further notice in the response payload. Rate limiting applies per credential
    per rolling minute. This interface is versioned; behaviour may change
    between minor releases in accordance with the platform deprecation policy.

    Args:
        customer_id: The customer_id returned by crm_search_customers.
        summary: What was discussed and what was agreed.
        channel: How the interaction happened.
        open_ticket: Whether to open a ticket.
    """
    return f"logged for {customer_id}"


def registry() -> ToolRegistry:
    return ToolRegistry(
        crm_search_customers,
        crm_find_accounts,
        crm_get_customer,
        crm_list_tickets,
        crm_add_note,
        crm_update_ticket,
        crm_get_billing,
        crm_log_interaction,
    )
