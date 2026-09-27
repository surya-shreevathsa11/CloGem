from __future__ import annotations

import os
import time
from typing import Any, Awaitable, Callable, Optional, Tuple

PLAN_FILENAME = "plan.md"
PLAN_DIRNAME = ".clogem"


def plan_path(repo_root: str) -> str:
    return os.path.join(repo_root, PLAN_DIRNAME, PLAN_FILENAME)


def plan_is_fresh(repo_root: str, ttl_hours: int) -> bool:
    path = plan_path(repo_root)
    if not os.path.isfile(path):
        return False
    age_h = (time.time() - os.path.getmtime(path)) / 3600.0
    return age_h <= max(1, ttl_hours)


def read_plan_block(repo_root: str, ttl_hours: int) -> str:
    if not plan_is_fresh(repo_root, ttl_hours):
        return ""
    try:
        with open(plan_path(repo_root), encoding="utf-8") as f:
            body = f.read().strip()
    except OSError:
        return ""
    if not body:
        return ""
    return f"## Approved plan (.clogem/plan.md)\n\n{body}\n\n"


def write_plan_file(repo_root: str, content: str) -> str:
    path = plan_path(repo_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    return path


def clear_plan_file(repo_root: str) -> bool:
    path = plan_path(repo_root)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def wants_plan_slash(task: str) -> bool:
    t = task.strip().lower()
    return t in ("/plan", "/plan show", "/plan clear") or t.startswith("/plan ")


async def run_plan_slash_command(
    task: str,
    repo_root: str,
    *,
    console: Any,
    Text: Callable[..., Any],
    MUTED: str,
    LOG_OK: str,
    section_rule: Callable[[str], None],
    run_role: Callable[[str, str, str], Awaitable[Tuple[str, str, int]]],
    ttl_hours: int,
) -> bool:
    """Handle /plan show|clear|generation. Returns True if handled."""
    t = task.strip()
    low = t.lower()
    if low == "/plan show":
        block = read_plan_block(repo_root, ttl_hours)
        section_rule("Plan")
        console.print()
        console.print(Text(block or "(no fresh plan on disk)", style=MUTED))
        console.print()
        return True
    if low == "/plan clear":
        clear_plan_file(repo_root)
        console.print(Text("Cleared .clogem/plan.md", style=LOG_OK))
        console.print()
        return True
    if low.startswith("/plan "):
        user_task = t[len("/plan ") :].strip()
    elif low == "/plan":
        console.print(Text("Usage: /plan <task description>", style=MUTED))
        console.print()
        return True
    else:
        return False

    from clogem import prompts as prompt_defs

    prompt = (
        "You are the planner for Clogem. Write a concise implementation plan in markdown.\n"
        "Include: goal, acceptance criteria, target files, risks, out of scope.\n"
        "Do NOT write code fences for full implementations.\n\n"
        f"Task:\n{user_task}\n"
    )
    out, err, rc = await run_role("planner", prompt, "Planner: writing plan...")
    if rc != 0 or not (out or "").strip():
        console.print(Text(f"Plan failed: {err or 'empty'}", style=MUTED))
        console.print()
        return True
    path = write_plan_file(repo_root, out)
    section_rule("Plan saved")
    console.print(Text(f"Wrote: {path}", style=LOG_OK))
    console.print()
    return True
