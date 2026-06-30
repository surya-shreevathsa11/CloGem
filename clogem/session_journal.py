from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


_DEFAULT_JOURNAL_PATH = ".clogem/session-history.jsonl"
_MAX_TASK_PREVIEW_LEN = 120
_MAX_TASKS_PER_SESSION = 50


@dataclass
class TurnRecord:
    task_preview: str
    files_written: List[str] = field(default_factory=list)
    success: bool = True


@dataclass
class SessionRecord:
    session_id: str
    started_at: float
    ended_at: float = 0.0
    turns: List[TurnRecord] = field(default_factory=list)
    memory_notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "turns": [asdict(t) for t in self.turns],
            "memory_notes": self.memory_notes,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "SessionRecord":
        turns = [
            TurnRecord(
                task_preview=str(t.get("task_preview", "")),
                files_written=list(t.get("files_written") or []),
                success=bool(t.get("success", True)),
            )
            for t in (d.get("turns") or [])
        ]
        return cls(
            session_id=str(d.get("session_id", "")),
            started_at=float(d.get("started_at", 0)),
            ended_at=float(d.get("ended_at", 0)),
            turns=turns,
            memory_notes=str(d.get("memory_notes", "")),
        )

    def task_summary(self, max_tasks: int = 3) -> str:
        """One-line preview of what was worked on."""
        previews = [t.task_preview for t in self.turns if t.task_preview.strip()]
        if not previews:
            return "(no tasks recorded)"
        shown = previews[:max_tasks]
        suffix = f" … +{len(previews) - max_tasks} more" if len(previews) > max_tasks else ""
        return "; ".join(shown) + suffix

    def all_files_written(self) -> List[str]:
        seen = set()
        out = []
        for t in self.turns:
            for f in t.files_written:
                if f and f not in seen:
                    seen.add(f)
                    out.append(f)
        return out

    def success_rate(self) -> str:
        if not self.turns:
            return "0 turns"
        ok = sum(1 for t in self.turns if t.success)
        n = len(self.turns)
        return f"{n} turn{'s' if n != 1 else ''}, {ok}/{n} ok"


class SessionJournal:
    """
    Append-only log of past clogem sessions.

    One JSON record per line in .clogem/session-history.jsonl.
    The current session is accumulated in memory and flushed on close().
    """

    def __init__(self, repo_root: str, journal_path: Optional[str] = None) -> None:
        self.repo_root = os.path.abspath(repo_root)
        self._path = os.path.join(
            self.repo_root,
            journal_path or _DEFAULT_JOURNAL_PATH,
        )
        self._current: Optional[SessionRecord] = None

    # ------------------------------------------------------------------
    # Write side
    # ------------------------------------------------------------------

    def begin_session(self) -> str:
        session_id = str(uuid.uuid4())[:16]
        self._current = SessionRecord(
            session_id=session_id,
            started_at=time.time(),
        )
        return session_id

    def record_turn(
        self,
        task_preview: str,
        *,
        files_written: Optional[List[str]] = None,
        success: bool = True,
    ) -> None:
        if self._current is None:
            return
        if len(self._current.turns) >= _MAX_TASKS_PER_SESSION:
            return
        preview = (task_preview or "").strip()[:_MAX_TASK_PREVIEW_LEN]
        if not preview:
            return
        self._current.turns.append(
            TurnRecord(
                task_preview=preview,
                files_written=list(files_written or []),
                success=success,
            )
        )

    def close(self, memory_notes: str = "") -> None:
        """Finalise the current session and append it to the journal."""
        if self._current is None:
            return
        if not self._current.turns:
            self._current = None
            return
        self._current.ended_at = time.time()
        self._current.memory_notes = (memory_notes or "").strip()[:2000]
        self._flush(self._current)
        self._current = None

    def _flush(self, record: SessionRecord) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        line = json.dumps(record.to_dict(), ensure_ascii=False)
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------

    def load_recent(self, n: int = 10) -> List[SessionRecord]:
        """Return the last *n* completed sessions, most recent first."""
        if not os.path.isfile(self._path):
            return []
        records: List[SessionRecord] = []
        try:
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        records.append(SessionRecord.from_dict(d))
                    except Exception:
                        continue
        except OSError:
            return []
        return list(reversed(records))[:n]

    # ------------------------------------------------------------------
    # Context formatting — injected into the LLM prompt on resume
    # ------------------------------------------------------------------

    @staticmethod
    def format_resume_context(record: SessionRecord) -> str:
        """
        Build a context block describing a past session, injected into
        the current session's memory/prompt so the LLM knows what was done.
        """
        import datetime

        when = ""
        if record.started_at:
            dt = datetime.datetime.fromtimestamp(record.started_at)
            when = dt.strftime("%Y-%m-%d %H:%M")

        lines = [
            f"## Resumed session — {when}",
            f"Session ID: {record.session_id}",
            f"Stats: {record.success_rate()}",
            "",
        ]

        previews = [t.task_preview for t in record.turns if t.task_preview.strip()]
        if previews:
            lines.append("### Tasks worked on")
            for p in previews:
                lines.append(f"  - {p}")
            lines.append("")

        files = record.all_files_written()
        if files:
            lines.append("### Files written")
            for f in files[:20]:
                lines.append(f"  - {f}")
            if len(files) > 20:
                lines.append(f"  … and {len(files) - 20} more")
            lines.append("")

        if record.memory_notes:
            lines.append("### Memory at session end")
            lines.append(record.memory_notes)
            lines.append("")

        lines.append(
            "Continue from where this session left off. "
            "The files listed above are already in the repo unless deleted."
        )

        return "\n".join(lines)
