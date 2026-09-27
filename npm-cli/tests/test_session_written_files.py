from __future__ import annotations

from clogem.runtime.session import SessionState


def test_record_written_dedupes() -> None:
    s = SessionState()
    s.record_written(["a.py", "b.py"])
    s.record_written(["b.py", "c.py"])
    assert s.written_files == ["a.py", "b.py", "c.py"]
