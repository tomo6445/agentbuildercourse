"""
Shared library for the Building AI Agents labs.

Everything here runs offline against a scripted model, so the labs are
deterministic, free, and safe to run in CI. Swap `ScriptedModel` for `LiveModel`
to point any lab at the real API.
"""

from .cost import Budget, PRICES, project, turn_cost
from .evals import (
    CaseResult, EvalCase, Report, cohens_kappa, run_case, run_suite, validate_judge,
)
from .loop import AgentLoop, AgentRun
from .model import (
    LiveModel, Response, ScriptedModel, ScriptExhausted, TextBlock, ToolUseBlock,
    Usage, call, estimate_tokens, parallel, paused, say, truncated,
)
from .tools import Tool, ToolError, ToolRegistry, error_result, ok_result, tool
from .trace import ToolSpan, Trace, TurnRecord

__all__ = [
    "AgentLoop", "AgentRun", "Budget", "CaseResult", "EvalCase", "LiveModel",
    "PRICES", "Report", "Response", "ScriptExhausted", "ScriptedModel", "TextBlock",
    "Tool", "ToolError", "ToolRegistry", "ToolSpan", "ToolUseBlock", "Trace",
    "TurnRecord", "Usage", "call", "cohens_kappa", "error_result", "estimate_tokens",
    "ok_result", "parallel", "paused", "project", "run_case", "run_suite", "say",
    "tool", "truncated", "turn_cost", "validate_judge",
]
__version__ = "1.0.0"
