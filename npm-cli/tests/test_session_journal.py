from __future__ import annotations

import json
import os
import time

import pytest

from clogem.session_journal import SessionJournal, SessionRecord, TurnRecord


# ---------------------------------------------------------------------------
# SessionRecord helpers
# ---------------------------------------------------------------------------

def _make_record(**kwargs) -> SessionRecord:
    defaults = dict(
        session_id="abc123",
        started_at=1_700_000_000.0,
        ended_at=1_700_000_060.0,
        turns=[],
        memory_notes="",
    )
    defaults.update(kwargs)
    return SessionRecord(**defaults)


def test_task_summary_empty():
    rec = _make_record()
    assert rec.task_summary() == "(no tasks recorded)"


def test_task_summary_shows_previews():
    rec = _make_record(
        turns=[
            TurnRecord(task_preview="build a REST API"),
            TurnRecord(task_preview="add tests"),
            TurnRecord(task_preview="write docs"),
            TurnRecord(task_preview="fix CI"),
        ]
    )
    summary = rec.task_summary(max_tasks=2)
    assert "build a REST API" in summary
    assert "add tests" in summary
    assert "+2 more" in summary


def test_all_files_written_deduplicates():
    rec = _make_record(
        turns=[
            TurnRecord(task_preview="t1", files_written=["a.py", "b.py"]),
            TurnRecord(task_preview="t2", files_written=["b.py", "c.py"]),
        ]
    )
    files = rec.all_files_written()
    assert files == ["a.py", "b.py", "c.py"]


def test_success_rate_all_ok():
    rec = _make_record(
        turns=[
            TurnRecord(task_preview="t1", success=True),
            TurnRecord(task_preview="t2", success=True),
        ]
    )
    assert "2/2 ok" in rec.success_rate()


def test_success_rate_partial():
    rec = _make_record(
        turns=[
            TurnRecord(task_preview="t1", success=True),
            TurnRecord(task_preview="t2", success=False),
        ]
    )
    assert "1/2 ok" in rec.success_rate()


def test_from_dict_roundtrip():
    original = _make_record(
        turns=[
            TurnRecord(task_preview="build thing", files_written=["x.py"], success=True),
        ],
        memory_notes="stack: Python",
    )
    restored = SessionRecord.from_dict(original.to_dict())
    assert restored.session_id == original.session_id
    assert len(restored.turns) == 1
    assert restored.turns[0].task_preview == "build thing"
    assert restored.turns[0].files_written == ["x.py"]
    assert restored.memory_notes == "stack: Python"


# ---------------------------------------------------------------------------
# SessionJournal write / read
# ---------------------------------------------------------------------------

def test_journal_write_and_read_recent(tmp_path):
    journal = SessionJournal(str(tmp_path))
    journal.begin_session()
    journal.record_turn("build an API", files_written=["api.py"], success=True)
    journal.record_turn("write tests", files_written=["test_api.py"], success=True)
    journal.close(memory_notes="stack: Python, FastAPI")

    recent = journal.load_recent(n=5)
    assert len(recent) == 1
    rec = recent[0]
    assert len(rec.turns) == 2
    assert rec.turns[0].task_preview == "build an API"
    assert rec.turns[0].files_written == ["api.py"]
    assert "Python" in rec.memory_notes


def test_journal_skips_empty_sessions(tmp_path):
    journal = SessionJournal(str(tmp_path))
    journal.begin_session()
    # No turns recorded
    journal.close()

    assert journal.load_recent() == []


def test_journal_multiple_sessions(tmp_path):
    journal = SessionJournal(str(tmp_path))

    for i in range(3):
        journal.begin_session()
        journal.record_turn(f"task {i}")
        journal.close()

    recent = journal.load_recent(n=5)
    assert len(recent) == 3
    # Most recent first
    assert recent[0].turns[0].task_preview == "task 2"
    assert recent[1].turns[0].task_preview == "task 1"
    assert recent[2].turns[0].task_preview == "task 0"


def test_journal_load_recent_caps_at_n(tmp_path):
    journal = SessionJournal(str(tmp_path))
    for i in range(10):
        journal.begin_session()
        journal.record_turn(f"task {i}")
        journal.close()

    recent = journal.load_recent(n=3)
    assert len(recent) == 3


def test_journal_no_file_returns_empty(tmp_path):
    journal = SessionJournal(str(tmp_path))
    assert journal.load_recent() == []


def test_journal_truncates_long_preview(tmp_path):
    journal = SessionJournal(str(tmp_path))
    journal.begin_session()
    long_task = "x" * 200
    journal.record_turn(long_task)
    journal.close()

    recent = journal.load_recent()
    assert len(recent[0].turns[0].task_preview) <= 120


def test_journal_caps_turns_per_session(tmp_path):
    journal = SessionJournal(str(tmp_path))
    journal.begin_session()
    for i in range(60):
        journal.record_turn(f"task {i}")
    journal.close()

    recent = journal.load_recent()
    assert len(recent[0].turns) == 50  # _MAX_TASKS_PER_SESSION


def test_journal_survives_corrupt_lines(tmp_path):
    path = tmp_path / ".clogem" / "session-history.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"session_id":"ok","started_at":1.0,"ended_at":2.0,"turns":[{"task_preview":"t","files_written":[],"success":true}],"memory_notes":""}\n'
        "NOT VALID JSON\n",
        encoding="utf-8",
    )
    journal = SessionJournal(str(tmp_path))
    recent = journal.load_recent()
    assert len(recent) == 1
    assert recent[0].session_id == "ok"


# ---------------------------------------------------------------------------
# format_resume_context
# ---------------------------------------------------------------------------

def test_format_resume_context_contains_key_sections():
    rec = SessionRecord(
        session_id="test-id",
        started_at=1_700_000_000.0,
        ended_at=1_700_000_060.0,
        turns=[
            TurnRecord(task_preview="build REST API", files_written=["api.py"], success=True),
            TurnRecord(task_preview="write tests", files_written=["test_api.py"], success=True),
        ],
        memory_notes="stack: Python, FastAPI",
    )
    ctx = SessionJournal.format_resume_context(rec)
    assert "Resumed session" in ctx
    assert "build REST API" in ctx
    assert "write tests" in ctx
    assert "api.py" in ctx
    assert "test_api.py" in ctx
    assert "Python, FastAPI" in ctx
    assert "Continue from where this session left off" in ctx


def test_format_resume_context_no_files():
    rec = SessionRecord(
        session_id="x",
        started_at=1_700_000_000.0,
        ended_at=1_700_000_060.0,
        turns=[TurnRecord(task_preview="just talked", files_written=[], success=True)],
        memory_notes="",
    )
    ctx = SessionJournal.format_resume_context(rec)
    assert "just talked" in ctx
    assert "Files written" not in ctx
