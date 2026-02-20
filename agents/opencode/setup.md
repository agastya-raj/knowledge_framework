# OpenCode Setup

## Overview

OpenCode is a terminal-based AI coding agent. Knowledge base integration works through:
- **instructions.md** — OpenCode's project-level instruction file
- **Session prompts** — include knowledge base references in your prompts

## Installation

### Step 1: Add to OpenCode Instructions

OpenCode reads project instructions from `instructions.md` (or configurable via `OPENCODE_INSTRUCTIONS`). Add the following:

```markdown
## Knowledge Base

A shared knowledge base exists at ~/knowledge_framework.

### Searching
Before starting non-trivial tasks:
1. Read `~/knowledge_framework/index.md` — a table of all knowledge entries
2. If you find relevant entries, read the full markdown for approach, recipe, and pitfalls
3. Apply the knowledge to your current task — adapt patterns, don't copy code

### Capturing
After completing significant work (new integration, hard bug, architectural decision):
1. Create `~/knowledge_framework/_inbox/YYYYMMDD_slug.md`
2. Include: title, tags, what was done, what was learned, pitfalls
3. Use the draft template at `~/knowledge_framework/templates/draft.md`
```

### Step 2: Global Configuration (Optional)

If you want all OpenCode sessions to know about the knowledge base, add the instructions to your global OpenCode config. Check your OpenCode configuration at `~/.opencode/` or the `OPENCODE_INSTRUCTIONS` environment variable.

## Equivalent Workflows

### Capture

After a productive session, type:

```
Review what we just built. Create a knowledge draft at ~/knowledge_framework/_inbox/
with the title, tags, key learnings, and pitfalls. Follow the template at
~/knowledge_framework/templates/draft.md.
```

### Reflect (Deep Introspection)

For session-scoped analysis:

```
Do a deep knowledge introspection of what we built this session. For each
significant pattern or decision, create a full entry in
~/knowledge_framework/entries/{appropriate_category}/. Include actual code
blocks where the implementation IS the knowledge. Add a "Key Code" section
with annotated snippets. Use the template at
~/knowledge_framework/templates/standard.md. After creating entries, run
python ~/knowledge_framework/scripts/rebuild_index.py and validate with
python ~/knowledge_framework/scripts/validate.py --all.
```

For full project analysis:

```
Analyze this entire project and extract all knowledge worth preserving.
Focus on: architecture, key code patterns, integration details, configurations,
and non-obvious decisions. Create comprehensive entries in
~/knowledge_framework/entries/ with code blocks and configs included.
Rebuild the index when done.
```

### Curate

```
Process all drafts in ~/knowledge_framework/_inbox/. For each: polish into a
full entry, check for duplicates against index.md, place in the right
entries/{category}/ folder. Then run:
python ~/knowledge_framework/scripts/curate.py --commit
```

## OpenCode-Specific Considerations

- **Tool access:** OpenCode has file read/write and bash access. The knowledge base is plain markdown, so no special tools are needed.
- **Session persistence:** OpenCode sessions are ephemeral. Knowledge captured in `_inbox/` persists on disk between sessions.
- **Model selection:** For deep introspection (`/reflect` equivalent), use a more capable model if available. The thorough analysis benefits from larger context and reasoning.
- **MCP servers:** If OpenCode supports MCP, you could potentially add a knowledge-search MCP server in the future for seamless integration.

## Verification

In an OpenCode session:

```
Read ~/knowledge_framework/index.md and tell me what knowledge entries are available.
```

This should return the entry table. If it can't find the file, check the path.
