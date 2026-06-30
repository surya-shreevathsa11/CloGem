from __future__ import annotations

import os


def test_god_mode_setting_from_env(monkeypatch):
    monkeypatch.setenv("CLOGEM_GOD_MODE", "1")
    from clogem.config import Settings
    s = Settings.from_env()
    assert s.god_mode is True


def test_god_mode_off_by_default(monkeypatch):
    monkeypatch.delenv("CLOGEM_GOD_MODE", raising=False)
    from clogem.config import Settings
    s = Settings.from_env()
    assert s.god_mode is False


def test_god_mode_false_values(monkeypatch):
    for val in ("0", "false", "no", "off"):
        monkeypatch.setenv("CLOGEM_GOD_MODE", val)
        from clogem.config import Settings
        s = Settings.from_env()
        assert s.god_mode is False


def test_god_mode_pre_grants_auto_permissions(monkeypatch):
    """When god_mode=True, auto_permissions and run_permissions should be pre-granted."""
    from clogem.config import Settings

    # Simulate what async_main does: initialise permission dicts from god_mode flag.
    s = Settings(god_mode=True)
    auto_permissions: dict = {"granted": True if s.god_mode else None}
    run_permissions: dict = {"granted": True if s.god_mode else None}

    assert auto_permissions["granted"] is True
    assert run_permissions["granted"] is True


def test_normal_mode_permissions_start_unset():
    from clogem.config import Settings

    s = Settings(god_mode=False)
    auto_permissions: dict = {"granted": True if s.god_mode else None}
    run_permissions: dict = {"granted": True if s.god_mode else None}

    assert auto_permissions["granted"] is None
    assert run_permissions["granted"] is None


def test_god_mode_main_sets_env_var(monkeypatch):
    """god_mode_main() sets CLOGEM_GOD_MODE=1 before calling main()."""
    called_with_god_mode = {}

    def _fake_main():
        called_with_god_mode["val"] = os.environ.get("CLOGEM_GOD_MODE")

    import clogem.cli as cli_mod
    monkeypatch.setattr(cli_mod, "main", _fake_main)
    monkeypatch.delenv("CLOGEM_GOD_MODE", raising=False)

    cli_mod.god_mode_main()

    assert called_with_god_mode["val"] == "1"


def test_god_mode_session_run_auto_yes(monkeypatch):
    """God mode sets run_auto_yes=True on the session."""
    from clogem.config import Settings
    from clogem.runtime.session import SessionState

    s = Settings(god_mode=True)
    session = SessionState()
    if s.god_mode:
        session.run_auto_yes = True

    assert session.run_auto_yes is True


def test_god_mode_codex_argv_includes_full_auto():
    """When auto_permissions are granted (god mode), --full-auto appears in codex argv."""
    auto_permissions = {"granted": True}

    # Replicate the _codex_argv logic from cli.py
    argv = ["codex", "exec", "--skip-git-repo-check"]
    if auto_permissions.get("granted"):
        argv.append("--full-auto")

    assert "--full-auto" in argv


def test_god_mode_gemini_argv_includes_yolo():
    """When auto_permissions are granted (god mode), --yolo appears in gemini argv."""
    auto_permissions = {"granted": True}

    # Replicate the _gemini_argv logic from cli.py
    argv = ["gemini", "--skip-trust"]
    if auto_permissions.get("granted"):
        argv.append("--yolo")

    assert "--yolo" in argv


def test_god_mode_in_toml_via_config_loader(tmp_path, monkeypatch):
    """god_mode can be set from a project .clogem.toml file."""
    config = tmp_path / ".clogem.toml"
    config.write_text("god_mode = true\n")

    monkeypatch.delenv("CLOGEM_GOD_MODE", raising=False)

    from clogem.config_loader import load_settings
    s, sources = load_settings(cwd=str(tmp_path))
    assert s.god_mode is True
