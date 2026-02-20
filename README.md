# Knowledge Framework

A personal knowledge base designed for the age of AI agents. Instead of reusing stale code across projects, capture the **knowledge** — patterns, decisions, pitfalls, recipes — and let agents rebuild fresh code tailored to each new context.

## Why

Code rots. Dependencies break, APIs change, frameworks get deprecated. But the *knowledge* of how to solve a problem stays valid. With agents that can generate code from good specifications, a well-written knowledge entry is more valuable than a stale GitHub repo.

**The workflow:**
1. You work on projects with AI agents (Claude Code, Codex, OpenCode, Cursor, etc.)
2. When something significant is built, the agent captures a knowledge draft
3. Periodically, drafts get curated into polished, searchable entries
4. Next time any agent starts a similar task, it finds and applies that knowledge — generating fresh, compatible code instead of wrestling with old integrations

## Quick Start

### Option A: Point an agent at this repo

Tell any AI agent:

> Clone https://github.com/agastya-raj/knowledge_framework and follow SETUP.md to configure it for my system.

The agent will handle everything: cloning, setting up paths, integrating with your agent config files.

### Option B: Manual setup

1. Clone this repo to a stable location:
   ```bash
   git clone https://github.com/agastya-raj/knowledge_framework ~/knowledge_framework
   ```

2. Add a pointer to your agent's config (e.g., `~/.claude/CLAUDE.md` for Claude Code):
   ```markdown
   ## Knowledge Base
   Shared knowledge base at ~/knowledge_framework.
   - Before non-trivial tasks: scan index.md for relevant entries
   - After significant work: drop a draft in _inbox/
   - On request: curate drafts into entries per CLAUDE.md instructions in that repo
   ```

3. Start working. Agents will search before building and capture after completing.

## Structure

```
knowledge_framework/
├── entries/              # Curated knowledge entries
│   ├── patterns/         # Architecture patterns, how-to recipes
│   ├── decisions/        # Design decisions and tradeoffs
│   ├── domain/           # Domain expertise
│   ├── integrations/     # API/tool/library integration knowledge
│   ├── debugging/        # Solutions to hard bugs
│   ├── tools/            # Tool usage tips and configurations
│   └── research/         # Research methods and workflows
├── _inbox/               # Draft knowledge captures (curated later)
├── _review/              # Entries that failed quality checks
├── templates/
│   ├── standard.md       # Full entry template (7 sections)
│   ├── quick.md          # Lightweight template (4 sections)
│   └── draft.md          # Rough capture template for _inbox/
├── scripts/
│   ├── curate.py         # _inbox/ → entries/ pipeline
│   ├── validate.py       # Entry format validator
│   └── rebuild_index.py  # Regenerate index.md and tags.md
├── index.md              # Auto-generated searchable index
├── tags.md               # Auto-generated tag index
├── CLAUDE.md             # Agent instructions (search, capture, curate)
├── SETUP.md              # Setup guide for agents
└── README.md             # This file
```

## How It Works

### Searching (Pull)

Any agent reads `index.md` — a compact table of all entries with titles, types, tags, and summaries. It identifies relevant entries, reads the full markdown, and applies the knowledge to the current task. Fresh code, informed by past experience.

### Capturing (Push)

After completing significant work, agents write a rough draft to `_inbox/` using `templates/draft.md`. The draft captures: what was built, key learnings, pitfalls, and suggested tags. Takes ~2 minutes. The agent continues with its main task.

### Curating

Triggered by asking any agent to "curate my knowledge base", or by running:

```bash
python scripts/curate.py           # Process inbox, rebuild indexes
python scripts/curate.py --commit  # Also git commit and push
```

The curator validates entries, categorizes them, checks for duplicates, rebuilds the index, and promotes them from `_inbox/` to `entries/`.

## Entry Format

Each entry is a markdown file with YAML frontmatter:

```yaml
---
title: "Descriptive Title"
type: pattern        # pattern | decision | domain | integration | debugging | tool | research
tags: [tag1, tag2]
domain: software-engineering  # software-engineering | optical-networking | ml-ai | devops | research-methods | general
created: 2026-02-20
updated: 2026-02-20
confidence: medium   # low (one experience) | medium (2+ projects) | high (battle-tested)
complexity: medium   # low | medium | high
related: [other_entry_slugs]
---
```

**Standard entries** have 7 sections: Problem, Context, Approach, Key Decisions, Pitfalls & Gotchas, Recipe, Verification.

**Quick entries** have 4 sections: Problem, Solution, Why It Works, Watch Out For.

See `templates/` for detailed guidance with examples.

## Cross-Agent Compatibility

This is just a folder of markdown files. Any agent that can read files can use it.

| Agent | Search | Capture |
|-------|--------|---------|
| Claude Code | Auto via CLAUDE.md | Auto via CLAUDE.md |
| Codex / OpenCode | Add to task prompt | Add to task prompt |
| Cursor | Add as workspace folder | Reference in rules |
| Any future agent | Read index.md | Write to _inbox/ |

## Scripts

All scripts are Python 3.9+, standard library only (no pip dependencies).

| Script | What it does |
|--------|-------------|
| `python scripts/validate.py --all` | Validate all entries against the schema |
| `python scripts/validate.py <file>` | Validate a single entry |
| `python scripts/rebuild_index.py` | Regenerate index.md and tags.md |
| `python scripts/curate.py` | Process _inbox/, validate, categorize, rebuild index |
| `python scripts/curate.py --commit` | Same + git commit and push |

## License

MIT
