from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from clogem.config import Settings


def llm_timeout_for_stage(settings: "Settings", stage: str) -> int:
    """Resolve LLM/subprocess timeout for a pipeline stage."""
    stage = (stage or "").strip().lower()
    if stage == "router":
        return max(1, settings.router_timeout_sec)
    if stage == "build":
        return max(1, settings.build_timeout_sec)
    if stage == "pdf":
        return max(1, settings.pdf_timeout_sec)
    if stage == "validation":
        return max(1, settings.validation_timeout_sec)
    return max(1, settings.subprocess_timeout_sec)
