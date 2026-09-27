from __future__ import annotations

import asyncio

from clogem.services.research import (
    conduct_multi_model_research,
    format_research_reports,
    research_providers,
)


def test_research_providers_include_orchestrator_and_skip_missing_optionals():
    panel = research_providers(
        orchestrator_provider="codex",
        grok_ready=False,
        claude_ready=False,
    )
    assert panel == ["codex", "gemini"]

    panel = research_providers(
        orchestrator_provider="claude",
        grok_ready=True,
        claude_ready=True,
    )
    assert panel == ["codex", "gemini", "grok", "claude"]


def test_research_providers_add_orchestrator_when_it_is_not_already_on_the_panel():
    panel = research_providers(
        orchestrator_provider="grok",
        grok_ready=False,
        claude_ready=False,
    )
    assert panel == ["codex", "gemini", "grok"]


def test_format_research_reports_keeps_failures_as_missing_evidence():
    text = format_research_reports(
        [
            ("codex", "alpha", "", 0),
            ("gemini", "", "search down", 1),
        ]
    )
    assert "### codex\nalpha" in text
    assert "### gemini" in text
    assert "search down" in text
    assert "unavailable" in text


def test_format_research_reports_hides_model_list_dumps():
    dump = (
        "ERROR codex models manager: failed to refresh available models: "
        "unknown variant 'max' body: {\"models\":[{\"slug\":\"gpt-5.5\"}]}"
    )
    text = format_research_reports([("codex", dump, dump, 1)])
    assert "gpt-5.5" not in text
    assert "update the Codex CLI" in text
    assert "unavailable" in text


def test_missing_api_key_skips_the_gemini_retry_and_stays_short():
    calls: list[str] = []

    async def run_provider(provider: str, prompt: str, status: str):
        calls.append(status)
        if "best-effort" in status:
            raise AssertionError("gemini was retried after a missing API key")
        if "compile one answer" in prompt.lower():
            return "compiled", "", 0
        return f"{provider} ok", "", 0

    async def run_gemini_grounded(prompt: str, status: str):
        return "", "No API key was provided. Please pass a valid API key.", 1

    compiled, _err, rc, reports = asyncio.run(
        conduct_multi_model_research(
            question="topic",
            sources="",
            providers=["codex", "gemini"],
            orchestrator_provider="codex",
            local_block="now",
            run_provider=run_provider,
            run_gemini_grounded=run_gemini_grounded,
        )
    )
    assert rc == 0
    assert compiled == "compiled"
    assert "needs an API key" in reports


def test_rejected_api_key_skips_the_gemini_retry():
    calls: list[str] = []

    async def run_provider(provider: str, prompt: str, status: str):
        calls.append(status)
        if "best-effort" in status:
            raise AssertionError("gemini was retried after a rejected API key")
        if "compile one answer" in prompt.lower():
            return "compiled", "", 0
        return f"{provider} ok", "", 0

    async def run_gemini_grounded(prompt: str, status: str):
        return "", "401 UNAUTHENTICATED. {'error': {'code': 401, 'message': 'Request had invalid authentication credentials.'}}", 1

    compiled, _err, rc, reports = asyncio.run(
        conduct_multi_model_research(
            question="topic",
            sources="",
            providers=["codex", "gemini"],
            orchestrator_provider="codex",
            local_block="now",
            run_provider=run_provider,
            run_gemini_grounded=run_gemini_grounded,
        )
    )
    assert rc == 0
    assert compiled == "compiled"
    assert "API key was rejected" in reports
    assert "401" not in reports
    assert "https://" not in reports


def test_compile_falls_back_when_the_orchestrator_dumps_its_model_list():
    async def run_provider(provider: str, prompt: str, status: str):
        if "compile one answer" in prompt.lower():
            if provider == "codex":
                return "", "failed to refresh available models: unknown variant 'max'", 1
            return "Earth formed from a disk of dust.", "", 0
        if provider == "grok":
            return "Grok notes on formation.", "", 0
        return "", "failed to refresh available models: unknown variant 'max'", 1

    async def run_gemini_grounded(prompt: str, status: str):
        return "", "No API key was provided.", 1

    compiled, _err, rc, reports = asyncio.run(
        conduct_multi_model_research(
            question="how the world was made",
            sources="",
            providers=["codex", "gemini", "grok"],
            orchestrator_provider="codex",
            local_block="now",
            run_provider=run_provider,
            run_gemini_grounded=run_gemini_grounded,
        )
    )
    assert rc == 0
    assert compiled == "Earth formed from a disk of dust."
    assert "unknown variant" not in reports
    assert "gpt-" not in reports


def test_format_research_reports_truncates_a_huge_report():
    text = format_research_reports([("codex", "x" * 7000, "", 0)])
    assert "...[truncated]" in text
    assert len(text) < 6200


def test_each_model_researches_then_orchestrator_compiles_conflicts():
    calls: list[tuple[str, str]] = []

    async def run_provider(provider: str, prompt: str, status: str):
        calls.append((provider, prompt))
        if "Compile one answer" in prompt or "compile one answer" in prompt.lower():
            return "compiled", "", 0
        if provider == "codex":
            return "Codex says 4", "", 0
        if provider == "grok":
            return "Grok says 5", "", 0
        return f"{provider} report", "", 0

    async def run_gemini_grounded(prompt: str, status: str):
        calls.append(("gemini-grounded", prompt))
        return "Gemini says 4", "", 0

    compiled, err, rc, reports = asyncio.run(
        conduct_multi_model_research(
            question="How many moons?",
            sources="",
            providers=["codex", "gemini", "grok"],
            orchestrator_provider="codex",
            local_block="now",
            run_provider=run_provider,
            run_gemini_grounded=run_gemini_grounded,
        )
    )

    assert rc == 0
    assert err == ""
    assert compiled == "compiled"
    assert [name for name, _ in calls] == [
        "codex",
        "gemini-grounded",
        "grok",
        "codex",
    ]
    assert "Google Search grounding" not in calls[0][1]
    assert "Google Search grounding" in calls[1][1]
    assert "Google Search grounding" not in calls[2][1]
    compile_prompt = calls[-1][1]
    assert "Codex says 4" in compile_prompt
    assert "Gemini says 4" in compile_prompt
    assert "Grok says 5" in compile_prompt
    assert "do not average" in compile_prompt.lower() or "Do not average" in compile_prompt
    assert "### codex" in reports


def test_one_researcher_failure_still_reaches_the_compiler():
    async def run_provider(provider: str, prompt: str, status: str):
        if "provider name" in prompt and "### " in prompt:
            return "compiled anyway", "", 0
        if provider == "grok":
            return "", "grok down", 1
        if provider == "gemini":
            return "", "gemini down", 1
        return f"{provider} ok", "", 0

    async def run_gemini_grounded(prompt: str, status: str):
        return "", "no search", 1

    compiled, err, rc, reports = asyncio.run(
        conduct_multi_model_research(
            question="topic",
            sources="",
            providers=["codex", "gemini", "grok"],
            orchestrator_provider="codex",
            local_block="now",
            run_provider=run_provider,
            run_gemini_grounded=run_gemini_grounded,
        )
    )

    assert rc == 0
    assert compiled == "compiled anyway"
    assert err == ""
    assert "grok down" in reports
    assert "gemini down" in reports
    assert "codex ok" in reports


def test_attached_sources_skip_web_grounding():
    calls: list[str] = []

    async def run_provider(provider: str, prompt: str, status: str):
        calls.append(prompt)
        if provider == "codex" and "Compile" in prompt:
            return "from sources", "", 0
        return f"{provider} sourced", "", 0

    async def run_gemini_grounded(prompt: str, status: str):
        raise AssertionError("web grounding must not run when @ sources are attached")

    compiled, err, rc, reports = asyncio.run(
        conduct_multi_model_research(
            question="What does the note say?",
            sources="[S1] notes.md\nThe note says blue.",
            providers=["codex", "gemini"],
            orchestrator_provider="codex",
            local_block="now",
            run_provider=run_provider,
            run_gemini_grounded=run_gemini_grounded,
        )
    )

    assert rc == 0
    assert compiled == "from sources"
    assert err == ""
    assert all("Google Search grounding" not in prompt for prompt in calls)
    assert any("The note says blue." in prompt for prompt in calls)
    assert "The note says blue." in calls[-1]
    assert "gemini sourced" in reports
