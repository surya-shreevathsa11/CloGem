from __future__ import annotations

import os
from typing import Awaitable, Callable, List, Optional, Sequence, Tuple

from clogem.prompts import (
    RESEARCH_COMPILE_PROMPT,
    RESEARCH_INDEPENDENT_PROMPT,
    RESEARCH_MODE_PROMPT_WITH_SOURCES,
    RESEARCH_WEB_PROMPT,
)
from clogem.role_mapping import grok_provider_available

RunModel = Callable[[str, str, str], Awaitable[Tuple[str, str, int]]]


def claude_research_ready() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def research_providers(
    *,
    orchestrator_provider: str,
    grok_ready: Optional[bool] = None,
    claude_ready: Optional[bool] = None,
) -> List[str]:
    """Each available model researches once. The orchestrator's model is always included."""
    grok_ok = grok_provider_available() if grok_ready is None else grok_ready
    claude_ok = claude_research_ready() if claude_ready is None else claude_ready
    panel = ["codex", "gemini"]
    if grok_ok and "grok" not in panel:
        panel.append("grok")
    if claude_ok and "claude" not in panel:
        panel.append("claude")
    orch = (orchestrator_provider or "codex").strip().lower() or "codex"
    if orch not in panel:
        panel.append(orch)
    return panel


def format_research_reports(reports: Sequence[Tuple[str, str, str, int]]) -> str:
    blocks: List[str] = []
    for provider, text, err, rc in reports:
        if rc == 0 and (text or "").strip():
            body = text.strip()
        else:
            detail = (err or "").strip() or "no output"
            body = f"(this researcher failed, exit {rc})\n{detail}"
        blocks.append(f"### {provider}\n{body}")
    return "\n\n".join(blocks)


def _sources_prompt(question: str, sources: str) -> str:
    return (
        RESEARCH_MODE_PROMPT_WITH_SOURCES.replace("__SOURCES__", sources)
        .replace("__TASK__", question)
    )


def _web_prompt(question: str, local_block: str) -> str:
    return (
        RESEARCH_WEB_PROMPT.replace("__LOCAL__", local_block).replace("__TASK__", question)
    )


def _independent_prompt(question: str, local_block: str) -> str:
    return (
        RESEARCH_INDEPENDENT_PROMPT.replace("__LOCAL__", local_block).replace(
            "__TASK__", question
        )
    )


def _compile_prompt(
    *,
    question: str,
    sources: str,
    reports_text: str,
    orchestrator_provider: str,
) -> str:
    return (
        RESEARCH_COMPILE_PROMPT.replace("__ORCH__", orchestrator_provider)
        .replace("__REPORTS__", reports_text)
        .replace("__SOURCES__", sources or "(none)")
        .replace("__TASK__", question)
    )


async def conduct_multi_model_research(
    *,
    question: str,
    sources: str,
    providers: Sequence[str],
    orchestrator_provider: str,
    local_block: str,
    run_provider: RunModel,
    run_gemini_grounded: RunModel,
) -> Tuple[str, str, int, str]:
    """
    Each provider researches independently. The orchestrator then verifies
    conflicts and returns one compiled answer.

    Returns (compiled_text, error, returncode, reports_text).
    """
    question = (question or "(no question)").strip()
    sources = (sources or "").strip()
    orch = (orchestrator_provider or "codex").strip().lower() or "codex"
    reports: List[Tuple[str, str, str, int]] = []

    for provider in providers:
        if sources:
            prompt = _sources_prompt(question, sources)
            text, err, rc = await run_provider(
                provider,
                prompt,
                f"{provider}: /research (from @ sources)...",
            )
        elif provider == "gemini":
            prompt = _web_prompt(question, local_block)
            text, err, rc = await run_gemini_grounded(
                prompt,
                "Gemini: /research (web-grounded)...",
            )
            if rc != 0:
                text, err, rc = await run_provider(
                    "gemini",
                    prompt
                    + "\n\n(Note: Google Search grounding was unavailable. "
                    "Answer conservatively; do not invent citations.)",
                    "Gemini: /research (best-effort)...",
                )
        else:
            text, err, rc = await run_provider(
                provider,
                _independent_prompt(question, local_block),
                f"{provider}: /research...",
            )
        reports.append((provider, text or "", err or "", rc))

    reports_text = format_research_reports(reports)
    compiled, err, rc = await run_provider(
        orch,
        _compile_prompt(
            question=question,
            sources=sources,
            reports_text=reports_text,
            orchestrator_provider=orch,
        ),
        "Orchestrator: verifying and compiling research...",
    )
    return compiled or "", err or "", rc, reports_text
