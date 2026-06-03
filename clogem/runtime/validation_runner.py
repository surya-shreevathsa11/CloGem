from __future__ import annotations

from typing import List, Optional, Tuple

from clogem.validation import ValidationReport


def build_validation_report(
    *,
    ok: bool,
    combined_feedback: str,
    tests_rc: int = 0,
    lint_rc: int = 0,
    typecheck_rc: int = 0,
) -> ValidationReport:
    """Build a structured report from combined validation output."""
    text = (combined_feedback or "").strip()
    sections: List[str] = []
    tests_text = ""
    lint_text = ""
    typecheck_text = ""
    for block in text.split("--- COMMAND:"):
        if not block.strip():
            continue
        low = block.lower()
        if low.startswith(" tests") or " tests " in low[:20]:
            tests_text = block
            sections.append("tests")
        elif low.startswith(" lint") or " lint " in low[:20]:
            lint_text = block
            sections.append("lint")
        elif "typecheck" in low[:30]:
            typecheck_text = block
            sections.append("typecheck")
    if not sections:
        tests_text = text
    return ValidationReport(
        ok=ok,
        tests_rc=tests_rc,
        lint_rc=lint_rc,
        typecheck_rc=typecheck_rc,
        tests_text=tests_text,
        lint_text=lint_text,
        typecheck_text=typecheck_text,
        sections=sections,
    )


def format_report_for_coder(report: ValidationReport) -> str:
    return report.as_prompt_block()
