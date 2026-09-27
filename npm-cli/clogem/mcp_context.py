from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

_MAX_CHARS = 8000


def _jira_key(text: str) -> Optional[str]:
    m = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", text or "")
    return m.group(1) if m else None


def _github_issue_ref(text: str) -> Optional[tuple[str, int]]:
    m = re.search(r"\b([\w.-]+/[\w.-]+)#(\d+)\b", text or "")
    if m:
        return m.group(1), int(m.group(2))
    return None


def gather_mcp_context(task: str, settings: Any) -> str:
    """
    Heuristic MCP context for BUILD (v1 — no extra LLM call).
    Returns a prompt block or empty string.
    """
    from clogem.logging_utils import get_logger

    logger = get_logger(__name__)
    parts: List[str] = []

    try:
        from clogem.mcp_plugins import call_tool, list_plugins
    except Exception:
        return ""

    plugins = list_plugins()
    if not plugins:
        return ""

    jira_key = _jira_key(task)
    if jira_key:
        for name in plugins:
            if "jira" in name.lower():
                ok, out = call_tool(name, "get_issue", {"issueKey": jira_key})
                if ok and out:
                    parts.append(f"### Jira {jira_key} (via {name})\n{out[:3000]}")
                break

    gh = _github_issue_ref(task)
    if gh:
        owner_repo, num = gh
        for name in plugins:
            if "github" in name.lower():
                ok, out = call_tool(
                    name,
                    "issue",
                    {"owner": owner_repo.split("/")[0], "repo": owner_repo.split("/")[1], "number": num},
                )
                if ok and out:
                    parts.append(f"### GitHub {owner_repo}#{num}\n{out[:3000]}")
                break

    if not parts:
        return ""

    block = "## MCP context (auto)\n\n" + "\n\n".join(parts)
    if len(block) > _MAX_CHARS:
        block = block[:_MAX_CHARS] + "\n\n[truncated]"
    return block + "\n\n"
