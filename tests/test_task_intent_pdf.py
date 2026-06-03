"""Tests for detect_pdf_generation_task."""
from __future__ import annotations

import pytest

from clogem.task_intent import detect_pdf_generation_task


@pytest.mark.parametrize(
    "text",
    [
        "generate a pdf",
        "Generate a PDF",
        "create a pdf report",
        "make a PDF of my notes",
        "export this as a pdf",
        "convert to pdf",
        "turn this into a pdf",
        "write a pdf document",
        "produce a pdf file",
        "build a pdf",
        "pdf report of sales",
        "pdf document about cats",
        "pdf file with my content",
        "pdf summary of the meeting",
        "save this as a pdf",
        "export as pdf",
        "into a pdf",
        "to pdf",
        "in pdf format",
        "pdf of this text",
        "pdf from my notes",
        "create a detailed pdf about machine learning",
        "please generate me a pdf with this content",
    ],
)
def test_detect_pdf_true(text: str):
    assert detect_pdf_generation_task(text), f"Expected True for: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "/pdf hello",
        "/pdf @file.txt",
        "read the file report.pdf",
        "open report.pdf",
        "summarize report.pdf",
        "what is in my report.pdf",
        "build a website",
        "create an API endpoint",
        "make a landing page",
        "hello there",
        "",
        "   ",
        "short",
        "implement auth",
    ],
)
def test_detect_pdf_false(text: str):
    assert not detect_pdf_generation_task(text), f"Expected False for: {text!r}"


def test_slash_command_not_detected():
    """Slash commands are excluded — wants_pdf_handling handles them directly."""
    assert not detect_pdf_generation_task("/pdf generate something")
    assert not detect_pdf_generation_task("/build create a pdf")
