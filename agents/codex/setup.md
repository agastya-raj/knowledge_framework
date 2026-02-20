# OpenAI Codex Setup

## Overview

Codex (OpenAI's coding agent) doesn't have slash commands or CLAUDE.md. Instead, knowledge base integration works through:
- **AGENTS.md** — project-level instructions Codex reads automatically
- **Task prompts** — include knowledge base instructions in your task description

## Installation

### Option A: Project-Level AGENTS.md (Recommended)

Add the following to your project's `AGENTS.md` (or create one at the project root):

```markdown
## Knowledge Base

A shared knowledge base exists at ~/knowledge_framework.

### Before Starting Work

1. Read `~/knowledge_framework/index.md` to check for relevant past knowledge
2. If you find entries matching your current task, read the full entry from `entries/{category}/{slug}.md`
3. Apply the knowledge — use patterns and approaches described, but generate fresh code for this project

### After Completing Significant Work

When you complete a non-trivial task (new integration, hard bug fix, architectural decision), capture knowledge:

1. Create a file in `~/knowledge_framework/_inbox/` named `YYYYMMDD_short_slug.md`
2. Use this format:

\`\`\`yaml
---
title: "What was learned"
tags: [relevant, tags]
source_project: "this project name"
drafted: YYYY-MM-DD
---
\`\`\`

3. Include sections: What I Did, What I Learned, Pitfalls
4. Suggest a category (pattern/decision/domain/integration/debugging/tool/research)
```

### Option B: Task Prompt Instructions

When giving Codex a task, prepend:

```
Before starting, check ~/knowledge_framework/index.md for relevant knowledge about [topic].
After completing, write learnings to ~/knowledge_framework/_inbox/YYYYMMDD_slug.md.
```

## Equivalent Workflows

Codex doesn't have slash commands, but you can achieve the same workflows:

### Capture (equivalent of `/capture`)

After Codex completes a task, add to your next prompt:

```
Review what you just built. Write a knowledge draft to ~/knowledge_framework/_inbox/
capturing: what problem was solved, the approach, and any pitfalls. Use the template
at ~/knowledge_framework/templates/draft.md.
```

### Reflect (equivalent of `/reflect`)

Give Codex a dedicated task:

```
Perform a deep knowledge introspection of this project. For each significant pattern,
decision, or integration:

1. Create a full knowledge entry in ~/knowledge_framework/entries/{category}/
2. Include actual code blocks where the implementation IS the knowledge
3. Use the template at ~/knowledge_framework/templates/standard.md
4. Add a "Key Code" section with annotated code snippets
5. After creating entries, run: python ~/knowledge_framework/scripts/rebuild_index.py
6. Validate: python ~/knowledge_framework/scripts/validate.py --all
```

For session-scoped reflection, add:

```
Focus only on the changes made in the most recent commits (git log -5, git diff).
```

### Curate (equivalent of `/curate`)

Give Codex a dedicated task:

```
Curate the knowledge base at ~/knowledge_framework:
1. Read all files in _inbox/
2. For each draft: polish into a full entry, place in entries/{category}/
3. Check for duplicates against existing entries in index.md
4. Run: python ~/knowledge_framework/scripts/curate.py --commit
```

## Codex-Specific Considerations

- **Sandbox environment:** Codex may run in a sandbox. Ensure `~/knowledge_framework` is accessible within the sandbox or mount it as a volume.
- **No conversation context:** Unlike Claude Code, Codex doesn't carry context between tasks. Each capture/reflect prompt needs to be self-contained.
- **File access:** Codex can read/write files. The knowledge base is just markdown files, so no special tooling is needed.
- **Git operations:** Codex can run git commands. The `curate.py --commit` flag handles the commit+push workflow.

## Verification

Give Codex this task to verify:

```
Read ~/knowledge_framework/index.md and summarize what knowledge entries exist.
Then create a test draft in ~/knowledge_framework/_inbox/YYYYMMDD_test.md with
title "Test Entry" and any valid frontmatter. Run python ~/knowledge_framework/scripts/validate.py
on it to confirm the format is correct. Delete the test file when done.
```
