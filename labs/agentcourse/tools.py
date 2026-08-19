"""
Tool definitions, registry and dispatch.

The `@tool` decorator generates a schema from a function's signature and
docstring, which makes the docstring the tool description — so everything in M2
applies to it directly.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, get_args, get_origin

JSON_TYPES = {
    str: "string", int: "integer", float: "number",
    bool: "boolean", list: "array", dict: "object",
}


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable

    @property
    def definition(self) -> dict:
        """The dict you put in the `tools` list of a request."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @property
    def definition_tokens(self) -> int:
        from .model import estimate_tokens
        return estimate_tokens(self.definition)

    def __call__(self, **kwargs):
        return self.fn(**kwargs)


# --------------------------------------------------------------------------
# docstring parsing
# --------------------------------------------------------------------------

_ARGS_HEADER = re.compile(r"^\s*(Args|Arguments|Parameters):\s*$", re.M)
_ARG_LINE = re.compile(r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)$")


def parse_docstring(doc: str) -> tuple[str, dict]:
    """Split a Google-style docstring into (description, {param: description})."""
    if not doc:
        return "", {}
    doc = inspect.cleandoc(doc)
    m = _ARGS_HEADER.search(doc)
    if not m:
        return doc.strip(), {}

    description = doc[: m.start()].strip()
    params, current = {}, None
    for line in doc[m.end():].splitlines():
        if not line.strip():
            continue
        if re.match(r"^\s*(Returns|Raises|Yields|Example|Note)s?:\s*$", line):
            break
        hit = _ARG_LINE.match(line)
        if hit and not line.startswith("      "):
            current = hit.group(1)
            params[current] = hit.group(2).strip()
        elif current:
            params[current] += " " + line.strip()
    return description, params


def json_type(annotation) -> dict:
    """Map a Python annotation onto a JSON Schema fragment."""
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        item = json_type(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item}
    if origin is dict:
        return {"type": "object"}
    return {"type": JSON_TYPES.get(annotation, "string")}


def tool(fn: Callable | None = None, *, name: str | None = None,
         enum: dict | None = None) -> Tool | Callable:
    """Turn a function into a Tool, deriving the schema from its signature.

    The docstring becomes the description and the per-parameter descriptions.
    `enum` closes a parameter to a fixed set — the poka-yoke from M2::

        @tool(enum={"status": ["active", "churned", "trial", "any"]})
        def crm_search(query: str, status: str = "any") -> str:
            ...
    """
    def build(f: Callable) -> Tool:
        description, param_docs = parse_docstring(f.__doc__ or "")
        sig = inspect.signature(f)
        properties, required = {}, []
        for pname, param in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            schema = json_type(param.annotation)
            if enum and pname in enum:
                schema["enum"] = list(enum[pname])
            if pname in param_docs:
                schema["description"] = param_docs[pname]
            properties[pname] = schema
            if param.default is inspect.Parameter.empty:
                required.append(pname)
        return Tool(
            name=name or f.__name__,
            description=description,
            input_schema={
                "type": "object", "properties": properties, "required": required,
            },
            fn=f,
        )

    return build if fn is None else build(fn)


# --------------------------------------------------------------------------
# registry and dispatch
# --------------------------------------------------------------------------


class ToolError(Exception):
    """Raised by a tool to signal a failure the model should see and act on."""


class ToolRegistry:
    """Holds tools and executes calls, turning failures into results."""

    def __init__(self, *tools: Tool):
        self._tools: dict[str, Tool] = {}
        for t in tools:
            self.add(t)

    def add(self, t: Tool) -> None:
        if t.name in self._tools:
            raise ValueError(f"duplicate tool name: {t.name}")
        self._tools[t.name] = t

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    @property
    def definitions(self) -> list[dict]:
        return [t.definition for t in self._tools.values()]

    @property
    def definition_tokens(self) -> int:
        """What this tool surface costs you on every single turn (M2)."""
        return sum(t.definition_tokens for t in self._tools.values())

    def execute(self, block) -> dict:
        """Run one tool_use block and return a tool_result block.

        Never raises: an unknown tool, a bad argument or a failing tool all come
        back as `is_error` results the model can read and recover from.
        """
        t = self._tools.get(block.name)
        if t is None:
            return error_result(
                block.id,
                f"Unknown tool '{block.name}'. Available tools: "
                f"{', '.join(self.names)}.",
            )
        try:
            output = t(**block.input)
        except TypeError as exc:
            return error_result(
                block.id,
                f"Invalid arguments for '{block.name}': {exc}. "
                f"Expected: {json.dumps(t.input_schema['properties'])}",
            )
        except ToolError as exc:
            return error_result(block.id, str(exc))
        except Exception as exc:                              # noqa: BLE001
            return error_result(block.id, f"{type(exc).__name__}: {exc}")
        return ok_result(block.id, output)


def ok_result(tool_use_id: str, content: Any) -> dict:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content if isinstance(content, str) else json.dumps(content, default=str),
    }


def error_result(tool_use_id: str, message: str) -> dict:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": f"Error: {message}",
        "is_error": True,
    }
