"""
Lab 6 — MCP, both ends.

The real protocol runs over stdio or streamable HTTP with JSON-RPC framing. This
module implements the same *shapes* in-process — initialize and capability
negotiation, the three server primitives, the three client primitives, and
list_changed — so the lab runs with no dependencies and no transport to debug.

Nothing demystifies a protocol like writing both ends. What this deliberately
does not simulate is the transport, which is where the security decision lives:
see `threat_model()` for the stdio-versus-HTTP comparison the lab requires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

PROTOCOL_VERSION = "2025-06-18"


# ==========================================================================
# server
# ==========================================================================

@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    handler: Callable


@dataclass
class ResourceDef:
    """Application-controlled, URI-addressed. The host decides when to include
    it — the model does not pull it."""

    uri: str
    name: str
    description: str
    reader: Callable


@dataclass
class PromptDef:
    """User-invoked template — the slash-command shape."""

    name: str
    description: str
    render: Callable


class Server:
    """An MCP server. Trust boundary note: everything a server returns —
    including its tool *descriptions* — enters the host's model context. A
    server is untrusted code with a plausible manner."""

    def __init__(self, name: str):
        self.name = name
        self.tools: dict = {}
        self.resources: dict = {}
        self.prompts: dict = {}
        self._listeners: list = []
        self.calls: list = []

    # -- registration ------------------------------------------------------

    def tool(self, name: str, description: str, input_schema: dict):
        def register(fn):
            self.tools[name] = ToolDef(name, description, input_schema, fn)
            self._notify("tools")
            return fn
        return register

    def resource(self, uri: str, name: str, description: str):
        def register(fn):
            self.resources[uri] = ResourceDef(uri, name, description, fn)
            self._notify("resources")
            return fn
        return register

    def prompt(self, name: str, description: str):
        def register(fn):
            self.prompts[name] = PromptDef(name, description, fn)
            self._notify("prompts")
            return fn
        return register

    # -- lifecycle ---------------------------------------------------------

    def initialize(self, client_capabilities: dict) -> dict:
        """Both sides declare what they support; neither assumes."""
        self.client_capabilities = client_capabilities
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": self.name, "version": "1.0.0"},
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"listChanged": True} if self.resources else None,
                "prompts": {"listChanged": True} if self.prompts else None,
            },
        }

    def on_list_changed(self, fn: Callable) -> None:
        self._listeners.append(fn)

    def _notify(self, what: str) -> None:
        for fn in self._listeners:
            fn(what)

    # -- primitives --------------------------------------------------------

    def list_tools(self) -> list:
        return [{"name": t.name, "description": t.description,
                 "inputSchema": t.input_schema} for t in self.tools.values()]

    def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        tool = self.tools.get(name)
        if tool is None:
            return {"isError": True,
                    "content": [{"type": "text", "text":
                                 f"Unknown tool {name!r}. Available: "
                                 f"{', '.join(sorted(self.tools))}."}]}
        try:
            return {"isError": False,
                    "content": [{"type": "text", "text": str(tool.handler(**arguments))}]}
        except Exception as exc:                                # noqa: BLE001
            return {"isError": True,
                    "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}]}

    def list_resources(self) -> list:
        return [{"uri": r.uri, "name": r.name, "description": r.description}
                for r in self.resources.values()]

    def read_resource(self, uri: str) -> dict:
        r = self.resources.get(uri)
        if r is None:
            raise KeyError(f"no resource at {uri}")
        return {"contents": [{"uri": uri, "text": r.reader()}]}

    def list_prompts(self) -> list:
        return [{"name": p.name, "description": p.description}
                for p in self.prompts.values()]

    def get_prompt(self, name: str, arguments: dict | None = None) -> dict:
        return {"messages": self.prompts[name].render(**(arguments or {}))}


# ==========================================================================
# client
# ==========================================================================

class SamplingRejected(Exception):
    """The host refused a server's sampling request."""


class Client:
    """An MCP client, including the three primitives everyone skips.

    Sampling and elicitation flow *from* the server *to* you, which is what makes
    the protocol interesting and what makes it a security surface.
    """

    def __init__(self, server: Server, *, roots: list | None = None,
                 sampling_handler: Callable | None = None,
                 elicitation_handler: Callable | None = None,
                 sampling_token_cap: int = 2000):
        self.server = server
        self.roots = roots or []
        self.sampling_handler = sampling_handler
        self.elicitation_handler = elicitation_handler
        self.sampling_token_cap = sampling_token_cap
        self.sampling_requests: list = []
        self.elicitation_requests: list = []
        self.tools_changed = 0
        self.initialized = False

        server.on_list_changed(self._on_list_changed)

    # -- lifecycle ---------------------------------------------------------

    def initialize(self) -> dict:
        result = self.server.initialize({
            "sampling": {} if self.sampling_handler else None,
            "elicitation": {} if self.elicitation_handler else None,
            "roots": {"listChanged": True} if self.roots else None,
        })
        self.server_capabilities = result["capabilities"]
        self.initialized = True
        return result

    def _on_list_changed(self, what: str) -> None:
        if what == "tools":
            self.tools_changed += 1

    def _require_init(self) -> None:
        if not self.initialized:
            raise RuntimeError("call initialize() before using the connection")

    # -- server primitives -------------------------------------------------

    def list_tools(self) -> list:
        self._require_init()
        return self.server.list_tools()

    def call_tool(self, name: str, **arguments) -> dict:
        self._require_init()
        return self.server.call_tool(name, arguments)

    def read_resource(self, uri: str) -> str:
        self._require_init()
        return self.server.read_resource(uri)["contents"][0]["text"]

    # -- client primitives -------------------------------------------------

    def handle_sampling(self, request: dict) -> str:
        """A server asks *your* model to generate something.

        Gate it. The prompt is server-authored, it runs on your budget, and the
        output flows back into your agent's context — a prompt-injection vector
        pointed at your inference spend.
        """
        self.sampling_requests.append(request)
        if self.sampling_handler is None:
            raise SamplingRejected("this client does not offer sampling")

        requested = request.get("maxTokens", 1000)
        if requested > self.sampling_token_cap:
            raise SamplingRejected(
                f"requested {requested} tokens, cap is {self.sampling_token_cap}"
            )
        return self.sampling_handler(request)

    def handle_elicitation(self, request: dict) -> dict:
        """A server asks the *user* a question mid-operation."""
        self.elicitation_requests.append(request)
        if self.elicitation_handler is None:
            return {"action": "decline"}
        return self.elicitation_handler(request)

    def list_roots(self) -> list:
        """Scope declaration: where a server may operate."""
        return [{"uri": f"file://{r}", "name": str(r)} for r in self.roots]


# ==========================================================================
# tool-surface budget and the transport threat model
# ==========================================================================

def surface_cost(servers: list, *, tokens_per_definition: int = 270,
                 turns: int = 14, tool_search: bool = False) -> dict:
    """What a connected surface costs before anyone types anything (M6).

    Definitions are re-sent on every turn whether or not any of them are used.
    """
    total_tools = sum(len(s.tools) for s in servers)
    resident = (900 + min(total_tools, 8) * tokens_per_definition
                if tool_search else total_tools * tokens_per_definition + 300)
    return {
        "servers": len(servers),
        "tools": total_tools,
        "tokens_per_turn": resident,
        "tokens_per_task": resident * turns,
        "tool_search": tool_search,
    }


def threat_model(transport: str) -> dict:
    """The comparison Lab 6c requires in writing.

    Transport is a security decision, not a convenience one.
    """
    if transport == "stdio":
        return {
            "transport": "stdio",
            "trust": "inherits the local user",
            "authentication": "none — there is no boundary to authenticate across",
            "reachable_secrets": "every environment variable in the host process",
            "multi_user": False,
            "you_are_trusting": "the package you ran",
            "residual_risks": [
                "an unreviewed dependency runs with your privileges",
                "the server sees your filesystem and environment",
                "tool descriptions enter your model context unreviewed",
            ],
        }
    return {
        "transport": "streamable-http",
        "trust": "explicit, per request",
        "authentication": "OAuth, scoped",
        "reachable_secrets": "only what the granted scopes allow",
        "multi_user": True,
        "you_are_trusting": "the operator and the transport",
        "residual_risks": [
            "you are now operating a service: token validation, rotation, audit",
            "a leaked token is usable until it expires or is revoked",
            "tool descriptions still enter your model context unreviewed",
        ],
    }
