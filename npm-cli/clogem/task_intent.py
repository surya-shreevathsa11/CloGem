"""Task-shape helpers that do not call a model."""

from __future__ import annotations

import re


def detect_pdf_generation_task(text: str) -> bool:
    """
    True when the user is asking Clogem to generate/export a PDF document.

    Broad patterns: generate/create/make/export/convert/turn ... pdf,
    pdf report/document/file, "as a pdf", "into pdf", "to pdf".
    Does NOT match slash commands (handled by pdf_pipeline directly).
    Does NOT try to exclude "read @file.pdf" — caller handles /pdf separately.
    """
    if not text or len(text.strip()) < 4:
        return False
    t = text.strip().lower()

    # Slash commands are handled by the pipeline directly via wants_pdf_handling
    if t.startswith("/"):
        return False

    # verb + (optional filler) + pdf
    if re.search(
        r"\b(generate|create|make|export|convert|turn|write|produce|build)\b"
        r".{0,60}\bpdf\b",
        t,
        re.DOTALL,
    ):
        return True

    # "pdf report/document/file/summary/version/doc"
    if re.search(r"\bpdf\s+(report|document|file|summary|version|doc)\b", t):
        return True

    # "as a pdf" / "into a pdf" / "to pdf" / "in pdf format"
    if re.search(r"\b(as|into|to|in)\s+(a\s+)?pdf\b", t):
        return True

    # "pdf of ..." / "pdf from ..."
    if re.search(r"\bpdf\s+(of|from)\b", t):
        return True

    return False
