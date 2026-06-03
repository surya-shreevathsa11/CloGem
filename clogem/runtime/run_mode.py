from __future__ import annotations

import sys
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple


async def run_one_turn(
    task: str,
    *,
    run_role: Callable[[str, str, str], Awaitable[Tuple[str, str, int]]],
    run_gemini: Callable[[str, str], Awaitable[Tuple[str, str, int]]],
    session: Any,
    settings: Any,
    console: Any,
    Text: Callable[..., Any],
    MUTED: str,
    TITLE: str,
    LOG_WARN: str,
    LOG_ERR: str,
    LOG_OK: str,
    section_rule: Callable[[str], None],
    json_trace: bool = False,
    verbose: bool = False,
) -> int:
"""
Legacy helper; production `clogem run` uses the full REPL turn path via
``_single_run_mode`` in ``clogem.cli.async_main``. Kept for tests/extensions.
"""
    import asyncio
    from clogem.turn_trace import begin_turn, end_turn, write_last_turn

    log_dir = getattr(settings, "log_dir", ".clogem/logs") if settings else ".clogem/logs"
    issue = getattr(session, "linked_issue", None) if session else None

    trace = begin_turn({"task_preview": task[:80], "issue": issue})
    exit_code = 0

    try:
        console.print(Text(f"[clogem run] task: {task[:120]}", style=MUTED))
        console.print()

        out, err, rc = await run_role("orchestrator", task, "Orchestrator: processing task...")

        if rc != 0:
            console.print(Text(f"[clogem run] ERROR (rc={rc})", style=LOG_ERR))
            if (err or "").strip():
                console.print(Text((err or "").strip()[:1200], style=LOG_ERR))
            exit_code = 1
        else:
            reply = (out or "").strip()
            if reply:
                section_rule("Reply")
                console.print()
                console.print(reply)
                console.print()

    except Exception as exc:
        console.print(Text(f"[clogem run] Unexpected error: {exc}", style=LOG_ERR))
        exit_code = 1
    finally:
        tr = end_turn(success=(exit_code == 0))
        path = write_last_turn(tr, log_dir)
        if json_trace and path:
            console.print(Text(f"[clogem] trace: {path}", style=MUTED))

    return exit_code
