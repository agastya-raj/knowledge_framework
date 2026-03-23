# Memory

## Me
Agastya, PhD researcher at Trinity College Dublin (TCD), working on optical networking, digital twins, and ML for autonomous optical networks. Part of the Open Ireland testbed.

## Knowledge Base
Shared knowledge base at `~/ad_hoc/knowledge_framework` (GitHub: knowledge_framework).
- **Before non-trivial tasks:** scan `index.md` for relevant entries, read full entries if matched
- **After significant work:** drop a draft in `_drafts/YYYYMMDD_slug.md` using the draft template
- **On request:** curate drafts into polished entries per CLAUDE.md instructions in that repo

## Preferences
- snake_case file naming
- Use `uv` for all Python operations — run with `uv run`, install with `uv add` or `uv pip install`, never bare `pip install`
- Python version is pinned via `.python-version` in project roots

## Multi-Agent Tools
- **Web search (Brave)**: Use `/web-search` for general search, `/news-search` for news, `/images-search` for images, `/llm-context` for RAG-grounded content. These are Brave Search API skills — fast (~0.5s), structured results. Prefer over built-in WebSearch/WebFetch.
- **Browser (Browserbase)**: `/search` (Browserbase search), `/browser` (full browser automation), `/fetch` (page content without JS). These are separate Browserbase skills — use when you need to visit/interact with pages, not for simple search.
- **Code review**: Use `/dual-review` for parallel Claude + Codex review, or call `codex` directly.
- **Claude** remains the primary agent for planning, architecture, and direct code edits.

### Codex MCP Usage Defaults
Always capture `threadId` from the initial `codex` response and use `codex-reply` for follow-ups.

- **Reviews**: `sandbox: "read-only"`, `approval-policy: "never"`, always pass `cwd`
- **Second-opinion generation**: `sandbox: "workspace-write"`, `approval-policy: "on-request"`, always pass `cwd`, and **always use a worktree** (`isolation: "worktree"` on the Agent, or pass a worktree path as `cwd`) so Codex writes to an isolated copy — never the user's working tree
- **base-instructions**: "Be critical. Focus on correctness, security, and edge cases over style."
