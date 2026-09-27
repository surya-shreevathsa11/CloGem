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
from clogem.ui import activity_note, gemini_error_is_final, is_model_dump

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


def _report_body(text: str, err: str, rc: int) -> str:
    if rc == 0 and (text or "").strip() and not is_model_dump(text):
        body = text.strip()
    else:
        reason = activity_note(f"{text or ''}\n{err or ''}", rc or 1) or "did not finish"
        body = f"(unavailable: {reason})"
    if len(body) > 6000:
        body = body[:6000] + "\n...[truncated]"
    return body


def research_check_note(reports: Sequence[Tuple[str, str]]) -> str:
    """Same note the website shows under a research reply.

    Keep this in step with web/src/logic/research.js compileResearch.
    """
    usable = [(provider, text.strip()) for provider, text in reports if (text or "").strip()]
    if not usable:
        return "No model answered."
    if len(usable) == 1:
        return "It was not cross-checked."
    groups: List[dict] = []
    for provider, text in usable:
        key = " ".join(text.split()).strip().lower()
        for group in groups:
            if group["key"] == key:
                group["who"].append(provider)
                break
        else:
            groups.append({"key": key, "text": text, "who": [provider]})
    if len(groups) == 1:
        return "they agreed"
    kept = sorted(groups, key=lambda group: (len(group["who"]), len(group["text"])), reverse=True)[0]
    split = "\n".join(f"{', '.join(group['who'])} held: {group['text']}" for group in groups)
    return f"{split}\nKept the claim from {', '.join(kept['who'])}."


def format_research_reports(reports: Sequence[Tuple[str, str, str, int]]) -> str:
    blocks: List[str] = []
    for provider, text, err, rc in reports:
        blocks.append(f"### {provider}\n{_report_body(text, err, rc)}")
    return "\n\n".join(blocks)


def visible_research_reply(
    compiled: str,
    reports: Sequence[Tuple[str, str, str, int]],
) -> str:
    """The text to show. Never a model-list dump or a raw stderr blob."""
    if (compiled or "").strip() and not is_model_dump(compiled):
        return compiled.strip()
    parts: List[str] = []
    for _provider, text, _err, rc in reports:
        if rc == 0 and (text or "").strip() and not is_model_dump(text):
            parts.append(text.strip())
    return "\n\n".join(parts)


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

    Returns (compiled_text, error, returncode, reports_text, check_note).
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
            if rc != 0 and not gemini_error_is_final(err):
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
    compile_prompt = _compile_prompt(
        question=question,
        sources=sources,
        reports_text=reports_text,
        orchestrator_provider=orch,
    )
    compiled, err, rc = await run_provider(
        orch,
        compile_prompt,
        "Orchestrator: verifying and compiling research...",
    )
    if rc != 0 or is_model_dump(compiled or ""):
        for provider, text, _err, provider_rc in reports:
            if provider == orch or provider_rc != 0 or is_model_dump(text):
                continue
            compiled, err, rc = await run_provider(
                provider,
                compile_prompt,
                "Orchestrator: verifying and compiling research...",
            )
            if rc == 0 and not is_model_dump(compiled or ""):
                break
    if rc != 0 or is_model_dump(compiled or ""):
        usable = visible_research_reply("", reports)
        note = research_check_note(
            [
                (provider, text)
                for provider, text, _err, provider_rc in reports
                if provider_rc == 0 and (text or "").strip() and not is_model_dump(text)
            ]
        )
        if usable:
            return usable, "", 0, reports_text, note
    note = research_check_note(
        [
            (provider, text)
            for provider, text, _err, provider_rc in reports
            if provider_rc == 0 and (text or "").strip() and not is_model_dump(text)
        ]
    )
    return compiled or "", err or "", rc, reports_text, note
