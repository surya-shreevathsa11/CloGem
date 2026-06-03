from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, Tuple

from clogem.services.ci_fix_pipeline import fetch_ci_logs, wants_ci_fix_task
from clogem.services.pdf_pipeline import wants_pdf_handling
from clogem.services.plan_pipeline import wants_plan_slash


@dataclass(frozen=True)
class PipelineEntry:
    name: str
    wants: Callable[[str], bool]
    run: Callable[..., Awaitable[Any]]


async def run_task_pipelines(
    task: str,
    *,
    pdf_runner: Callable[[str], Awaitable[bool]],
    plan_runner: Callable[[str], Awaitable[bool]],
    ci_fix_prep: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Try registered pipelines in order.
    Returns (handled, optional_ci_context_to_prepend).
    """
    if wants_plan_slash(task):
        handled = await plan_runner(task)
        return handled, None

    if wants_pdf_handling(task):
        handled = await pdf_runner(task)
        return handled, None

    if ci_fix_prep is not None and wants_ci_fix_task(task):
        ctx = await ci_fix_prep(task)
        return False, ctx

    return False, None
