"""
Course metadata: the single source of truth for structure.

Lesson prose lives in content/mNN.md. This file holds everything the hub page,
the navigation, and the per-module headers need to agree on.
"""

COURSE = {
    "title": "Building AI Agents",
    "subtitle": "from first principles to production",
    "version": "v1.0",
    "standfirst": (
        "Sixteen modules for working developers. You write the agent loop by hand before "
        "you're allowed near a framework — then you learn to evaluate it, secure it, cost it, "
        "and ship it. Claude-first stack; transferable mechanics."
    ),
    "weeks": 10,
}

PHASES = [
    {"id": 0, "num": "Phase 0", "name": "Mechanics",
     "blurb": "No frameworks. You build the loop, the tools, and the context strategy by hand, and you build the trace viewer that makes all of it visible. Everything later is measured against what you built here."},
    {"id": 1, "num": "Phase 1", "name": "Building blocks",
     "blurb": "Choose the right amount of autonomy, then adopt the production harness and the integration protocol — with every abstraction mapped back to the line of Phase 0 code it replaces."},
    {"id": 2, "num": "Phase 2", "name": "Making agents good",
     "blurb": "State, evaluation, and orchestration. This is where demos become products, and where most projects quietly die for want of an eval suite."},
    {"id": 3, "num": "Phase 3", "name": "Production",
     "blurb": "Observability, security, economics, and the human interface. Four things that are invisible on a laptop and fatal at scale."},
    {"id": 4, "num": "Phase 4", "name": "Applied",
     "blurb": "Package what you know, study eight domains that each punish a different mistake, then ship one real thing and defend it."},
]

MODULES = [
    {
        "n": "M1", "phase": 0, "hrs": 2.5, "core": True,
        "title": "The Loop: what an agent actually is",
        "line": "An agent is a while-loop with a language model in it. Everything else is ergonomics.",
        "tags": ["Messages API", "tool_use protocol", "termination", "no frameworks"],
        "labs": ["labs/lab01_tinyagent", "labs/lab01b_observatory"],
        "gate": "12 assertions including two parallel tool_use blocks in one turn, graceful is_error results, termination under a permanently-failing tool, and a trace the Observatory renders.",
        "gate_cmd": "pytest labs/lab01_tinyagent -q",
    },
    {
        "n": "M2", "phase": 0, "hrs": 3.0, "core": True,
        "title": "Tools: designing the agent's hands",
        "line": "Agent-tool interfaces are as critical as human-computer interfaces, and get a fraction of the care.",
        "tags": ["schema design", "tool_choice", "consolidation", "namespacing", "poka-yoke"],
        "labs": ["labs/lab02_tool_surgery"],
        "gate": "≥85% on a held-out eval set below baseline token cost, plus a 300-word design review of a classmate's tool layer.",
        "gate_cmd": "pytest labs/lab02_tool_surgery -q",
    },
    {
        "n": "M3", "phase": 0, "hrs": 3.0, "core": True,
        "title": "Context: the finite resource",
        "line": "Every token you add is a token of attention you spend. Context is a budget, not a bucket.",
        "tags": ["context rot", "system prompt altitude", "JIT retrieval", "compaction", "caching"],
        "labs": ["labs/lab03_context"],
        "gate": "Research agent holds ≥90% of baseline accuracy at turn 60 under a fixed cost ceiling.",
        "gate_cmd": "pytest labs/lab03_context -q",
    },
    {
        "n": "M4", "phase": 1, "hrs": 2.5, "core": True,
        "title": "Workflows vs. Agents: choosing the right autonomy",
        "line": "The most common architectural error in this field is reaching for an agent when a workflow would do.",
        "tags": ["5 patterns", "orchestrator-workers", "evaluator-optimiser", "decision framework"],
        "labs": ["labs/lab04_patterns"],
        "gate": "All five implementations pass; comparison table complete; memo defends a choice with numbers. First graded Decision Log entry.",
        "gate_cmd": "pytest labs/lab04_patterns -q",
    },
    {
        "n": "M5", "phase": 1, "hrs": 3.5, "core": True,
        "title": "The Claude Agent SDK: from hand-rolled to harness",
        "line": "Here's the loop you should actually ship — and exactly which of your lines it replaces.",
        "tags": ["Agent SDK", "sessions", "hooks", "permissions", "structured output"],
        "labs": ["labs/lab05_sdk_port"],
        "gate": "Ported agent passes M3's eval suite unchanged, plus new tests for resume-after-kill, cost-ceiling abort, and permission denial.",
        "gate_cmd": "pytest labs/lab05_sdk_port -q",
    },
    {
        "n": "M6", "phase": 1, "hrs": 4.0, "core": True,
        "title": "MCP: the integration layer",
        "line": "An agent is worth roughly what it can reach. MCP is how it reaches.",
        "tags": ["protocol", "servers & clients", "sampling", "elicitation", "transports", "OAuth"],
        "labs": ["labs/lab06_mcp"],
        "gate": "Server passes conformance + tool-design rubric; client drives sampling and elicitation; remote deployment passes an auth suite.",
        "gate_cmd": "pytest labs/lab06_mcp -q",
    },
    {
        "n": "M7", "phase": 2, "hrs": 3.0, "core": True,
        "title": "Memory and state",
        "line": "A stateless agent is a colleague with amnesia. A badly-stated agent has false memories, which is worse.",
        "tags": ["memory tool", "sessions", "compaction", "path traversal", "memory poisoning"],
        "labs": ["labs/lab07_memory"],
        "gate": "Task completes across kills; attack suite fully blocked; memory stays under budget across 20 simulated sessions.",
        "gate_cmd": "pytest labs/lab07_memory -q",
    },
    {
        "n": "M8", "phase": 2, "hrs": 3.5, "core": True,
        "title": "Evaluation: the discipline that separates demos from products",
        "line": "If you cannot evaluate it, you cannot improve it, and you should not ship it.",
        "tags": ["eval sets", "LLM-as-judge", "trajectory eval", "CI", "judge validation"],
        "labs": ["labs/lab08_evals"],
        "gate": "Suite runs in CI under a cost cap; judge-human agreement above threshold; suite catches three injected regressions in a provided broken agent.",
        "gate_cmd": "pytest labs/lab08_evals -q",
    },
    {
        "n": "M9", "phase": 2, "hrs": 3.0, "core": True,
        "title": "Multi-agent systems: when more agents help",
        "line": "Multi-agent systems can burn many times the tokens of a single chat. The task has to be worth it.",
        "tags": ["orchestrator-workers", "subagents", "delegation prompts", "effort scaling", "token economics"],
        "labs": ["labs/lab09_multiagent"],
        "gate": "Beats the single-agent baseline on rubric and passes a cost-per-task ceiling; economics report complete.",
        "gate_cmd": "pytest labs/lab09_multiagent -q",
    },
    {
        "n": "M10", "phase": 3, "hrs": 2.5, "core": True,
        "title": "Observability and debugging",
        "line": "You cannot debug what you cannot see. Agents are the least observable software most teams have shipped.",
        "tags": ["OpenTelemetry", "failure taxonomy", "replay debugging", "privacy-preserving traces"],
        "labs": ["labs/lab10_observability"],
        "gate": "All three broken agents correctly root-caused in writing; waterfall renders with accurate cost attribution.",
        "gate_cmd": "pytest labs/lab10_observability -q",
    },
    {
        "n": "M11", "phase": 3, "hrs": 3.0, "core": True,
        "title": "Security: agents that can't be turned against you",
        "line": "Every document your agent reads is untrusted input to a system that holds tools.",
        "tags": ["prompt injection", "lethal trifecta", "sandboxing", "credential proxy", "egress control"],
        "labs": ["labs/lab11_security"],
        "gate": "Survives the full attack suite plus three unseen attacks; written threat model for your own capstone design.",
        "gate_cmd": "pytest labs/lab11_security -q",
    },
    {
        "n": "M12", "phase": 3, "hrs": 3.0, "core": True,
        "title": "Cost, latency and reliability engineering",
        "line": "The prototype cost $2 a day. The rollout costs $40,000 a month. Have this conversation first.",
        "tags": ["cost modelling", "prompt caching", "model routing", "durable execution", "rainbow deploys"],
        "labs": ["labs/lab12_cost_chaos"],
        "gate": "Cost target met within accuracy tolerance; chaos suite passes; dashboard accurate to within 5% of billed usage.",
        "gate_cmd": "pytest labs/lab12_cost_chaos -q",
    },
    {
        "n": "M13", "phase": 3, "hrs": 2.5, "core": False,
        "title": "Human-in-the-loop and interface design",
        "line": "The hard question isn't “can the agent do it” but “when should it ask, and how does a human know whether to say yes.”",
        "tags": ["autonomy ladder", "approval design", "steering", "trust calibration", "streaming UX"],
        "labs": ["labs/lab13_hitl"],
        "gate": "Functional checklist plus a usability rubric scored by three peers, and a written summary of what testing changed.",
        "gate_cmd": "pytest labs/lab13_hitl -q",
    },
    {
        "n": "M14", "phase": 4, "hrs": 2.5, "core": True,
        "title": "Skills, plugins and packaging capability",
        "line": "Tools give an agent hands. Skills give it a trade.",
        "tags": ["SKILL.md", "progressive disclosure", "plugins", "distribution trust"],
        "labs": ["labs/lab14_skills"],
        "gate": "Measurable eval improvement; plugin installs and works from a clean environment; a peer can use it from the README alone.",
        "gate_cmd": "pytest labs/lab14_skills -q",
    },
    {
        "n": "M15", "phase": 4, "hrs": 3.0, "core": False,
        "title": "Applied patterns: eight domains, eight architectures",
        "line": "The patterns are the same. The failure modes are not.",
        "tags": ["case studies", "reference architectures", "deployment shape"],
        "labs": ["labs/lab15_domains"],
        "gate": "Two mini-implementations pass smoke tests; a one-page architecture brief for each, in capstone format.",
        "gate_cmd": "pytest labs/lab15_domains -q",
    },
    {
        "n": "M16", "phase": 4, "hrs": 8.0, "core": True, "capstone": True,
        "title": "Capstone: ship one real thing and defend it",
        "line": "Two students can build the same agent and receive very different grades. Judgement is weighted highest.",
        "tags": ["eval-first", "threat model", "panel defence", "2 weeks"],
        "labs": ["labs/lab16_capstone"],
        "gate": "≥70% across problem fit, engineering quality, evaluation rigour, security posture, and Decision Log judgement — plus a defence that survives both mandatory questions.",
        "gate_cmd": "python -m lab16_capstone.checklist",
    },
]

CAPSTONE_STAGES = [
    {"n": "01", "t": "Problem definition", "w": "10%",
     "d": "User, task, success criteria, why an agent (M4 framework applied), estimated value per task."},
    {"n": "02", "t": "Eval-first design", "w": "20%",
     "d": "≥30 cases, rubric, validated judge — committed before a line of agent code."},
    {"n": "03", "t": "Architecture", "w": "15%",
     "d": "Diagram plus Decision Log entries: autonomy level, tools, context, memory, single vs. multi-agent, deployment."},
    {"n": "04", "t": "Build", "w": "20%",
     "d": "Working agent on the Agent SDK, with MCP integration where the domain warrants it."},
    {"n": "05", "t": "Harden", "w": "15%",
     "d": "Threat model, sandboxing, egress and credential posture, red-team results."},
    {"n": "06", "t": "Instrument", "w": "10%",
     "d": "Traces, cost dashboard, alerting, a documented failure taxonomy for this agent."},
    {"n": "07", "t": "Ship &amp; defend", "w": "10%",
     "d": "10-minute demo, 10-minute panel defence, two mandatory questions."},
]

PILLARS = [
    {"n": "PILLAR 01", "h": "First principles before abstractions",
     "p": "Module 1 is a small agent against the raw API, no SDK. Every later abstraction is mapped back to the line it replaces. Students who understand the loop can debug any harness; students who only know a harness can debug nothing."},
    {"n": "PILLAR 02", "h": "Informating, not just automating",
     "p": "The course spine is the Observatory — a trace viewer students build in M1 and extend for fifteen modules. Token counts, context occupancy, decision points, cost. By the end they aren't guessing why an agent misbehaved; they're reading it."},
    {"n": "PILLAR 03", "h": "Ship gates, not quizzes",
     "p": "No module ends in multiple choice alone. Each ends in a runnable eval suite the artifact must pass — machine-graded where possible, rubric and peer review where not. The M8 gate is “write the eval suite for M5's agent.” The course eats its own tail on purpose."},
]


def module_by_n(n):
    for m in MODULES:
        if m["n"] == n:
            return m
    raise KeyError(n)


def slug_for(m):
    """m01 … m16 — the on-disk name for a module's content and page."""
    return "m%02d" % int(m["n"][1:])
