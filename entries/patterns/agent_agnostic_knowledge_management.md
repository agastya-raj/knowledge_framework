---
title: "Agent-Agnostic Knowledge Management for AI-Assisted Development"
type: pattern
tags: [knowledge-management, multi-agent, workflow, knowledge-base, agentic, cross-tool]
domain: software-engineering
created: 2026-02-20
updated: 2026-02-20
confidence: medium
complexity: medium
related: [multi_agent_research_pipeline]
---

# Agent-Agnostic Knowledge Management for AI-Assisted Development

## Problem

When working across multiple AI coding agents (Claude Code, Codex, OpenCode, Cursor, etc.), knowledge gets trapped in individual conversations. You solve the same problem differently each time because no agent remembers what another agent learned. Code repositories don't transfer well between projects — the integration cost often exceeds rebuilding from scratch. The real value isn't the code, it's the knowledge of *how* and *why* something was built.

## Context

This pattern emerged from experience building SDK bridges, integrations, and research tools across many projects. Key observations:
- Code is ephemeral in the age of agents — agents regenerate code faster than you can integrate old code
- The expensive part is the knowledge: which approach works, what tradeoffs exist, what pitfalls to avoid
- Different agents have different context mechanisms (CLAUDE.md, system prompts, etc.) but ALL can read files
- A well-written knowledge doc produces better agent output than a stale code repository

## Approach

### Core Architecture: Markdown Files in a Git Repo

The knowledge base is a git repository of structured markdown files. No database, no server, no special tooling. The file system IS the search engine. Any agent that can read files can use it.

```
knowledge_framework/
├── CLAUDE.md          # Agent instructions (search, capture, curate)
├── index.md           # Compact table of all entries
├── tags.md            # Entries grouped by tag
├── _drafts/           # Rough captures during work
├── templates/         # Entry and draft templates
└── entries/
    ├── patterns/      # How-to recipes
    ├── decisions/     # Design tradeoffs
    ├── domain/        # Domain expertise
    ├── integrations/  # API/tool knowledge
    ├── debugging/     # Bug solutions
    ├── tools/         # Tool usage
    └── research/      # Research methods
```

### The Pull Side (Using Knowledge)

Agents search the knowledge base when starting non-trivial tasks:
1. Read `index.md` — a compact table (~1 line per entry) that fits in any context window
2. Match entries by title/tags to the current task
3. Read only the 1-3 relevant full entries
4. Adapt the knowledge to the current project context — fresh code, not copy-paste

**Context cost:** ~200 lines for the index + ~100 lines per relevant entry. Negligible.

### The Push Side (Capturing Knowledge)

Two-phase capture prevents knowledge capture from disrupting main work:

**Phase 1 — Quick Draft (during work):**
When an agent does something non-trivial, it drops a rough draft into `_drafts/`. The draft is intentionally lightweight — title, what was done, what was learned, rough tags. Takes 2 minutes. Agent continues with main task.

**Phase 2 — Curation (periodic):**
When triggered, a curator agent processes all drafts:
- Deduplicates against existing entries
- Polishes drafts into full entries with proper structure
- Files into the correct category
- Rebuilds index and tag files
- Commits and pushes to git

### Cross-Agent Integration

The key insight: **use the lowest common denominator — files.**

| Agent | Integration method |
|-------|-------------------|
| Claude Code | CLAUDE.md instructions auto-trigger search/capture |
| Codex | Include in task prompt: "Check ~/knowledge_framework/index.md" |
| OpenCode | Same as Codex — reference in system/task prompt |
| Cursor | Add as workspace folder, reference in rules |
| Any agent | Point to the repo. If it can read files, it can use the knowledge base. |

The CLAUDE.md in the knowledge repo itself contains full instructions. Any Claude Code session that reads it immediately knows how to search, capture, and curate.

### Quality Control

Built into the curation process, not a separate step:
- **Self-containment check**: could an agent with zero context rebuild from this entry?
- **Pitfalls required**: entries without "what went wrong" sections are incomplete
- **Confidence scoring**: `low` (one experience) → `medium` (confirmed across projects) → `high` (well-established)
- **Boundary conditions**: when does this approach NOT work?
- **No code dumps**: patterns and approaches, not raw implementation

## Key Decisions

**Markdown over structured data (JSON/YAML docs)**: Markdown is human-readable, agent-readable, git-diffable, and requires no tooling. YAML frontmatter gives just enough structure for indexing without sacrificing readability.

**Flat index over embedding search (initially)**: At <200 entries, a flat markdown table that any agent can grep is simpler and more portable than a vector database. Embeddings can be added as an enhancement layer later without changing the core architecture.

**Agent-driven curation over automated scripts**: Curation requires judgment (is this a duplicate? what category? is it self-contained?). Agents are better at this than scripts. The tradeoff is that curation must be explicitly triggered.

**Fully self-contained entries over code links**: If entries depend on external repos, they break when repos are archived, refactored, or deleted. Self-contained entries survive indefinitely. The code is the ephemeral artifact; the knowledge is permanent.

**Draft-then-curate over write-once**: Lowering the capture barrier (rough drafts) means more knowledge gets captured. Quality is enforced at curation time, not capture time. This prevents "I'll write it up properly later" procrastination.

## Pitfalls & Gotchas

**The #1 risk is non-adoption.** If capturing knowledge feels like a chore, it won't happen. The draft template must be VERY lightweight. If it takes more than 2 minutes to capture, the barrier is too high.

**Index staleness.** If the index isn't rebuilt after adding entries, agents find stale results. Always rebuild index as part of curation, never separately.

**Over-capturing creates noise.** Not everything is worth a knowledge entry. Trivial fixes, highly project-specific logic, and well-documented external tools don't belong. The "what's NOT worth capturing" guidelines must be clear.

**Agent instruction bloat.** The pointer in global CLAUDE.md must stay small (3-5 lines). If you put too much instruction there, it adds context cost to every session regardless of relevance.

**Cross-agent prompt differences.** Claude Code reads CLAUDE.md automatically. Other agents need explicit prompting. Don't assume all agents will auto-search — for non-Claude agents, you'll need to mention the knowledge base in your task prompt.

## Recipe

1. **Create the repository** with the directory structure above
2. **Write CLAUDE.md** with search, capture, and curation instructions
3. **Create templates** for entries (full) and drafts (lightweight)
4. **Seed with 2-3 real entries** so it's not empty — agents engage better with populated knowledge bases
5. **Add a pointer to global agent config** (e.g., `~/.claude/CLAUDE.md`): just 3 lines saying the knowledge base exists and where
6. **For each new project**: no setup needed if using Claude Code (global config already points to it). For other agents, mention the knowledge base path in the project prompt.
7. **Curate periodically**: weekly or when drafts accumulate to 5+. Say "curate my knowledge base" to any capable agent.
8. **Grow the index organically**: confidence levels will naturally rise as patterns are confirmed across projects

## Verification

- Agents find and use relevant knowledge when starting tasks (check by asking "did you find anything in the knowledge base?")
- New drafts appear in `_drafts/` after significant work sessions
- Curation produces clean, self-contained entries
- The index stays current and accurate
- Knowledge entries are actually useful — an agent reading one produces better output than one without it
- Entry count grows over time; confidence levels increase as patterns are confirmed
