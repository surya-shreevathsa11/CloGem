from __future__ import annotations

from clogem.config import Settings
from clogem.runtime.build_workflow import build_extra_context_blocks


def test_build_extra_context_includes_plan(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    plan_dir = tmp_path / ".clogem"
    plan_dir.mkdir()
    (plan_dir / "plan.md").write_text("## Goal\nDo the thing\n", encoding="utf-8")
    s = Settings(plan_ttl_hours=48)
    block = build_extra_context_blocks(
        task_clean="implement feature",
        repo_root=str(tmp_path),
        settings=s,
    )
    assert "Approved plan" in block
    assert "Do the thing" in block
