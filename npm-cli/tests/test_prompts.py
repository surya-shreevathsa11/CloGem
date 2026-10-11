from __future__ import annotations

from clogem.prompts import build_gemini_review_prompt


def test_build_gemini_review_prompt_injects_context_and_code() -> None:
    p = build_gemini_review_prompt("ctx", "code")
    assert "ctx" in p
    assert "code" in p
