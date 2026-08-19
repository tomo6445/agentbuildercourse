"""
The Lab 2 eval set: twenty tasks over a CRM tool layer.

Frozen. You may not edit this file — the exercise is to change the tool layer
until these pass. Tasks are tagged with the tool-design property each exercises,
so a failure tells you which part of M2 you are missing.
"""

from .surrogate import Task

TASKS = [
    # --- selection: can the model tell these tools apart? -----------------
    Task("t01", "Find the customer record for jane@acme.example",
         expects_tool="crm_search_customers",
         intent=["search", "customer", "find", "email"],
         needs_params=["query"]),
    Task("t02", "Show me everything on file for customer C-4471",
         expects_tool="crm_get_customer",
         intent=["customer", "record", "details", "retrieve", "account"],
         needs_params=["customer_id"], opaque_id_params=["customer_id"]),
    Task("t03", "List the open support tickets for Acme Corp",
         expects_tool="crm_list_tickets",
         intent=["tickets", "support", "list", "open"],
         needs_params=["customer_id"], opaque_id_params=["customer_id"],
         closed_set_params=["status"]),
    Task("t04", "Log a note on the Acme account about today's call",
         expects_tool="crm_add_note",
         intent=["note", "log", "record", "comment", "account"],
         needs_params=["customer_id", "body"], opaque_id_params=["customer_id"]),
    Task("t05", "Which plan is Acme Corp on?",
         expects_tool="crm_get_customer",
         intent=["customer", "plan", "account", "details", "retrieve"],
         needs_params=["customer_id"], opaque_id_params=["customer_id"]),

    # --- enums: closed sets typed as free strings -------------------------
    Task("t06", "Show me only the churned customers in the enterprise segment",
         expects_tool="crm_search_customers",
         intent=["search", "customer", "find"],
         needs_params=["query"], closed_set_params=["status"]),
    Task("t07", "List all tickets that are still waiting on the customer",
         expects_tool="crm_list_tickets",
         intent=["tickets", "support", "list"],
         needs_params=["customer_id"], opaque_id_params=["customer_id"],
         closed_set_params=["status"]),
    Task("t08", "Escalate ticket T-9912 to urgent priority",
         expects_tool="crm_update_ticket",
         intent=["ticket", "update", "escalate", "priority", "change"],
         needs_params=["ticket_id", "priority"], closed_set_params=["priority"]),
    Task("t09", "Close ticket T-9912 as resolved",
         expects_tool="crm_update_ticket",
         intent=["ticket", "update", "close", "change", "status"],
         needs_params=["ticket_id", "status"], closed_set_params=["status"]),
    Task("t10", "Find trial accounts that signed up this month",
         expects_tool="crm_search_customers",
         intent=["search", "customer", "find"],
         needs_params=["query"], closed_set_params=["status"]),

    # --- parameter descriptions -------------------------------------------
    Task("t11", "Give me the 5 most recent tickets for customer C-4471",
         expects_tool="crm_list_tickets",
         intent=["tickets", "support", "list", "recent"],
         needs_params=["customer_id", "limit"], opaque_id_params=["customer_id"]),
    Task("t12", "Search for customers matching 'northwind' and show me 3",
         expects_tool="crm_search_customers",
         intent=["search", "customer", "find"],
         needs_params=["query", "limit"]),
    Task("t13", "Add a note to C-4471 saying the renewal is at risk",
         expects_tool="crm_add_note",
         intent=["note", "log", "record", "comment"],
         needs_params=["customer_id", "body"], opaque_id_params=["customer_id"]),
    Task("t14", "Reassign ticket T-9912 to the billing queue",
         expects_tool="crm_update_ticket",
         intent=["ticket", "update", "reassign", "change", "queue"],
         needs_params=["ticket_id", "queue"]),

    # --- recovery: empty results are not errors ---------------------------
    Task("t15", "Look up the customer 'Zzyzx Holdings'",
         expects_tool="crm_search_customers",
         intent=["search", "customer", "find", "look"],
         needs_params=["query"], empty_result=True),
    Task("t16", "Do we have any tickets from customer C-0000?",
         expects_tool="crm_list_tickets",
         intent=["tickets", "support", "list"],
         needs_params=["customer_id"], opaque_id_params=["customer_id"],
         empty_result=True),
    Task("t17", "Find anyone at 'notarealcompany.example'",
         expects_tool="crm_search_customers",
         intent=["search", "customer", "find", "email"],
         needs_params=["query"], empty_result=True),

    # --- recovery: permanent failures must not be retried ------------------
    Task("t18", "Pull the billing history for C-4471",
         expects_tool="crm_get_billing",
         intent=["billing", "invoice", "payment", "history", "charges"],
         needs_params=["customer_id"], opaque_id_params=["customer_id"],
         permanent_failure=True),
    Task("t19", "What did Acme pay us last quarter?",
         expects_tool="crm_get_billing",
         intent=["billing", "invoice", "payment", "history", "charges"],
         needs_params=["customer_id"], opaque_id_params=["customer_id"],
         permanent_failure=True),

    # --- consolidation: a task-shaped request ------------------------------
    Task("t20", "Acme called about a billing problem — log it and open a ticket",
         expects_tool="crm_log_interaction",
         intent=["log", "interaction", "call", "ticket", "open", "record"],
         needs_params=["customer_id", "summary"], opaque_id_params=["customer_id"],
         closed_set_params=["channel"]),
]

assert len({t.id for t in TASKS}) == len(TASKS) == 20
