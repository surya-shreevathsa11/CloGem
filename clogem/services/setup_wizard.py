"""Install companion CLIs and write first-run shell settings."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

BEGIN = "# >>> clogem setup >>>"
END = "# <<< clogem setup <<<"

COMPANIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("codex", ("npm", "install", "-g", "@openai/codex")),
    ("gemini", ("npm", "install", "-g", "@google/gemini-cli")),
    ("claude", ("npm", "install", "-g", "@anthropic-ai/claude-code")),
    ("grok", ("bash", "-c", "curl -fsSL https://x.ai/cli/install.sh | bash")),
)

SUDO_HINTS = {
    "codex": "sudo npm install -g @openai/codex",
    "gemini": "sudo npm install -g @google/gemini-cli",
    "claude": "sudo npm install -g @anthropic-ai/claude-code",
}

DEFAULT_ENV = {
    "CLOGEM_GEMINI_BACKEND": "sdk",
    "CLOGEM_AUTO_PERMISSIONS": "no",
}

# Add a row here when a new provider needs a key. `clogem key <name>` picks it up.
API_KEYS: tuple[tuple[str, str, str], ...] = (
    ("gemini", "GEMINI_API_KEY", "Gemini"),
    ("claude", "ANTHROPIC_API_KEY", "Claude"),
    ("grok", "XAI_API_KEY", "Grok"),
    ("openai", "OPENAI_API_KEY", "OpenAI"),
)

Say = Callable[[str], None]
Runner = Callable[[Sequence[str]], "CmdResult"]
InputFn = Callable[[str], str]
Which = Callable[[str], Optional[str]]


@dataclass
class CmdResult:
    code: int
    stderr: str = ""


def missing_companions(which: Which) -> list[str]:
    return [name for name, _cmd in COMPANIONS if not which(name)]


def shell_rc_path(home: Path, environ: Mapping[str, str]) -> Path:
    shell = environ.get("SHELL", "")
    if shell.endswith("zsh"):
        return home / ".zshrc"
    if shell.endswith("bash"):
        return home / ".bashrc"
    if (home / ".zshrc").is_file():
        return home / ".zshrc"
    return home / ".bashrc"


def render_shell_block(values: Mapping[str, str]) -> str:
    lines = [BEGIN]
    for key, value in values.items():
        lines.append(f"export {key}={shlex.quote(value)}")
    lines.append(END)
    return "\n".join(lines) + "\n"


def parse_shell_block(existing: str) -> dict[str, str]:
    """Read export lines from the Clogem block. Values are unquoted."""
    if BEGIN not in existing or END not in existing:
        return {}
    body = existing.split(BEGIN, 1)[1].split(END, 1)[0]
    values: dict[str, str] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("export ") or "=" not in line:
            continue
        key, raw = line[len("export ") :].split("=", 1)
        parsed = shlex.split(raw) if raw else []
        values[key.strip()] = parsed[0] if parsed else ""
    return values


def saved_shell_values(rc_path: Path) -> dict[str, str]:
    if not rc_path.is_file():
        return {}
    return parse_shell_block(rc_path.read_text(encoding="utf-8"))


def apply_saved_env(home: Optional[Path] = None, environ: Optional[dict[str, str]] = None) -> None:
    """Load the Clogem shell block into this process when the shell has not."""
    import os

    target = environ if environ is not None else os.environ
    home = home or Path.home()
    for key, value in saved_shell_values(shell_rc_path(home, target)).items():
        if value and not str(target.get(key, "")).strip():
            target[key] = value


def key_prompt(label: str, env_name: str, saved: Mapping[str, str]) -> str:
    if saved.get(env_name):
        return f"{label} API key (Enter to keep the saved key): "
    extra = ""
    if env_name == "XAI_API_KEY":
        extra = "; leave empty if you use grok login"
    return f"{label} API key (Enter to skip{extra}): "


def upsert_shell_block(existing: str, block: str) -> str:
    if BEGIN in existing and END in existing:
        pre, rest = existing.split(BEGIN, 1)
        _old, post = rest.split(END, 1)
        if post.startswith("\n"):
            post = post[1:]
        return pre + block + post
    base = existing
    if base and not base.endswith("\n"):
        base += "\n"
    if base and not base.endswith("\n\n"):
        base += "\n"
    return base + block


def mark_complete(home: Path) -> None:
    folder = home / ".local" / "share" / "clogem"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "setup-done").write_text("ok\n", encoding="utf-8")


def _default_runner(cmd: Sequence[str]) -> CmdResult:
    proc = subprocess.run(list(cmd))
    return CmdResult(proc.returncode, "")


def _yes(prompt: str, *, assume_yes: bool, is_tty: bool, input_fn: InputFn) -> bool:
    if assume_yes:
        return True
    if not is_tty:
        return False
    answer = input_fn(f"{prompt} [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _secret(prompt: str, *, assume_yes: bool, is_tty: bool, input_fn: InputFn) -> str:
    if assume_yes or not is_tty:
        return ""
    return input_fn(prompt).strip()


def run_setup(
    *,
    assume_yes: bool = False,
    home: Optional[Path] = None,
    environ: Optional[Mapping[str, str]] = None,
    which: Optional[Which] = None,
    runner: Optional[Runner] = None,
    input_fn: Optional[InputFn] = None,
    say: Optional[Say] = None,
    is_tty: Optional[bool] = None,
) -> int:
    """Install missing CLIs and write shell settings. Returns a process exit code."""
    home = home or Path.home()
    env_map = dict(environ or {})
    which_fn = which or shutil.which
    run = runner or _default_runner
    ask = input_fn or input
    speak = say or print
    tty = sys_is_tty() if is_tty is None else is_tty
    rc_path = shell_rc_path(home, env_map)

    speak("Clogem setup")
    speak("This installs Codex, Gemini, Claude Code, and Grok when they are missing,")
    speak("then saves the settings Clogem needs on a personal machine.")

    for name, cmd in COMPANIONS:
        if which_fn(name):
            speak(f"{name}: already installed")
            continue
        if not _yes(f"Install {name}?", assume_yes=assume_yes, is_tty=tty, input_fn=ask):
            speak(f"Skipped {name}.")
            continue
        result = run(cmd)
        if result.code != 0:
            speak(f"{name} install exited {result.code}.")
            hint = SUDO_HINTS.get(name)
            if hint:
                speak(f"If npm reported a permission error, run: {hint}")
            elif name == "grok":
                speak("You can retry with: curl -fsSL https://x.ai/cli/install.sh | bash")

    if which_fn("codex") and _yes(
        "Start codex login now?",
        assume_yes=False,
        is_tty=tty and not assume_yes,
        input_fn=ask,
    ):
        run(("codex", "login"))
    elif not which_fn("codex"):
        speak("After Codex is installed, run: codex login")

    saved = saved_shell_values(rc_path)
    values = dict(DEFAULT_ENV)
    values.update(saved)
    speak("Gemini on a personal account uses that API key with CLOGEM_GEMINI_BACKEND=sdk.")
    speak("Claude inside Clogem needs ANTHROPIC_API_KEY. The claude command is a separate login.")
    speak("Press Enter to keep a key that is already saved.")
    for _name, env_name, label in API_KEYS:
        entered = _secret(
            key_prompt(label, env_name, saved),
            assume_yes=assume_yes,
            is_tty=tty,
            input_fn=ask,
        )
        if entered:
            values[env_name] = entered

    if which_fn("grok") and _yes(
        "Start grok sign-in now?",
        assume_yes=False,
        is_tty=tty and not assume_yes,
        input_fn=ask,
    ):
        run(("grok",))
    elif not which_fn("grok"):
        speak("After Grok is installed, run grok once and finish browser sign-in.")

    block = render_shell_block(values)
    if _yes(
        f"Write these settings to {rc_path}?",
        assume_yes=assume_yes,
        is_tty=tty,
        input_fn=ask,
    ):
        existing = rc_path.read_text(encoding="utf-8") if rc_path.is_file() else ""
        rc_path.parent.mkdir(parents=True, exist_ok=True)
        rc_path.write_text(upsert_shell_block(existing, block), encoding="utf-8")
        speak(f"Updated {rc_path}. Open a new terminal so the settings load.")
    else:
        speak("Settings were not written. Add them yourself if you want:")
        speak(block.rstrip())

    mark_complete(home)
    speak("Setup finished. Run clogem to start.")
    return 0


def run_key(
    name: Optional[str] = None,
    *,
    home: Optional[Path] = None,
    environ: Optional[Mapping[str, str]] = None,
    input_fn: Optional[InputFn] = None,
    say: Optional[Say] = None,
    is_tty: Optional[bool] = None,
) -> int:
    """Save one provider API key without reinstalling the other tools."""
    home = home or Path.home()
    env_map = dict(environ or {})
    ask = input_fn or input
    speak = say or print
    tty = sys_is_tty() if is_tty is None else is_tty
    rc_path = shell_rc_path(home, env_map)
    known = {item[0]: item for item in API_KEYS}
    saved = saved_shell_values(rc_path)

    chosen = (name or "").strip().lower()
    if not chosen:
        speak("API keys")
        for key_name, env_name, _label in API_KEYS:
            state = "saved" if saved.get(env_name) else "not set"
            speak(f"  {key_name}: {state}")
        if not tty:
            speak("Name one key, for example: clogem key gemini")
            return 2
        chosen = ask("Which key? ").strip().lower()

    row = known.get(chosen)
    if row is None:
        names = ", ".join(item[0] for item in API_KEYS)
        speak(f"Unknown key {chosen!r}. Use one of: {names}.")
        return 2

    _key_name, env_name, label = row
    entered = _secret(key_prompt(label, env_name, saved), assume_yes=False, is_tty=tty, input_fn=ask)
    if not entered:
        speak("Key unchanged.")
        return 0

    values = dict(DEFAULT_ENV)
    values.update(saved)
    values[env_name] = entered
    existing = rc_path.read_text(encoding="utf-8") if rc_path.is_file() else ""
    rc_path.parent.mkdir(parents=True, exist_ok=True)
    rc_path.write_text(upsert_shell_block(existing, render_shell_block(values)), encoding="utf-8")
    speak(f"Saved {chosen}. Open a new terminal so clogem can see it.")
    return 0


def sys_is_tty() -> bool:
    import sys

    return bool(sys.stdin.isatty())
