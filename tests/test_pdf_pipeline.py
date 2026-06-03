"""Unit tests for clogem/services/pdf_pipeline.py."""
from __future__ import annotations

import os
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from clogem.services.pdf_pipeline import (
    PdfPipelineDeps,
    _strip_markdown_fences,
    run_pdf_generation_pipeline,
    wants_pdf_handling,
)


# ---------------------------------------------------------------------------
# wants_pdf_handling
# ---------------------------------------------------------------------------


def test_wants_pdf_slash_command():
    assert wants_pdf_handling("/pdf hello world")
    assert wants_pdf_handling("/pdf")
    assert wants_pdf_handling("/pdf @file.txt output.pdf")


def test_wants_pdf_natural_language():
    assert wants_pdf_handling("generate a pdf about cats")
    assert wants_pdf_handling("create a pdf report of sales")
    assert wants_pdf_handling("export as pdf")


def test_wants_pdf_false_for_non_pdf():
    assert not wants_pdf_handling("build a website")
    assert not wants_pdf_handling("implement auth")
    assert not wants_pdf_handling("hello there")


# ---------------------------------------------------------------------------
# _strip_markdown_fences
# ---------------------------------------------------------------------------


def test_strip_fences_removes_backticks():
    text = "```\nHello world\n```"
    assert _strip_markdown_fences(text) == "Hello world"


def test_strip_fences_removes_typed_backticks():
    text = "```text\nHello world\n```"
    assert _strip_markdown_fences(text) == "Hello world"


def test_strip_fences_passthrough_plain():
    text = "Hello world\n\nSecond paragraph"
    assert _strip_markdown_fences(text) == text


# ---------------------------------------------------------------------------
# Helper to build a PdfPipelineDeps with mocks
# ---------------------------------------------------------------------------


def _make_deps(
    tmp_path,
    gemini_return: tuple = ("Hello PDF\n\nSecond paragraph", "", 0),
    reviewer_return: tuple = ("Hello PDF reviewed\n\nSecond paragraph", "", 0),
) -> PdfPipelineDeps:
    console = MagicMock()
    Text = MagicMock(side_effect=lambda text, style=None: text)

    run_gemini = AsyncMock(return_value=gemini_return)
    run_role = AsyncMock(return_value=reviewer_return)

    cwd = str(tmp_path)

    def _shlex(raw: str) -> List[str]:
        import shlex
        return shlex.split(raw)

    def _mention_roots() -> List[str]:
        return [cwd]

    def _resolve(rel: str) -> Optional[str]:
        return os.path.join(cwd, rel)

    def _allowed(path: str, roots: Any) -> bool:
        real = os.path.realpath(path)
        for r in roots:
            rr = os.path.realpath(r)
            if real == rr or real.startswith(rr + os.sep):
                return True
        return False

    def _read_file(path: str, max_bytes: int) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read(max_bytes)
        except OSError:
            return "[read error]"

    section_rule = MagicMock()

    return PdfPipelineDeps(
        run_gemini=run_gemini,
        run_role=run_role,
        console=console,
        Text=Text,
        MUTED="muted",
        TITLE="title",
        LOG_WARN="warn",
        LOG_ERR="err",
        LOG_OK="ok",
        section_rule=section_rule,
        cwd=cwd,
        timeout_sec=180,
        _shlex_split_cmd=_shlex,
        _mention_roots_list=_mention_roots,
        _resolve_mention_path=_resolve,
        _path_allowed_for_mention=_allowed,
        _read_file_for_mention=_read_file,
    )


# ---------------------------------------------------------------------------
# run_pdf_generation_pipeline — natural-language path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_natural_language_creates_pdf(tmp_path):
    deps = _make_deps(tmp_path)
    task = "generate a pdf about cats"

    handled = await run_pdf_generation_pipeline(task, deps)

    assert handled is True
    # PDF file should exist in tmp_path
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) == 1, f"Expected 1 PDF, found: {pdfs}"


@pytest.mark.asyncio
async def test_pipeline_slash_pdf_creates_pdf(tmp_path):
    deps = _make_deps(tmp_path)
    task = "/pdf This is some content for the PDF"

    handled = await run_pdf_generation_pipeline(task, deps)

    assert handled is True
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) == 1


@pytest.mark.asyncio
async def test_pipeline_slash_pdf_with_explicit_output_name(tmp_path):
    deps = _make_deps(tmp_path)
    out_name = str(tmp_path / "myreport.pdf")
    task = f"/pdf Some content {out_name}"

    handled = await run_pdf_generation_pipeline(task, deps)

    assert handled is True
    assert os.path.exists(out_name)


@pytest.mark.asyncio
async def test_pipeline_returns_true_on_gemini_failure(tmp_path):
    deps = _make_deps(tmp_path, gemini_return=("", "Gemini error", 1))
    task = "generate a pdf about dogs"

    handled = await run_pdf_generation_pipeline(task, deps)

    assert handled is True
    # No PDF should be created
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) == 0


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_draft_when_reviewer_fails(tmp_path):
    deps = _make_deps(tmp_path, reviewer_return=("", "Reviewer error", 1))
    task = "generate a pdf"

    handled = await run_pdf_generation_pipeline(task, deps)

    assert handled is True
    # Still creates PDF from draft
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) == 1


@pytest.mark.asyncio
async def test_pipeline_slash_pdf_no_content_returns_true(tmp_path):
    deps = _make_deps(tmp_path)
    task = "/pdf"

    handled = await run_pdf_generation_pipeline(task, deps)

    assert handled is True
    # No PDF created (usage message printed)
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) == 0


@pytest.mark.asyncio
async def test_pipeline_uses_reviewer_output(tmp_path):
    reviewer_body = "Reviewed content\n\nThis is paragraph two."
    deps = _make_deps(tmp_path, reviewer_return=(reviewer_body, "", 0))
    task = "generate a pdf"

    handled = await run_pdf_generation_pipeline(task, deps)

    assert handled is True
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) == 1
