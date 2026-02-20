# Claude Code Setup

## Overview

Claude Code has first-class support for the knowledge framework via:
- **CLAUDE.md** integration — agents auto-search and auto-capture
- **Slash commands** — `/capture`, `/reflect`, `/curate` for explicit knowledge workflows

## Installation

### Step 1: Add Knowledge Base Pointer

Add the following to `~/.claude/CLAUDE.md` (global, all projects) or to a project's `.claude/CLAUDE.md` (project-specific):

```markdown
## Knowledge Base
Shared knowledge base at ~/knowledge_framework.
- **Before non-trivial tasks:** scan `index.md` for relevant entries, read full entries if matched
- **After significant work:** drop a draft in `_inbox/` using the draft template
- **On request:** curate drafts into polished entries per CLAUDE.md instructions in that repo
```

Replace `~/knowledge_framework` with the actual path where you cloned the repo.

### Step 2: Install Slash Commands

Copy the command files to your Claude Code commands directory:

```bash
mkdir -p ~/.claude/commands
cp agents/claude-code/commands/capture.md ~/.claude/commands/
cp agents/claude-code/commands/reflect.md ~/.claude/commands/
cp agents/claude-code/commands/curate.md ~/.claude/commands/
```

Or as a one-liner from the knowledge_framework root:

```bash
mkdir -p ~/.claude/commands && cp agents/claude-code/commands/*.md ~/.claude/commands/
```

### Step 3: Update Paths (if needed)

The commands reference `~/ad_hoc/knowledge_framework` by default. If your knowledge base is at a different path, update all three command files:

```bash
# Example: if your knowledge base is at ~/knowledge_framework
sed -i '' 's|~/ad_hoc/knowledge_framework|~/knowledge_framework|g' ~/.claude/commands/capture.md
sed -i '' 's|~/ad_hoc/knowledge_framework|~/knowledge_framework|g' ~/.claude/commands/reflect.md
sed -i '' 's|~/ad_hoc/knowledge_framework|~/knowledge_framework|g' ~/.claude/commands/curate.md
```

## Slash Commands

### `/capture` — Quick Knowledge Capture

**What it does:** Analyzes the current session (git diff, conversation context), creates a rough draft in `_inbox/`.

**When to use:** At the end of any session where you did something non-trivial. Takes ~30 seconds.

**Example:**
```
> /capture
```

The agent will:
1. Check `git diff --stat` and recent commits
2. Review what was discussed/built in the session
3. Write a draft to `_inbox/YYYYMMDD_descriptive_slug.md`
4. Confirm what was captured

### `/reflect` — Deep Introspection

**What it does:** Thorough analysis that includes actual code blocks, configurations, and architectural detail. Creates polished entries directly in `entries/` (skips inbox).

**When to use:** After completing a significant feature, at project milestones, or when you want to extract comprehensive knowledge from a codebase.

**Two modes:**
```
> /reflect              # Analyze current session's work
> /reflect --full       # Analyze the entire project/repo
```

The agent will:
1. Deep-dive into code changes (session) or full codebase (--full)
2. Identify distinct knowledge topics
3. Create polished entries with **Key Code** sections containing annotated code blocks
4. Rebuild the index and validate
5. Report what was captured

**Key difference from `/capture`:** Entries include actual code snippets, config files, API contracts — the implementation details that ARE the knowledge.

### `/curate` — Process Inbox

**What it does:** Polishes drafts from `_inbox/` into proper entries, deduplicates against existing entries, rebuilds the index, commits and pushes.

**When to use:** When drafts have accumulated (5+ in inbox), or periodically (weekly).

**Example:**
```
> /curate
```

The agent will:
1. Read all drafts in `_inbox/`
2. Polish each into a full entry (or merge with existing)
3. Place in the correct `entries/{category}/`
4. Rebuild `index.md` and `tags.md`
5. Validate all entries
6. Commit and push to GitHub

## Automatic Behavior

With the CLAUDE.md pointer in place, Claude Code will also:
- **Auto-search** the knowledge base when starting non-trivial tasks (reads `index.md`, loads relevant entries)
- **Auto-prompt** to capture knowledge when significant work is completed (writes to `_inbox/`)

The slash commands give you explicit control over when and how knowledge is captured/curated.

## Typical Workflow

```
[Start working on a project]
    ↓
Claude auto-searches knowledge base, finds relevant entries
    ↓
[Work on the project with the agent]
    ↓
/capture                    ← quick draft at end of session
    ↓
[...more sessions...]
    ↓
/reflect                    ← deep analysis after a milestone
    ↓
/curate                     ← process accumulated drafts, push to GitHub
```

## Verification

After setup, test in a new Claude Code session:

1. Start Claude Code in any project
2. Ask: "What's in my knowledge base?" — the agent should read `index.md` and summarize
3. Run `/capture` — should create a draft (even if minimal)
4. Run `/curate` — should process the draft and rebuild the index
