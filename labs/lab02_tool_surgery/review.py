"""
Produce the diff summary for the peer design review the gate requires.

    python -m lab02_tool_surgery.review
"""

from __future__ import annotations

from .harness import evaluate, load


def main() -> int:
    base_reg, mine_reg = load("starter"), load("tools")
    base, mine = evaluate(base_reg), evaluate(mine_reg)

    base_tools = {t.name: t for t in base_reg}
    mine_tools = {t.name: t for t in mine_reg}

    print("# Tool layer design review\n")
    print(f"pass rate      {base['pass_rate']:.0%} -> {mine['pass_rate']:.0%}")
    print(f"tools          {len(base_reg)} -> {len(mine_reg)}")
    print(f"tokens/turn    {base['definition_tokens']:,} -> "
          f"{mine['definition_tokens']:,} "
          f"({mine['definition_tokens'] / base['definition_tokens'] - 1:+.0%})\n")

    removed = sorted(set(base_tools) - set(mine_tools))
    added = sorted(set(mine_tools) - set(base_tools))
    if removed:
        print("## Removed\n" + "\n".join(f"- `{n}`" for n in removed) + "\n")
    if added:
        print("## Added\n" + "\n".join(f"- `{n}`" for n in added) + "\n")

    print("## Per tool\n")
    for name in sorted(set(base_tools) & set(mine_tools)):
        b, m = base_tools[name], mine_tools[name]
        changes = []
        if b.definition_tokens != m.definition_tokens:
            changes.append(f"{b.definition_tokens} -> {m.definition_tokens} tokens")
        b_enums = {k for k, v in b.input_schema["properties"].items() if v.get("enum")}
        m_enums = {k for k, v in m.input_schema["properties"].items() if v.get("enum")}
        if m_enums - b_enums:
            changes.append(f"enums added: {', '.join(sorted(m_enums - b_enums))}")
        b_desc = {k for k, v in b.input_schema["properties"].items() if v.get("description")}
        m_desc = {k for k, v in m.input_schema["properties"].items() if v.get("description")}
        if m_desc - b_desc:
            changes.append(f"described: {', '.join(sorted(m_desc - b_desc))}")
        print(f"- **{name}** — {'; '.join(changes) if changes else 'unchanged'}")

    print("\n## Remaining failures\n")
    if not mine["failures_by_class"]:
        print("None.")
    for cls, rows in sorted(mine["failures_by_class"].items()):
        for tid, reason in rows:
            print(f"- `{tid}` ({cls}) {reason}")

    print("\n## For your reviewer\n")
    print("Write 300 words on: which change bought the most pass rate, which "
          "bought the most token reduction, and which tool you would consolidate "
          "next and why.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
