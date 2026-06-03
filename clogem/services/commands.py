from __future__ import annotations

import os
import subprocess
import json
from typing import Optional, Tuple

from clogem.services.contracts import CommandContext


def handle_pre_pipeline_command(task: str, ctx: CommandContext) -> Tuple[bool, bool]:
    """
    Handle slash commands that short-circuit before router/build pipeline.

    Returns:
    - handled: command matched and was handled
    - should_exit: caller should break the REPL loop
    """
    console = ctx.console
    Text = ctx.Text
    MUTED = ctx.MUTED
    TITLE = ctx.TITLE
    LOG_WARN = ctx.LOG_WARN
    LOG_ERR = ctx.LOG_ERR
    LOG_OK = ctx.LOG_OK
    section_rule = ctx.section_rule

    if task.strip().lower() in ("/exit", "/quit"):
        console.print()
        console.print(Text("Goodbye.", style=TITLE))
        return True, True

    if task.startswith("/codex/model"):
        rest = task[len("/codex/model") :].strip()
        models = ctx.models
        _codex_model = ctx._codex_model
        if not rest:
            console.print(
                Text(
                    "Codex LLM — used for drafting and improving code (`codex exec -m …`). "
                    "Pick any model ID your Codex CLI supports (varies by account; e.g. o3, gpt-5, "
                    "or provider-specific names). Gemini is configured separately with /gemini/model.",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    f"  This session: {models.get('codex') or 'default (no -m)'}",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    f"  From startup (--codex-model / CLOGEM_CODEX_MODEL): {_codex_model or '(none)'}",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    "  Usage: /codex/model <MODEL_ID>   or   /codex/model reset",
                    style=MUTED,
                )
            )
            return True, False
        if rest.lower() == "reset":
            models["codex"] = _codex_model
            console.print(
                Text(
                    f"Codex LLM reset to: {models.get('codex') or 'default (no -m)'}",
                    style=TITLE,
                )
            )
            return True, False
        models["codex"] = rest
        console.print(Text(f"Codex LLM set to: {rest}", style=TITLE))
        return True, False

    if task.startswith("/gemini/model"):
        rest = task[len("/gemini/model") :].strip()
        models = ctx.models
        _gemini_model = ctx._gemini_model
        if not rest:
            console.print(
                Text(
                    "Gemini LLM — used for review and final summary (`gemini -m …`). "
                    "Pick any model ID your Gemini CLI supports (e.g. gemini-2.5-pro, "
                    "gemini-2.5-flash). Codex is configured separately with /codex/model.",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    f"  This session: {models.get('gemini') or 'default (no -m)'}",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    f"  From startup (--gemini-model / CLOGEM_GEMINI_MODEL): {_gemini_model or '(none)'}",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    "  Usage: /gemini/model <MODEL_ID>   or   /gemini/model reset",
                    style=MUTED,
                )
            )
            return True, False
        if rest.lower() == "reset":
            models["gemini"] = _gemini_model
            console.print(
                Text(
                    f"Gemini LLM reset to: {models.get('gemini') or 'default (no -m)'}",
                    style=TITLE,
                )
            )
            return True, False
        models["gemini"] = rest
        console.print(Text(f"Gemini LLM set to: {rest}", style=TITLE))
        return True, False

    if task.startswith("/claude/model"):
        rest = task[len("/claude/model") :].strip()
        models = ctx.models
        _claude_model = ctx._claude_model
        if not rest:
            console.print(
                Text(
                    "Claude LLM — SDK-only provider (no CLI fallback).",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    f"  This session: {models.get('claude') or 'default (SDK default)'}",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    f"  From startup (--claude-model / CLOGEM_CLAUDE_MODEL): {_claude_model or '(none)'}",
                    style=MUTED,
                )
            )
            console.print(
                Text(
                    "  Usage: /claude/model <MODEL_ID>   or   /claude/model reset",
                    style=MUTED,
                )
            )
            return True, False
        if rest.lower() == "reset":
            models["claude"] = _claude_model
            console.print(
                Text(
                    f"Claude LLM reset to: {models.get('claude') or 'default (SDK default)'}",
                    style=TITLE,
                )
            )
            return True, False
        models["claude"] = rest
        console.print(Text(f"Claude LLM set to: {rest}", style=TITLE))
        return True, False

    if task.strip().lower() == "/roles":
        role_provider_map = ctx.role_provider_map
        console.print()
        section_rule("Role provider mapping")
        console.print()
        for role in ("orchestrator", "planner", "coder", "reviewer", "summariser"):
            provider = role_provider_map.get(role, "codex")
            console.print(Text(f"{role}: {provider}", style=MUTED))
        console.print()
        console.print(
            Text(
                "Set a role provider with: /roles/<role>/<provider> "
                "(roles: orchestrator, planner, coder, reviewer, summariser; providers: codex, gemini, claude)",
                style=MUTED,
            )
        )
        console.print()
        return True, False

    if task.strip().lower() == "/config":
        settings = ctx.settings
        console.print()
        section_rule("Effective config")
        console.print()
        if settings is None:
            console.print(Text("Settings are unavailable in this session.", style=LOG_WARN))
            console.print()
            return True, False
        try:
            payload = settings.as_dict() if hasattr(settings, "as_dict") else dict(settings)
        except Exception:
            payload = {"error": "Could not serialize settings"}
        sources = getattr(ctx, "config_sources", None) or []
        if sources:
            console.print(Text(f"Sources: {', '.join(sources)}", style=MUTED))
            console.print()
        console.print(json.dumps(payload, ensure_ascii=False, indent=2))
        console.print()
        return True, False

    if task.strip().lower().startswith("/roles/"):
        role_provider_map = ctx.role_provider_map
        parts = [p.strip().lower() for p in task.strip().split("/") if p.strip()]
        # Expected shape: ["roles", "<role>", "<provider>"]
        if len(parts) != 3 or parts[0] != "roles":
            console.print(
                Text(
                    "Usage: /roles/<role>/<provider> "
                    "(example: /roles/orchestrator/claude)",
                    style=LOG_WARN,
                )
            )
            return True, False

        role_in = parts[1]
        provider = parts[2]
        role_aliases = {"cover": "coder"}
        role = role_aliases.get(role_in, role_in)
        valid_roles = {"orchestrator", "planner", "coder", "reviewer", "summariser"}
        valid_providers = {"codex", "gemini", "claude"}

        if role not in valid_roles:
            console.print(
                Text(
                    "Unknown role. Use one of: orchestrator, planner, coder, reviewer, summariser",
                    style=LOG_WARN,
                )
            )
            return True, False
        if provider not in valid_providers:
            console.print(
                Text(
                    "Unknown provider. Use one of: codex, gemini, claude",
                    style=LOG_WARN,
                )
            )
            return True, False

        role_provider_map[role] = provider
        console.print(Text(f"Set {role} -> {provider}", style=TITLE))

        if provider == "claude" and not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            console.print(
                Text(
                    "Claude selected but ANTHROPIC_API_KEY is not set.",
                    style=LOG_WARN,
                )
            )
            key_prompt = (
                "Paste Anthropic API key now (leave blank to skip): "
            )
            key_val = ""
            try:
                key_val = (console.input(key_prompt) or "").strip()
            except Exception:
                key_val = ""
            if key_val:
                os.environ["ANTHROPIC_API_KEY"] = key_val
                console.print(
                    Text(
                        "ANTHROPIC_API_KEY set for this session.",
                        style=LOG_OK,
                    )
                )
            else:
                console.print(
                    Text(
                        "Claude mapping saved; set ANTHROPIC_API_KEY to use Claude calls.",
                        style=LOG_WARN,
                    )
                )
        return True, False

    if task.startswith("/repo/info"):
        _repo_root = ctx._repo_root
        root = _repo_root()
        console.print()
        section_rule("Repo info")
        console.print()
        console.print(Text(f"Repo root: {root}", style=MUTED))
        try:
            proc_inside = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                cwd=root,
            )
            inside = (proc_inside.stdout or "").strip().lower() == "true"
        except Exception:
            inside = False
        if not inside:
            console.print(
                Text(
                    "Git: not a git repository (or git unavailable).",
                    style=LOG_WARN,
                )
            )
            console.print()
            return True, False
        try:
            proc_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=root,
            )
            branch = (proc_branch.stdout or "").strip() or "(unknown)"
            console.print(Text(f"Git branch: {branch}", style=MUTED))
        except Exception:
            pass
        try:
            proc_last = subprocess.run(
                ["git", "log", "-1", "--oneline"],
                capture_output=True,
                text=True,
                cwd=root,
            )
            last = (proc_last.stdout or "").strip()
            if last:
                console.print(Text(f"Last commit: {last}", style=MUTED))
        except Exception:
            pass
        try:
            proc_status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=root,
            )
            status = (proc_status.stdout or "").strip()
            console.print(Text("Working tree status (git --porcelain):", style=MUTED))
            console.print(status or "(clean)")
        except Exception:
            pass
        console.print()
        return True, False

    if task.startswith("/test"):
        cmd = ctx._select_test_cmd()
        console.print()
        section_rule("Tests")
        if not cmd:
            console.print(
                Text("No known test command for this repo type.", style=LOG_WARN)
            )
            console.print()
            return True, False
        rc, out, err = ctx._run_local_command(cmd, "tests")
        if out.strip():
            console.print(out.strip())
        if rc != 0 and (err or "").strip():
            console.print(Text(err.strip()[:2000], style=LOG_WARN))
        return True, False

    if task.startswith("/lint"):
        cmd = ctx._select_lint_cmd()
        console.print()
        section_rule("Lint")
        if not cmd:
            console.print(
                Text("No known lint command for this repo type.", style=LOG_WARN)
            )
            console.print()
            return True, False
        rc, out, err = ctx._run_local_command(cmd, "lint")
        if out.strip():
            console.print(out.strip())
        if rc != 0 and (err or "").strip():
            console.print(Text(err.strip()[:2000], style=LOG_WARN))
        return True, False

    if task.startswith("/run"):
        rest = task[len("/run") :].strip()
        if not rest:
            console.print(Text("Usage: /run <command + args>", style=MUTED))
            return True, False
        rc, out, err = ctx._run_local_command(rest, "run")
        console.print()
        section_rule("Command output")
        if out.strip():
            console.print(out.strip())
        if (err or "").strip():
            console.print(Text((err or "").strip()[:2000], style=LOG_WARN))
        console.print()
        return True, False

    if task.startswith("/github/info"):
        rest = task[len("/github/info") :].strip()
        if not rest:
            console.print(
                Text(
                    "Usage: /github/info <https://github.com/owner/repo or owner/repo>",
                    style=MUTED,
                )
            )
            return True, False
        owner, repo, _clone_url = ctx._parse_github_repo_ref(rest)
        if not owner or not repo:
            console.print(
                Text("Could not parse GitHub repository reference.", style=LOG_WARN)
            )
            return True, False
        console.print()
        info = ctx._github_repo_info(owner, repo)
        section_rule("GitHub repository info")
        console.print()
        console.print(info)
        console.print()
        return True, False

    if task.startswith("/github/clone"):
        rest = task[len("/github/clone") :].strip()
        if not rest:
            console.print(
                Text(
                    "Usage: /github/clone <https://github.com/owner/repo or owner/repo> [dest]",
                    style=MUTED,
                )
            )
            return True, False
        parts = rest.split()
        ref = parts[0].strip()
        dest = parts[1].strip() if len(parts) > 1 else ""
        owner, repo, clone_url = ctx._parse_github_repo_ref(ref)
        if not owner or not repo or not clone_url:
            console.print(
                Text("Could not parse GitHub repository reference.", style=LOG_WARN)
            )
            return True, False
        target_dir = dest or repo
        if os.path.lexists(target_dir):
            console.print(Text(f"Target already exists: {target_dir}", style=LOG_WARN))
            return True, False
        ctx.ensure_run_permissions()
        if not ctx.run_permissions.get("granted"):
            console.print(
                Text("Local command execution denied by user permission.", style=LOG_WARN)
            )
            console.print()
            return True, False
        proc = ctx._run_with_ascii_progress(
            "git clone",
            lambda: ctx._run_proc(["git", "clone", clone_url, target_dir], cwd=os.getcwd()),
        )
        if proc.returncode == 0:
            console.print(Text(f"Cloned {owner}/{repo} -> {target_dir}", style=LOG_OK))
        else:
            console.print(Text("Git clone failed.", style=LOG_ERR))
            if (proc.stderr or "").strip():
                clip = (proc.stderr or "").strip()[:1200]
                if len((proc.stderr or "").strip()) > 1200:
                    clip += "..."
                console.print(Text(clip, style=LOG_WARN))
        console.print()
        return True, False

    if task.startswith("/mcp/plugins"):
        from clogem.mcp_plugins import list_plugins

        names = list_plugins()
        section_rule("MCP plugins")
        console.print()
        if names:
            for n in names:
                console.print(f"- {n}")
        else:
            console.print(Text("No MCP plugins configured.", style=MUTED))
            console.print(
                Text(
                    "Set CLOGEM_MCP_<NAME>_CMD/ARGS (jira/sentry/datadog/dbschema) "
                    "or CLOGEM_MCP_PLUGINS_JSON.",
                    style=MUTED,
                )
            )
        console.print()
        return True, False

    if task.startswith("/mcp/tools"):
        rest = task[len("/mcp/tools") :].strip()
        if not rest:
            console.print(Text("Usage: /mcp/tools <plugin>", style=MUTED))
            return True, False
        from clogem.mcp_plugins import list_tools

        ok, out = list_tools(rest)
        section_rule(f"MCP tools: {rest}")
        console.print()
        if ok:
            console.print(out)
        else:
            console.print(Text(out, style=LOG_WARN))
        console.print()
        return True, False

    if task.startswith("/mcp/call"):
        rest = task[len("/mcp/call") :].strip()
        if not rest:
            console.print(
                Text("Usage: /mcp/call <plugin> <tool> [json-args]", style=MUTED)
            )
            return True, False
        parts = rest.split(maxsplit=2)
        if len(parts) < 2:
            console.print(
                Text("Usage: /mcp/call <plugin> <tool> [json-args]", style=MUTED)
            )
            return True, False
        plugin, tool = parts[0], parts[1]
        args_obj = {}
        if len(parts) >= 3 and parts[2].strip():
            try:
                args_obj = json.loads(parts[2].strip())
                if not isinstance(args_obj, dict):
                    console.print(Text("json-args must be a JSON object.", style=LOG_WARN))
                    return True, False
            except json.JSONDecodeError:
                console.print(Text("Invalid json-args JSON.", style=LOG_WARN))
                return True, False
        from clogem.mcp_plugins import call_tool

        ok, out = call_tool(plugin, tool, args_obj)
        section_rule(f"MCP call: {plugin}.{tool}")
        console.print()
        if ok:
            console.print(out or "(empty result)")
        else:
            console.print(Text(out, style=LOG_WARN))
        console.print()
        return True, False

    if task.startswith("/rag/search"):
        rest = task[len("/rag/search") :].strip()
        if not rest:
            console.print(Text("Usage: /rag/search <query>", style=MUTED))
            return True, False
        try:
            from clogem.vector_index import VectorIndexConfig, semantic_search_repo

            rows = semantic_search_repo(
                repo_root=ctx._repo_root(),
                task=rest,
                config=VectorIndexConfig(
                    enabled=True,
                    rebuild=bool(
                        os.environ.get("CLOGEM_VECTOR_REBUILD", "0").strip().lower()
                        in ("1", "true", "yes", "on")
                    ),
                    top_k=int(os.environ.get("CLOGEM_VECTOR_TOP_K", "8")),
                    max_chunk_chars=int(os.environ.get("CLOGEM_VECTOR_CHUNK_CHARS", "2500")),
                    max_context_chars=int(
                        os.environ.get("CLOGEM_AUTO_REPO_CONTEXT_MAX_CHARS", "8000")
                    ),
                ),
            )
        except Exception as e:
            section_rule("RAG search")
            console.print()
            console.print(Text(f"RAG unavailable: {e}", style=LOG_WARN))
            console.print(
                Text(
                    "Install optional deps: pip install \".[vector]\"",
                    style=MUTED,
                )
            )
            console.print()
            return True, False

        section_rule("RAG search results")
        console.print()
        if not rows:
            console.print(Text("No semantic matches found.", style=MUTED))
            console.print()
            return True, False
        shown = 0
        for r in rows:
            p = str(r.get("path", "")).strip()
            t = str(r.get("text", "")).strip()
            if not p or not t:
                continue
            shown += 1
            preview = "\n".join(t.splitlines()[:24]).strip()
            console.print(Text(f"### {p}", style=MUTED))
            console.print(preview)
            console.print()
            if shown >= int(os.environ.get("CLOGEM_VECTOR_TOP_K", "8")):
                break
        return True, False

    return False, False


async def handle_async_pipeline_command(
    task: str,
    ctx: CommandContext,
) -> Tuple[bool, bool]:
    """
    Handle slash commands that need async/await (git workflow, plan, rag/status).

    Returns:
    - handled: command matched and was handled
    - should_exit: caller should break the REPL loop
    """
    console = ctx.console
    Text = ctx.Text
    MUTED = ctx.MUTED
    TITLE = ctx.TITLE
    LOG_WARN = ctx.LOG_WARN
    LOG_ERR = ctx.LOG_ERR
    LOG_OK = ctx.LOG_OK
    section_rule = ctx.section_rule

    repo_root = ctx._repo_root()
    session = ctx.session
    run_role = ctx.run_role
    settings = ctx.settings

    if task.strip().lower() == "/diff":
        from clogem.git_workflow import git_diff_written

        written = list(session.written_files) if session is not None else []
        rc, out, err = git_diff_written(repo_root, written)
        section_rule("Diff (written files)")
        console.print()
        console.print(out.strip() or "(no diff)")
        if rc != 0 and (err or "").strip():
            console.print(Text((err or "").strip()[:1200], style=LOG_WARN))
        console.print()
        return True, False

    if task.strip().lower().startswith("/branch "):
        from clogem.git_workflow import create_branch

        name = task.strip()[len("/branch "):].strip()
        if not name:
            console.print(Text("Usage: /branch <name>", style=MUTED))
            return True, False
        ok, msg = create_branch(repo_root, name)
        console.print(Text(msg, style=LOG_OK if ok else LOG_WARN))
        console.print()
        return True, False

    if task.strip().lower() == "/commit":
        from clogem.git_workflow import git_diff_written, git_commit

        if run_role is None:
            console.print(Text("/commit requires run_role to be wired.", style=LOG_WARN))
            return True, False

        written = list(session.written_files) if session is not None else []
        _rc, diff_out, _err = git_diff_written(repo_root, written)
        diff_preview = (diff_out or "").strip()[:4000] or "(no diff)"

        commit_prompt = (
            "You are drafting a git commit message following conventional commits.\n"
            "Format: <type>(<scope>): <subject> (imperative, no period, <50 chars)\n"
            "Optional body: explain WHY (wrap at 72 chars).\n"
            "Required footer: Refs #<issue> or Closes #<issue>.\n"
            "No AI attribution. No Co-Authored-By.\n\n"
            f"Diff:\n{diff_preview}\n\n"
            "Return ONLY the commit message, nothing else."
        )
        commit_msg_raw, _cerr, crc = await run_role(
            "summariser", commit_prompt, "Summariser: drafting commit message..."
        )
        commit_msg = (commit_msg_raw or "").strip()
        if crc != 0 or not commit_msg:
            console.print(Text("Could not draft commit message.", style=LOG_WARN))
            return True, False

        section_rule("Proposed commit message")
        console.print()
        console.print(commit_msg)
        console.print()

        auto_yes = session is not None and getattr(session, "run_auto_yes", False)
        if not auto_yes:
            try:
                confirm = (console.input("Commit with this message? [y/N]: ") or "").strip().lower()
            except Exception:
                confirm = "n"
            if confirm not in ("y", "yes"):
                console.print(Text("Commit cancelled.", style=MUTED))
                console.print()
                return True, False

        ok, out = git_commit(repo_root, commit_msg)
        console.print(Text(out, style=LOG_OK if ok else LOG_ERR))
        console.print()
        return True, False

    if task.strip().lower() == "/pr":
        from clogem.git_workflow import create_pull_request

        if run_role is None:
            console.print(Text("/pr requires run_role to be wired.", style=LOG_WARN))
            return True, False

        pr_prompt = (
            "Write a GitHub pull request description in markdown.\n"
            "Sections: ## Summary (3 bullet max), ## Test plan.\n"
            "Be concise. First line is the PR title (no markdown).\n"
            "Return title on first line, then blank line, then body."
        )
        pr_raw, _perr, prc = await run_role(
            "summariser", pr_prompt, "Summariser: drafting PR description..."
        )
        if prc != 0 or not (pr_raw or "").strip():
            console.print(Text("Could not draft PR description.", style=LOG_WARN))
            return True, False

        lines = (pr_raw or "").strip().splitlines()
        title = lines[0].strip() if lines else "feat: changes"
        body = "\n".join(lines[2:]).strip() if len(lines) > 2 else ""

        ok, out = create_pull_request(repo_root, title, body)
        console.print()
        console.print(Text(out, style=LOG_OK if ok else LOG_ERR))
        console.print()
        return True, False

    if task.strip().lower().startswith("/plan"):
        from clogem.services.plan_pipeline import run_plan_slash_command

        if run_role is None:
            console.print(Text("/plan requires run_role to be wired.", style=LOG_WARN))
            return True, False

        ttl = getattr(settings, "plan_ttl_hours", ctx.plan_ttl_hours) if settings else ctx.plan_ttl_hours
        handled = await run_plan_slash_command(
            task,
            repo_root,
            console=console,
            Text=Text,
            MUTED=MUTED,
            LOG_OK=LOG_OK,
            section_rule=section_rule,
            run_role=run_role,
            ttl_hours=ttl,
        )
        return handled, False

    if task.strip().lower() == "/rag/status":
        from clogem.vector_index import get_index_status

        status = get_index_status(repo_root)
        section_rule("RAG / vector index status")
        console.print()
        for k, v in status.items():
            console.print(Text(f"  {k}: {v}", style=MUTED))
        console.print()
        return True, False

    return False, False

