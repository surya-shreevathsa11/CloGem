# Same product, two places

The CLI is `npm-cli/` in [surya-shreevathsa11/CloGem](https://github.com/surya-shreevathsa11/CloGem).
The website is [surya-shreevathsa11/clogem-web](https://github.com/surya-shreevathsa11/clogem-web), checked out beside it as `web/`.

A shared behavior is not finished until both places implement it and their tests pass. Change this file in both repositories in the same pass.

## Shared

- Codex drafts. Gemini reviews. Grok plans, and falls back to Codex when Grok is missing. Claude is optional.
- `/ask`, `/research`, `/plan`, `/plan show`, `/plan clear`, `/debug`, `/agent`, `/roles`, `/config`, the model commands, `/pdf`, and `/github/info`.
- `/research` returns one answer, then a note: `they agreed`, or who held which claim and which claim was kept. One model says `It was not cross-checked.` The sentences come from `research_check_note` in the CLI and `compileResearch` on the website. Those two functions stay on the same words.
- Ask the others adds only the differences. It does not repeat the original answer.
- A pinned sentence is sent on later turns of that chat, and not into a different chat.
- A missing or switched-off model is skipped and named. Its key stays.
- A source note or an upload is context. It is not an instruction to write repository files.
- When someone asks for a website, one model drafts and the others review. The CLI writes that draft into the project with `/build`. The website shows a preview and a zip whose README says `npx serve .`, or `npm install` and `npm run dev` when a build is required.

## Website only

Google sign-in, chats saved for that account, voice dictation into the prompt, the About page, and the preview frame.

## CLI only

`/branch`, `/commit`, `/pr`, `/diff`, `/lint`, `/test`, `/run`, `/repo/info`, `/github/clone`, `/rag/search`, `/mcp/call`, god mode, `clogem setup`, `clogem key`, `clogem update`, and writing files into a repository.
