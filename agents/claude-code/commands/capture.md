---
description: Quick knowledge capture — draft what was learned this session into the knowledge base
allowed-tools: Read, Write, Glob, Grep, Bash(git diff:*, git log:*, git status:*, git show:*)
---

You are capturing knowledge from the current session into the knowledge base at ~/ad_hoc/knowledge_framework.

## Instructions

### 1. Analyze the Session

Figure out what was done:
- Run `git diff --stat` and `git log --oneline -5` to see recent changes
- Review the conversation context for key decisions, approaches, and pitfalls encountered
- Identify what was non-trivial — new integrations, hard bugs, architectural decisions, novel approaches

If nothing significant was done this session, say so and don't create an empty entry.

### 2. Create a Draft

Write a file to `~/ad_hoc/knowledge_framework/_inbox/` named `YYYYMMDD_short_slug.md` (today's date + descriptive slug in snake_case).

Use this format:

```
---
title: "Short descriptive title of the learning"
tags: [2-5 lowercase tags for searchability]
source_project: "name or path of the current project"
drafted: YYYY-MM-DD
---

## What I Did

Brief description of the task/project/problem solved.

## What I Learned

Key insights, patterns, or approaches worth remembering. Be specific — "Use batch_size=32 with Adam lr=1e-3" not "tune hyperparameters."

## Pitfalls

What went wrong, was surprisingly hard, or would waste time for someone doing this again.

## Tags Suggestion

Suggest category: pattern | decision | domain | integration | debugging | tool | research
Suggest domain: software-engineering | optical-networking | ml-ai | research-methods | devops | general
```

### 3. Confirm

Tell the user:
- What was captured (title + key learning in one sentence)
- The file path
- Remind them to run `/curate` or `python ~/ad_hoc/knowledge_framework/scripts/curate.py` when drafts accumulate
