from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SessionState:
    """Mutable per-session state shared across REPL and run mode."""

    written_files: List[str] = field(default_factory=list)
    session_tokens: Dict[str, int] = field(
        default_factory=lambda: {"codex": 0, "gemini": 0, "claude": 0}
    )
    linked_issue: Optional[int] = None
    run_auto_yes: bool = False
    permissions_granted: Optional[bool] = None

    def record_written(self, paths: List[str]) -> None:
        for p in paths:
            norm = (p or "").strip()
            if norm and norm not in self.written_files:
                self.written_files.append(norm)

    def reset_turn_tokens(self) -> None:
        for k in self.session_tokens:
            self.session_tokens[k] = 0
