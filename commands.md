# Clogem Commands Reference

All commands available in a `clogem` session, sorted alphabetically.

---

## CLI entry points

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `clogem` | Start the interactive REPL | `pip install -e .` |
| `clogem --god-mode` | Start with all permissions pre-granted (no approval prompts) | Pass the flag, or set `CLOGEM_GOD_MODE=1`, or `god_mode = true` in `.clogem.toml` |
| `clogem --no-stitch` | Disable the Google Stitch stage for UI-heavy tasks | Pass the flag, or set `CLOGEM_STITCH=0` |
| `clogem --role-provider ROLE=PROVIDER` | Map a role to a provider at startup (repeatable) | e.g. `--role-provider coder=claude reviewer=gemini` |
| `clogem --validation-docker` | Prefer Docker sandbox for test/lint/typecheck | Pass the flag, or set `CLOGEM_VALIDATION_DOCKER=1` |
| `clogem --verbose` | Enable INFO-level logging to stderr | Pass the flag, or set `CLOGEM_DEBUG=1` |
| `clogem-god-mode` | Alias entry point for `clogem --god-mode` | Install the package (`pip install -e .`) |
| `clogem run <task>` | Run a single non-interactive task and exit | Built-in subcommand |
| `clogem run --issue N <task>` | Link the run to GitHub issue N | Built-in subcommand flag |
| `clogem run --json-trace <task>` | Print the trace file path after the run | Built-in subcommand flag |
| `clogem run --task-file <path>` | Read task text from a file instead of inline | Built-in subcommand flag |
| `clogem run --yes <task>` | Skip all confirmation prompts in non-interactive mode | Built-in subcommand flag |

---

## Session directives (turn mode)

Prefix your message with one of these to override how that turn is routed. They do not change model settings for future turns.

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/agent <task>` | Autonomous multi-step coding within your stated scope | Always available |
| `/ask <question>` | Answer directly — skip the full build/review loop | Always available |
| `/build <task>` | Force the full build pipeline, skip BUILD/CHAT router | Always available |
| `/debug <task>` | Debugging and root-cause emphasis for this turn | Always available |
| `/plan <task>` | Planning and milestones emphasis; write or update `.clogem/plan.md` | Always available; `run_role` must be wired (it is in the REPL) |
| `/research <query>` | Research-style response; uses Gemini + Google Search when available | Always available |

---

## Model commands

Change which LLM is used for each provider mid-session. Changes apply from the next turn onward. Startup defaults come from `--codex-model` / `--gemini-model` / `--claude-model` flags or their `CLOGEM_*_MODEL` env vars.

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/claude/model` | Show current Claude model and startup default | Claude SDK must be configured (`ANTHROPIC_API_KEY`) |
| `/claude/model <MODEL_ID>` | Set Claude model for this session | Same as above |
| `/claude/model reset` | Restore Claude model to startup default | Same as above |
| `/codex/model` | Show current Codex model and startup default | Always available |
| `/codex/model <MODEL_ID>` | Set Codex model for this session | Always available |
| `/codex/model reset` | Restore Codex model to startup default | Always available |
| `/gemini/model` | Show current Gemini model and startup default | Always available |
| `/gemini/model <MODEL_ID>` | Set Gemini model for this session | Always available |
| `/gemini/model reset` | Restore Gemini model to startup default | Always available |

---

## Config and roles commands

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/config` | Show all effective runtime settings, their values, and which config sources (env, TOML file, CLI) set them | Always available |
| `/roles` | Show the current role-to-provider mapping for this session | Always available |
| `/roles/<role>/<provider>` | Remap a role to a different provider inline | Always available. Roles: `orchestrator` `planner` `coder` `reviewer` `summariser`. Providers: `codex` `gemini` `claude`. Example: `/roles/reviewer/claude` |

---

## Git workflow commands

Require `gh` on `PATH` for PR commands. Require `run_role` to be wired (true in the REPL, not in unit tests).

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/branch <name>` | Create and checkout a new feature branch (refuses if already on `main`/`master`) | Requires local git repo and run permissions |
| `/commit` | Draft a conventional commit message via the summariser role, confirm, then commit staged changes | Requires run permissions (`CLOGEM_ALLOW_LOCAL_COMMANDS=yes` or god mode) |
| `/diff` | Show a unified diff of all files written in the current session | Always available |
| `/pr` | Draft PR title and body via the summariser role, then run `gh pr create` | Requires `gh` on PATH and run permissions |

---

## Plan commands

Plans are written to `.clogem/plan.md` and included in build prompts until they expire (default 48 hours, configurable via `CLOGEM_PLAN_TTL_HOURS`).

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/plan <task>` | Generate or update `.clogem/plan.md` via the planner role | Always available |
| `/plan clear` | Delete `.clogem/plan.md` | Always available |
| `/plan show` | Display the current plan if it hasn't expired | Always available |

---

## Local execution commands

Require user approval or `CLOGEM_ALLOW_LOCAL_COMMANDS=yes` (or god mode). Commands are validated against an allowlist (`command_policy.py`) and shell operators (`&&`, `|`, `;`, etc.) are rejected.

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/lint` | Run the detected lint command for the repo (ruff, eslint, etc.) | `CLOGEM_ALLOW_LOCAL_COMMANDS=yes` or god mode |
| `/run <command>` | Run an arbitrary local shell command (allowlist and shell-operator restrictions apply) | `CLOGEM_ALLOW_LOCAL_COMMANDS=yes` or god mode |
| `/test` | Run the detected test command for the repo (pytest, npm test, etc.) | `CLOGEM_ALLOW_LOCAL_COMMANDS=yes` or god mode |

---

## Repo commands

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/repo/info` | Show git root, current branch, last commit hash and message, working tree status | Always available |

---

## GitHub commands

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/github/clone <url\|owner/repo> [dest]` | Clone a GitHub repo into the current directory | Requires `git` on PATH and run permissions |
| `/github/info <url\|owner/repo>` | Show public metadata for a GitHub repository (stars, description, language, topics) | Always available (uses GitHub API; no auth required for public repos) |

---

## MCP plugin commands

Require at least one MCP plugin to be configured via `CLOGEM_MCP_PLUGINS_JSON` (a JSON array of plugin definitions).

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/mcp/call <plugin> <tool> [json-args]` | Invoke a specific tool on a named MCP plugin | `CLOGEM_MCP_PLUGINS_JSON` must be set with plugin config |
| `/mcp/plugins` | List all configured MCP plugins and their status | `CLOGEM_MCP_PLUGINS_JSON` must be set |
| `/mcp/tools <plugin>` | List available tools on a named MCP plugin | `CLOGEM_MCP_PLUGINS_JSON` must be set |

---

## RAG / vector search commands

Require the `vector` optional dependency group (`pip install ".[vector]"`) and `CLOGEM_VECTOR_RAG=1`.

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/rag/search <query>` | Semantic search across the full local repo vector index | `pip install ".[vector]"` and `CLOGEM_VECTOR_RAG=1` |
| `/rag/status` | Show the vector index path, manifest stats, and dependency availability | Always available (shows unavailable if deps missing) |

---

## PDF commands

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/pdf <text> [output.pdf]` | Generate a PDF from inline text | `reportlab` installed (included in default deps) |
| `/pdf @path/to/file.txt [output.pdf]` | Generate a PDF from a file's contents | Same as above |

---

## Utility commands

| Command | What it does | How to enable |
|---------|-------------|---------------|
| `/exit` | Exit the clogem session | Always available |
| `/quit` | Exit the clogem session (alias for `/exit`) | Always available |

---

## Environment variable quick reference

| Variable | Default | What it controls |
|----------|---------|-----------------|
| `ANTHROPIC_API_KEY` | — | Required for Claude SDK calls |
| `CLOGEM_ALLOW_LOCAL_COMMANDS` | `""` (ask) | Pre-approve local command execution (`yes`/`no`) |
| `CLOGEM_AUTO_PERMISSIONS` | `""` (ask) | Pre-approve `--full-auto` (Codex) and `--yolo` (Gemini) (`yes`/`no`) |
| `CLOGEM_CLAUDE_MODEL` | — | Claude model ID at startup |
| `CLOGEM_CODEX_BACKEND` | `auto` | `auto` / `sdk` / `cli` — how Codex calls are made |
| `CLOGEM_CODEX_MODEL` | — | Codex model ID at startup |
| `CLOGEM_DEBUG` | `0` | Enable verbose INFO logging |
| `CLOGEM_GEMINI_BACKEND` | `auto` | `auto` / `sdk` / `cli` — how Gemini calls are made |
| `CLOGEM_GEMINI_MODEL` | — | Gemini model ID at startup |
| `CLOGEM_GOD_MODE` | `0` | Auto-grant all permissions, no prompts (`1` to enable) |
| `CLOGEM_MCP_PLUGINS_JSON` | `""` | JSON config for MCP plugins |
| `CLOGEM_PLAN_TTL_HOURS` | `48` | How long `.clogem/plan.md` stays active before expiring |
| `CLOGEM_ROLE_PROVIDER_MAP` | `""` | Startup role mapping, e.g. `coder=claude,reviewer=gemini` |
| `CLOGEM_STITCH` | `1` | Enable/disable Google Stitch stage (`0` to disable) |
| `CLOGEM_STREAM_OUTPUT` | `1` | Enable streaming token output to stdout (`0` to disable) |
| `CLOGEM_VALIDATION_DOCKER` | `0` | Use Docker sandbox for test/lint/typecheck |
| `CLOGEM_VECTOR_RAG` | `0` | Enable semantic vector search in build context |

---

## Project config file

Settings can also be placed in `.clogem.toml` (project) or `~/.config/clogem/config.toml` (user). Project file takes precedence over user file; both are overridden by environment variables.

```toml
# .clogem.toml
god_mode = false
stream_output = true
build_timeout_sec = 300
validation_docker = true
vector_rag = true
log_dir = ".clogem/logs"
profile_name = "thorough"   # "default" | "fast" | "thorough"
```
