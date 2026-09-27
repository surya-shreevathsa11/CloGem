from __future__ import annotations

from typing import Any, Optional


def build_extra_context_blocks(
    *,
    task_clean: str,
    repo_root: str,
    settings: Any,
    ci_context: Optional[str] = None,
) -> str:
    """
    Assemble optional context prepended to BUILD prompts (plan, MCP, CI).
    """
    from clogem.mcp_context import gather_mcp_context
    from clogem.services.plan_pipeline import read_plan_block

    parts = []
    if ci_context:
        parts.append(ci_context.strip())
    plan = read_plan_block(repo_root, int(getattr(settings, "plan_ttl_hours", 48)))
    if plan:
        parts.append(plan)
    mcp = gather_mcp_context(task_clean, settings)
    if mcp:
        parts.append(mcp)
    return "\n".join(p for p in parts if p).strip() + ("\n\n" if parts else "")
