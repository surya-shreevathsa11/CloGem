from __future__ import annotations

from pathlib import Path

from clogem.services.setup_wizard import (
    CmdResult,
    apply_saved_env,
    missing_companions,
    render_shell_block,
    run_key,
    run_setup,
    upsert_shell_block,
)


def test_missing_companions_reports_only_absent_tools():
    found = {"codex", "gemini"}
    missing = missing_companions(lambda name: "/bin/" + name if name in found else None)
    assert missing == ["claude", "grok"]


def test_shell_block_replaces_previous_settings_and_quotes_values():
    block = render_shell_block({"CLOGEM_GEMINI_BACKEND": "sdk", "GEMINI_API_KEY": "a b"})
    assert "export GEMINI_API_KEY='a b'" in block
    first = upsert_shell_block("export PATH=old\n", block)
    second = upsert_shell_block(first, render_shell_block({"CLOGEM_GEMINI_BACKEND": "cli"}))
    assert second.count("# >>> clogem setup >>>") == 1
    assert "export CLOGEM_GEMINI_BACKEND=cli" in second
    assert "sdk" not in second
    assert second.startswith("export PATH=old\n")


def test_yes_installs_missing_tools_and_writes_non_secret_env(tmp_path: Path):
    calls: list[tuple[str, ...]] = []

    def runner(cmd):
        calls.append(tuple(cmd))
        return CmdResult(0)

    home = tmp_path / "home"
    home.mkdir()
    code = run_setup(
        assume_yes=True,
        home=home,
        environ={"SHELL": "/bin/zsh"},
        which=lambda _name: None,
        runner=runner,
        is_tty=False,
    )
    assert code == 0
    assert calls[0][-1] == "@openai/codex"
    assert calls[1][-1] == "@google/gemini-cli"
    assert calls[2][-1] == "@anthropic-ai/claude-code"
    assert "x.ai/cli/install.sh" in calls[3][-1]
    rc = (home / ".zshrc").read_text(encoding="utf-8")
    assert "CLOGEM_GEMINI_BACKEND=sdk" in rc
    assert "CLOGEM_AUTO_PERMISSIONS=no" in rc
    assert "API_KEY" not in rc
    assert (home / ".local" / "share" / "clogem" / "setup-done").is_file()


def test_declined_install_does_not_run_npm(tmp_path: Path):
    calls: list[tuple[str, ...]] = []

    def runner(cmd):
        calls.append(tuple(cmd))
        return CmdResult(1, "EACCES")

    answers = iter(["n", "n", "n", "n", "", "", "", "", "n"])
    home = tmp_path / "home"
    home.mkdir()
    code = run_setup(
        assume_yes=False,
        home=home,
        environ={"SHELL": "/bin/bash"},
        which=lambda _name: None,
        runner=runner,
        input_fn=lambda _prompt: next(answers),
        is_tty=True,
    )
    assert code == 0
    assert calls == []
    assert not (home / ".bashrc").exists()


def test_failed_npm_install_prints_sudo_hint(tmp_path: Path):
    notes: list[str] = []

    def runner(cmd):
        return CmdResult(243, "EACCES")

    home = tmp_path / "home"
    home.mkdir()
    run_setup(
        assume_yes=True,
        home=home,
        environ={"SHELL": "/bin/zsh"},
        which=lambda name: "/bin/tool" if name != "codex" else None,
        runner=runner,
        say=notes.append,
        is_tty=False,
    )
    assert any("sudo npm install -g @openai/codex" in note for note in notes)
    assert not any("sudo npm install -g @google/gemini-cli" in note for note in notes)


def test_setup_keeps_a_saved_key_when_the_prompt_is_skipped(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    rc = home / ".zshrc"
    rc.write_text(
        "\n".join(
            [
                "# >>> clogem setup >>>",
                "export CLOGEM_GEMINI_BACKEND=sdk",
                "export GEMINI_API_KEY=already",
                "export ANTHROPIC_API_KEY=claude-key",
                "# <<< clogem setup <<<",
                "",
            ]
        ),
        encoding="utf-8",
    )
    answers = iter(["n", "", "new-claude", "", "", "n", "y"])
    code = run_setup(
        assume_yes=False,
        home=home,
        environ={"SHELL": "/bin/zsh"},
        which=lambda _name: "/bin/tool",
        runner=lambda _cmd: CmdResult(0),
        input_fn=lambda _prompt: next(answers),
        is_tty=True,
    )
    assert code == 0
    text = rc.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=already" in text
    assert "ANTHROPIC_API_KEY=new-claude" in text
    assert text.count("# >>> clogem setup >>>") == 1


def test_key_command_saves_one_key_and_leaves_the_others(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    rc = home / ".zshrc"
    rc.write_text("export PATH=old\n", encoding="utf-8")
    notes: list[str] = []
    code = run_key(
        "gemini",
        home=home,
        environ={"SHELL": "/bin/zsh"},
        input_fn=lambda _prompt: "gemini-secret",
        say=notes.append,
        is_tty=True,
    )
    assert code == 0
    text = rc.read_text(encoding="utf-8")
    assert "export PATH=old" in text
    assert "GEMINI_API_KEY=gemini-secret" in text
    assert "ANTHROPIC_API_KEY" not in text
    assert any("Saved gemini" in note for note in notes)

    code = run_key(
        "claude",
        home=home,
        environ={"SHELL": "/bin/zsh"},
        input_fn=lambda _prompt: "claude-secret",
        say=notes.append,
        is_tty=True,
    )
    text = rc.read_text(encoding="utf-8")
    assert code == 0
    assert "GEMINI_API_KEY=gemini-secret" in text
    assert "ANTHROPIC_API_KEY=claude-secret" in text


def test_apply_saved_env_loads_a_key_the_shell_has_not_exported(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".zshrc").write_text(
        "\n".join(
            [
                "# >>> clogem setup >>>",
                "export GEMINI_API_KEY=from-file",
                "export CLOGEM_GEMINI_BACKEND=sdk",
                "# <<< clogem setup <<<",
                "",
            ]
        ),
        encoding="utf-8",
    )
    env = {"SHELL": "/bin/zsh", "GEMINI_API_KEY": ""}
    apply_saved_env(home, env)
    assert env["GEMINI_API_KEY"] == "from-file"
    assert env["CLOGEM_GEMINI_BACKEND"] == "sdk"

    env["GEMINI_API_KEY"] = "already-in-process"
    apply_saved_env(home, env)
    assert env["GEMINI_API_KEY"] == "already-in-process"


def test_key_command_rejects_an_unknown_provider(tmp_path: Path):
    notes: list[str] = []
    code = run_key(
        "nope",
        home=tmp_path,
        environ={"SHELL": "/bin/zsh"},
        say=notes.append,
        is_tty=True,
    )
    assert code == 2
    assert any("gemini" in note and "openai" in note for note in notes)
