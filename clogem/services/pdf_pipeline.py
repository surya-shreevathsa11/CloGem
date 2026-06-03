from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from clogem.task_intent import detect_pdf_generation_task


def wants_pdf_handling(task: str) -> bool:
    """True when the task should be handled by the PDF generation pipeline."""
    stripped = task.strip()
    if stripped.startswith("/pdf"):
        return True
    return detect_pdf_generation_task(stripped)


@dataclass(frozen=True)
class PdfPipelineDeps:
    run_gemini: Callable[[str, str], Awaitable[Tuple[str, str, int]]]
    run_role: Callable[[str, str, str], Awaitable[Tuple[str, str, int]]]
    console: Any
    Text: Callable[..., Any]
    MUTED: str
    TITLE: str
    LOG_WARN: str
    LOG_ERR: str
    LOG_OK: str
    section_rule: Callable[[str], None]
    cwd: str
    timeout_sec: int
    _shlex_split_cmd: Callable[[str], List[str]]
    _mention_roots_list: Callable[[], List[str]]
    _resolve_mention_path: Callable[[str], Optional[str]]
    _path_allowed_for_mention: Callable[[str, Any], bool]
    _read_file_for_mention: Callable[[str, int], str]


def _parse_slash_pdf_body(task: str, deps: PdfPipelineDeps) -> Tuple[str, Optional[str]]:
    """
    Parse '/pdf <content> [out.pdf]' into (body_text, desired_out_path).

    Returns ("", None) if there is no usable content.
    """
    rest = task[len("/pdf"):].strip()
    if not rest:
        return "", None

    tokens = deps._shlex_split_cmd(rest)
    if not tokens:
        return "", None

    desired_out: Optional[str] = None
    if len(tokens) >= 2 and tokens[-1].lower().endswith(".pdf"):
        desired_out = tokens[-1]
        content_tokens = tokens[:-1]
    else:
        content_tokens = tokens

    body = ""
    if (
        len(content_tokens) == 1
        and content_tokens[0].startswith("@")
        and not content_tokens[0].startswith("@@")
    ):
        rel = content_tokens[0][1:]
        roots = deps._mention_roots_list()
        abs_p = deps._resolve_mention_path(rel)
        if abs_p and deps._path_allowed_for_mention(abs_p, roots):
            try:
                max_b = max(4096, int(os.environ.get("CLOGEM_AT_MAX_FILE_BYTES", "400000")))
            except ValueError:
                max_b = 400000
            body = deps._read_file_for_mention(abs_p, max_b)
        else:
            body = ""
    else:
        body = " ".join(content_tokens).strip()

    return body, desired_out


def _strip_markdown_fences(text: str) -> str:
    """Remove leading/trailing triple-backtick fences from LLM output."""
    text = text.strip()
    text = re.sub(r"^```[^\n]*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


async def run_pdf_generation_pipeline(task: str, deps: PdfPipelineDeps) -> bool:
    """
    Run the Gemini-draft + reviewer + ReportLab PDF generation pipeline.

    Returns True if the pipeline handled the request (success or graceful error).
    Returns False only if this task is not a PDF request (shouldn't normally happen
    since callers check wants_pdf_handling first).
    """
    from clogem.pdf_tools import generate_pdf_from_text, pdf_path_for_text_request
    from clogem.prompts import build_pdf_gemini_draft_prompt, build_pdf_reviewer_prompt

    console = deps.console
    Text = deps.Text

    is_slash = task.strip().startswith("/pdf")

    # --- Parse content ---
    if is_slash:
        source_content, desired_out = _parse_slash_pdf_body(task, deps)
        user_request = task.strip()
        if not source_content and not task.strip()[len("/pdf"):].strip():
            console.print(
                Text(
                    "Usage: /pdf <text> [out.pdf]  OR  /pdf @path/to/file.txt [out.pdf]",
                    style=deps.MUTED,
                )
            )
            console.print()
            return True
    else:
        source_content = ""
        desired_out = None
        user_request = task.strip()

    # --- Validate write path early ---
    from clogem.pdf_tools import pdf_path_for_text_request  # noqa: F811

    final_path, display_name = pdf_path_for_text_request(deps.cwd, desired_out)
    roots = deps._mention_roots_list()
    final_abs = os.path.realpath(final_path)
    if not any(
        final_abs == os.path.realpath(r)
        or final_abs.startswith(os.path.realpath(r) + os.sep)
        for r in roots
    ):
        console.print(
            Text(
                "Refusing to write PDF outside the allowed workspace.", style=deps.LOG_WARN
            )
        )
        console.print()
        return True

    # --- Step 1: Gemini drafts the PDF body ---
    draft_prompt = build_pdf_gemini_draft_prompt(user_request, source_content)
    draft_out, draft_err, draft_rc = await deps.run_gemini(
        draft_prompt, "Gemini: drafting PDF content..."
    )
    if draft_rc != 0 or not draft_out.strip():
        console.print(
            Text(
                f"PDF draft failed: {draft_err or 'Gemini returned no content.'}",
                style=deps.LOG_ERR,
            )
        )
        console.print()
        return True

    draft_body = _strip_markdown_fences(draft_out)

    # --- Step 2: Reviewer role checks and refines the body ---
    review_prompt = build_pdf_reviewer_prompt(user_request, draft_body)
    rev_out, rev_err, rev_rc = await deps.run_role(
        "reviewer", review_prompt, "Reviewer: checking PDF content..."
    )
    if rev_rc == 0 and rev_out.strip():
        reviewed_body = _strip_markdown_fences(rev_out)
    else:
        # Reviewer failed — fall back to Gemini draft
        reviewed_body = draft_body

    if not reviewed_body.strip():
        reviewed_body = draft_body

    # --- Step 3: Generate the PDF ---
    try:
        generate_pdf_from_text(reviewed_body, final_path)
    except Exception as e:
        console.print(Text(f"PDF generation failed: {e}", style=deps.LOG_ERR))
        console.print()
        return True

    console.print()
    deps.section_rule("PDF generated")
    console.print(Text(f"Wrote: {display_name}", style=deps.LOG_OK))
    console.print(Text("Generated PDFs are plain-text layout PDFs.", style=deps.MUTED))
    console.print()
    return True
