"""
The Lab 6 gate: the server passes conformance and the M2 tool-design rubric,
the client drives sampling and elicitation, and the transports are compared.
"""

import pytest

from .inventory_server import server
from .protocol import (
    PROTOCOL_VERSION, Client, SamplingRejected, Server, surface_cost, threat_model,
)


# --------------------------------------------------------------- conformance

def test_initialize_negotiates_capabilities():
    client = Client(server, roots=["/srv/inventory"], sampling_handler=lambda r: "ok")
    result = client.initialize()
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == "inventory"
    assert result["capabilities"]["tools"]["listChanged"] is True


def test_operations_require_initialization():
    fresh = Client(Server("x"))
    with pytest.raises(RuntimeError):
        fresh.list_tools()


def test_all_three_server_primitives_are_used():
    """Exposing everything as tools is the standard mistake."""
    assert server.list_tools(), "tools: model-invoked"
    assert server.list_resources(), "resources: application-controlled"
    assert server.list_prompts(), "prompts: user-invoked"


def test_unknown_tool_returns_an_error_result_listing_what_exists():
    client = Client(server)
    client.initialize()
    result = client.call_tool("inventory_teleport", sku="AC-1180")
    assert result["isError"] is True
    assert "inventory_check_stock" in result["content"][0]["text"]


# ------------------------------------------------------- tool-design rubric

def test_server_tools_pass_the_m2_rubric():
    for tool in server.list_tools():
        description = tool["description"]
        assert len(description) > 150, f"{tool['name']}: description too thin"
        assert "use this when" in description.lower() or "whenever" in description.lower()
        assert "return" in description.lower(), f"{tool['name']}: return shape undocumented"
        assert any(w in description.lower() for w in ("no such", "not an error", "empty")), \
            f"{tool['name']}: failure semantics undocumented"

        props = tool["inputSchema"]["properties"]
        for name, schema in props.items():
            assert schema.get("description"), f"{tool['name']}.{name} undescribed"
        assert tool["inputSchema"].get("required") is not None
        assert tool["name"].startswith("inventory_"), "namespace by system"


def test_the_server_hides_the_legacy_apis_sins():
    client = Client(server)
    client.initialize()

    # 200-with-an-error-body becomes a clear, actionable message.
    missing = client.call_tool("inventory_check_stock", sku="ZZ-9999")
    assert missing["isError"] is False
    assert "No such SKU" in missing["content"][0]["text"]

    # Inconsistent casing is normalised at the boundary, once.
    found = client.call_tool("inventory_check_stock", sku="ac-1180")
    text = found["content"][0]["text"]
    assert "warehouse_a" in text and "warehouse_c" in text
    assert "WAREHOUSE-C" not in text
    assert "total 49" in text


# ------------------------------------------------------- client primitives

def test_sampling_runs_on_the_host_model_and_is_capped():
    """A server asking your model to generate is your inference budget and your
    injection surface."""
    seen = []

    def handler(request):
        seen.append(request)
        return "a summary"

    client = Client(server, sampling_handler=handler, sampling_token_cap=1500)
    client.initialize()

    assert client.handle_sampling({"messages": [], "maxTokens": 500}) == "a summary"
    assert seen, "the host handler must actually run"

    with pytest.raises(SamplingRejected):
        client.handle_sampling({"messages": [], "maxTokens": 100_000})

    ungated = Client(server)
    ungated.initialize()
    with pytest.raises(SamplingRejected):
        ungated.handle_sampling({"messages": [], "maxTokens": 10})


def test_elicitation_asks_the_user_and_declines_by_default():
    asked = []
    client = Client(server, elicitation_handler=lambda r: (asked.append(r) or
                                                           {"action": "accept",
                                                            "content": {"sku": "AC-1180"}}))
    client.initialize()
    answer = client.handle_elicitation({"message": "Which SKU did you mean?"})
    assert answer["action"] == "accept" and asked

    silent = Client(server)
    silent.initialize()
    assert silent.handle_elicitation({"message": "?"})["action"] == "decline"


def test_roots_declare_scope():
    client = Client(server, roots=["/srv/inventory"])
    assert client.list_roots()[0]["uri"] == "file:///srv/inventory"


def test_list_changed_reaches_the_client():
    """A tool list that changes mid-session invalidates the prompt cache."""
    s = Server("dynamic")
    client = Client(s)
    client.initialize()
    before = client.tools_changed

    @s.tool("dynamic_thing", "A tool added at runtime. Use this when testing.",
            {"type": "object", "properties": {}, "required": []})
    def _thing():
        return "ok"

    assert client.tools_changed == before + 1


# ------------------------------------------------------------ surface budget

def test_a_large_surface_is_a_context_problem_before_a_capability():
    servers = []
    for i in range(6):
        s = Server(f"s{i}")
        for j in range(9):
            s.tool(f"s{i}_tool{j}", "x", {"type": "object", "properties": {}})(lambda: "")
        servers.append(s)

    naive = surface_cost(servers)
    assert naive["tools"] == 54
    assert naive["tokens_per_turn"] > 14_000
    assert naive["tokens_per_task"] > 200_000, "paid before the user says anything"

    searched = surface_cost(servers, tool_search=True)
    assert searched["tokens_per_turn"] < naive["tokens_per_turn"] / 4


def test_transport_choice_is_a_security_decision():
    stdio, http = threat_model("stdio"), threat_model("streamable-http")
    assert stdio["authentication"] == "none — there is no boundary to authenticate across"
    assert "environment variable" in stdio["reachable_secrets"]
    assert stdio["multi_user"] is False and http["multi_user"] is True
    assert http["authentication"].startswith("OAuth")
    # Both carry the same unreviewed-description risk: the protocol does not fix it.
    assert any("model context" in r for r in stdio["residual_risks"])
    assert any("model context" in r for r in http["residual_risks"])
