from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class StageRecord:
    name: str
    started_at: float
    duration_ms: int
    provider: str = ""
    returncode: int = 0
    error: str = ""


@dataclass
class TurnTrace:
    turn_id: str
    success: bool = True
    stages: List[StageRecord] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def add_stage(
        self,
        name: str,
        *,
        started_at: float,
        duration_ms: int,
        provider: str = "",
        returncode: int = 0,
        error: str = "",
    ) -> None:
        self.stages.append(
            StageRecord(
                name=name,
                started_at=started_at,
                duration_ms=duration_ms,
                provider=provider,
                returncode=returncode,
                error=(error or "")[:2000],
            )
        )
        if returncode != 0:
            self.success = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "success": self.success,
            "stages": [asdict(s) for s in self.stages],
            "extra": self.extra,
        }


_current: Optional[TurnTrace] = None


def begin_turn(extra: Optional[Dict[str, Any]] = None) -> TurnTrace:
    global _current
    _current = TurnTrace(turn_id=str(uuid.uuid4())[:12])
    if extra:
        _current.extra.update(extra)
    return _current


def current_turn() -> Optional[TurnTrace]:
    return _current


def end_turn(success: bool = True) -> Optional[TurnTrace]:
    global _current
    if _current is not None:
        _current.success = _current.success and success
    trace = _current
    _current = None
    return trace


@contextmanager
def stage(
    name: str,
    *,
    provider: str = "",
) -> Iterator[None]:
    """Record stage timing on the active turn trace."""
    t0 = time.monotonic()
    started = time.time()
    err = ""
    rc = 0
    try:
        yield
    except Exception as e:
        rc = 1
        err = str(e)
        if current_turn() is not None:
            current_turn().success = False  # type: ignore[union-attr]
        raise
    finally:
        dur = int((time.monotonic() - t0) * 1000)
        tr = current_turn()
        if tr is not None:
            tr.add_stage(
                name,
                started_at=started,
                duration_ms=dur,
                provider=provider,
                returncode=rc,
                error=err,
            )


def write_last_turn(trace: Optional[TurnTrace], log_dir: str) -> Optional[str]:
    """Atomically write last-turn.json; return path or None."""
    if trace is None:
        return None
    root = os.path.abspath(log_dir)
    os.makedirs(root, exist_ok=True)
    dest = os.path.join(root, "last-turn.json")
    payload = json.dumps(trace.to_dict(), indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".turn-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dest)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return None
    return dest
