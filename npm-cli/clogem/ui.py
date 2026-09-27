from __future__ import annotations

from clogem.logging_utils import get_logger

logger = get_logger(__name__)


def is_genai_cleanup_noise(message: str, exc: BaseException | None = None) -> bool:
    """google-genai schedules aclose() from __del__ even when the async client was never created."""
    blob = f"{message}\n{exc or ''}".lower()
    return "_async_httpx_client" in blob


def mentions_api_key(text: str) -> bool:
    low = (text or "").lower()
    return "api key" in low or "api_key" in low


def auth_rejected(text: str) -> bool:
    """True when the provider received a key and refused it."""
    low = (text or "").lower()
    return "unauthenticated" in low or "invalid authentication credentials" in low


def gemini_error_is_final(text: str) -> bool:
    """Missing or rejected keys will not succeed on another Gemini attempt."""
    return mentions_api_key(text) or auth_rejected(text)


def is_model_dump(text: str) -> bool:
    """True when text is a CLI diagnostic, not an answer."""
    low = (text or "").lower()
    if ("unknown variant" in low and "max" in low) or "failed to refresh available models" in low:
        return True
    stripped = (text or "").lstrip()
    return stripped.startswith("{") and '"models"' in low


def activity_note(stderr: str, code: int) -> str:
    """One short reason for a failed model step. Never a traceback or log dump."""
    text = stderr or ""
    low = text.lower()
    if ("unknown variant" in low and "max" in low) or "failed to refresh available models" in low:
        return "update the Codex CLI"
    if auth_rejected(text):
        return "API key was rejected"
    if "api key" in low or "api_key" in low:
        return "needs an API key"
    if "timed out" in low or code == 124:
        return "timed out"
    if "argument list too long" in low or "too long" in low:
        return "request was too large"
    if "full-auto" in low or "sandbox workspace-write" in low:
        return "permission flag rejected"
    if "grounding" in low:
        return "search unavailable"
    if "traceback (most recent call last)" in low:
        return "did not finish"
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("{") or line.startswith("["):
            continue
        if line.lower().startswith(("stderr:", "warning:", "error ", "[clogem]")):
            continue
        if len(line) > 64:
            line = line[:61] + "..."
        return line
    return "did not finish" if code else ""


# Dark warm ink. One dusty accent, the rest near-black grays.
INK = "\033[38;2;236;232;227m"
SILVER = "\033[38;2;176;170;162m"
DIM = "\033[38;2;120;114;108m"
FAINT = "\033[38;2;72;68;64m"
ACCENT = "\033[38;2;196;122;110m"
BAD = "\033[38;2;196;120;112m"
RESET = "\033[0m"

ACTIVITY_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
ACTIVITY_INK = INK
ACTIVITY_DIM = DIM
ACTIVITY_ACCENT = ACCENT
ACTIVITY_BAD = BAD
ACTIVITY_RESET = RESET

FRAME_INNER = 52


def frame_top() -> str:
    return f"  {FAINT}╭{'─' * FRAME_INNER}╮{RESET}"


def frame_bottom() -> str:
    return f"  {FAINT}╰{'─' * FRAME_INNER}╯{RESET}"


def frame_row(segments: list[tuple[str, str]], *, align: str = "center") -> str:
    """One line inside the session outline. Segments are (text, ansi color)."""
    visible = sum(len(text) for text, _color in segments)
    if visible > FRAME_INNER:
        # Keep the right edge aligned if a hint is longer than the card.
        room = FRAME_INNER
        trimmed: list[tuple[str, str]] = []
        for text, color in segments:
            if room <= 0:
                break
            if len(text) > room:
                text = text[: max(0, room - 1)] + "…"
            trimmed.append((text, color))
            room -= len(text)
        segments = trimmed
        visible = sum(len(text) for text, _color in segments)
    gap = FRAME_INNER - visible
    if align == "left":
        left, right = (1, gap - 1) if gap else (0, 0)
        if right < 0:
            left, right = 0, 0
    else:
        left, right = gap // 2, gap - (gap // 2)
    body = "".join(f"{color}{text}{RESET}" if color else text for text, color in segments)
    return f"  {FAINT}│{RESET}{' ' * left}{body}{' ' * right}{FAINT}│{RESET}"


def input_outline() -> tuple[object, object, object]:
    """Rounded prompt: top edge, a left rail, and a bottom edge."""
    from prompt_toolkit.formatted_text import HTML

    bar = "─" * FRAME_INNER
    message = HTML(
        f'<style fg="#484440">  ╭{bar}╮\n  │ </style>'
        '<style fg="#c47a6e">› </style>'
    )
    continuation = HTML('<style fg="#484440">  │ </style>   ')
    toolbar = HTML(f'<style fg="#484440">  ╰{bar}╯</style>')
    return message, continuation, toolbar

_ORBIT = (
    (0, 6),
    (0, 10),
    (1, 12),
    (2, 10),
    (2, 6),
    (2, 2),
    (1, 0),
    (0, 2),
)
_ORBIT_W = 13
_ORBIT_H = 3
_WORD = "clogem"


def _tty() -> bool:
    import sys

    return bool(sys.stdout.isatty())


def _out(text: str) -> None:
    import sys

    sys.stdout.write(text)
    sys.stdout.flush()


BOOT_MODELS = ("codex", "gemini", "claude", "grok")


def _orbit_lines(active: int | None) -> list[str]:
    """A small ring. One spark walks the dots; the center stays lit."""
    grid = [[" "] * _ORBIT_W for _ in range(_ORBIT_H)]
    for index, (row, col) in enumerate(_ORBIT):
        grid[row][col] = "●" if active is not None and index == active else "·"
    grid[1][6] = "✦"
    lines: list[str] = []
    for row in grid:
        pieces: list[str] = ["    "]
        for ch in row:
            if ch == " ":
                pieces.append(" ")
            elif ch == "✦":
                pieces.append(f"{ACCENT}{ch}{RESET}")
            elif ch == "●":
                pieces.append(f"{INK}{ch}{RESET}")
            else:
                pieces.append(f"{FAINT}{ch}{RESET}")
        lines.append("".join(pieces))
    return lines


def _shimmer(text: str, head: float) -> str:
    pieces = ["       "]
    for index, ch in enumerate(text):
        dist = abs(index - head)
        if dist < 0.8:
            color = INK
        elif dist < 1.8:
            color = SILVER
        else:
            color = DIM
        pieces.append(f"{color}{ch}{RESET}")
    return "".join(pieces)


def _rewind(rows: int) -> None:
    if rows:
        _out(f"\033[{rows}A")


def _paint_rows(lines: list[str], *, first: bool) -> None:
    if not first:
        _rewind(len(lines))
    for line in lines:
        _out("\033[2K" + line + "\n")


def _boot_models_line() -> None:
    _out(f"       {DIM}{' · '.join(BOOT_MODELS)}{RESET}\n\n")


def _boot_intro() -> None:
    """Orbit, then the name. The ring is not boxed, so the spark can travel cleanly."""
    import time

    _out("\n")
    if not _tty():
        _out(f"       {INK}{_WORD}{RESET}\n")
        _out(f"       {FAINT}──────{RESET}\n")
        _out(f"       {DIM}build · review · evolve{RESET}\n")
        _boot_models_line()
        return

    _out("\033[?25l")
    try:
        lines = _orbit_lines(0)
        _paint_rows(lines, first=True)
        for step in range(1, 16):
            time.sleep(0.055)
            _paint_rows(_orbit_lines(step % len(_ORBIT)), first=False)
        time.sleep(0.12)
        _rewind(len(lines))
        for _ in lines:
            _out("\033[2K\n")
        _rewind(len(lines))
        for step in range(12):
            head = step * (len(_WORD) + 1) / 11 - 1
            _out("\r\033[2K" + _shimmer(_WORD, head))
            time.sleep(0.04)
        _out("\n")
        _out("       ")
        for ch in "──────":
            _out(f"{FAINT}{ch}{RESET}")
            time.sleep(0.016)
        _out("\n")
        _out(f"       {DIM}build · review · evolve{RESET}\n")
        _boot_models_line()
    finally:
        _out("\033[?25h")


def _boot_run_step(label: str, check, min_spin: float = 0.32, *, required: bool = True) -> bool:
    """Braille spinner, then one quiet line. No spinner when stdout is not a TTY."""
    import sys
    import threading
    import time

    if not _tty():
        ok = True if check is None else bool(check())
        _out(_step_row(label, ok=ok, required=required) + "\n")
        return ok or not required

    stop = threading.Event()

    def _spin() -> None:
        i = 0
        while not stop.is_set():
            ch = ACTIVITY_FRAMES[i % len(ACTIVITY_FRAMES)]
            _out(f"\r\033[2K  {ACCENT}{ch}{RESET}  {SILVER}{label}{RESET}")
            time.sleep(0.08)
            i += 1

    worker = threading.Thread(target=_spin, daemon=True)
    worker.start()
    started = time.monotonic()
    ok = True
    if check is not None:
        ok = bool(check())
    while time.monotonic() - started < min_spin:
        time.sleep(0.04)
    stop.set()
    worker.join(timeout=2.0)
    sys.stdout.write("\r\033[2K" + _step_row(label, ok=ok, required=required) + "\n")
    sys.stdout.flush()
    return ok or not required


def _step_row(label: str, *, ok: bool = True, required: bool = True) -> str:
    if ok:
        color = INK
        tail = ""
    elif required:
        color = BAD
        tail = f"  {DIM}unavailable{RESET}"
    else:
        color = DIM
        tail = ""
    return f"  {color}·{RESET}  {color}{label}{RESET}{tail}"


def boot_sequence(required_providers: set[str] | None = None) -> bool:
    """TTY-style boot, real codex/gemini checks. Returns False if deps missing."""
    import os
    import shutil
    import shlex

    def _cmd_exists(raw: str, default_cmd: str) -> bool:
        txt = (raw or "").strip() or default_cmd
        try:
            parts = shlex.split(txt, posix=os.name != "nt")
        except Exception:
            logger.debug("Failed to parse command line for dependency check: %s", txt, exc_info=True)
            parts = txt.split()
        if not parts:
            parts = [default_cmd]
        exe = parts[0]
        return bool(shutil.which(exe) or os.path.isfile(exe))

    def _openai_sdk_ready() -> bool:
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            return False
        try:
            import openai  # noqa: F401

            return True
        except Exception:
            logger.debug("OpenAI SDK readiness check failed", exc_info=True)
            return False

    def _gemini_sdk_ready() -> bool:
        if not (
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        ):
            return False
        try:
            from google import genai  # noqa: F401

            return True
        except Exception:
            logger.debug("Gemini SDK readiness check failed", exc_info=True)
            return False

    def _claude_sdk_ready() -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            return False
        try:
            import anthropic  # noqa: F401

            return True
        except Exception:
            logger.debug("Anthropic SDK readiness check failed", exc_info=True)
            return False

    def _grok_sdk_ready() -> bool:
        if not os.environ.get("XAI_API_KEY", "").strip():
            return False
        try:
            import openai  # noqa: F401

            return True
        except Exception:
            logger.debug("Grok SDK readiness check failed", exc_info=True)
            return False

    def _miss(hint: str) -> None:
        _out(f"    {DIM}{hint}{RESET}\n\n")

    _boot_intro()

    if required_providers is not None and not required_providers:
        return True

    req = {"codex", "gemini"} if required_providers is None else set(required_providers)
    checks = {
        "codex": (
            lambda: _cmd_exists(os.environ.get("CLOGEM_CODEX_CMD", ""), "codex")
            or _openai_sdk_ready(),
            "Install the Codex CLI, or set OPENAI_API_KEY.",
        ),
        "gemini": (
            lambda: _cmd_exists(os.environ.get("CLOGEM_GEMINI_CMD", ""), "gemini")
            or _gemini_sdk_ready(),
            "Install the Gemini CLI, or set GEMINI_API_KEY.",
        ),
        "claude": (
            _claude_sdk_ready,
            "Set ANTHROPIC_API_KEY.",
        ),
        "grok": (
            lambda: _cmd_exists(os.environ.get("CLOGEM_GROK_CMD", ""), "grok")
            or _grok_sdk_ready(),
            "Install the Grok CLI, or set XAI_API_KEY.",
        ),
    }
    for name in BOOT_MODELS:
        check, hint = checks[name]
        if not _boot_run_step(name, check, required=name in req):
            _miss(hint)
            return False

    _out("\n")
    return True
