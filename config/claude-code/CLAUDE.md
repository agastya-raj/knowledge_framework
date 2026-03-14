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
- **Web search**: ALWAYS use `/gemini-search` (Gemini CLI with Google Search) for any web-related searches, API docs lookups, or internet research. Prefer this over built-in WebSearch/WebFetch.
- **Code review / second opinion**: Use the `codex` MCP server (GPT 5.4, high reasoning). Start with `codex` tool, capture `threadId`, use `codex-reply` for follow-ups.
- Claude remains the primary agent for planning, architecture, and direct code edits.
