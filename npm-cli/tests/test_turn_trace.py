from __future__ import annotations

from clogem.turn_trace import begin_turn, end_turn, stage, write_last_turn


def test_stage_records_duration(tmp_path) -> None:
    begin_turn()
    with stage("router", provider="codex"):
        pass
    tr = end_turn(success=True)
    assert tr is not None
    assert len(tr.stages) == 1
    assert tr.stages[0].name == "router"
    assert tr.stages[0].provider == "codex"
    assert tr.stages[0].duration_ms >= 0


def test_write_last_turn_atomic(tmp_path) -> None:
    tr = begin_turn()
    with stage("build"):
        pass
    end_turn()
    path = write_last_turn(tr, str(tmp_path / "logs"))
    assert path is not None
    assert (tmp_path / "logs" / "last-turn.json").is_file()
