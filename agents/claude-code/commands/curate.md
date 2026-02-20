---
description: Curate the knowledge base — process inbox drafts into polished entries
allowed-tools: Read, Write, Glob, Grep, Bash(git:*, python:*)
---

You are curating the knowledge base at ~/ad_hoc/knowledge_framework.

## Instructions

Follow the curation process defined in ~/ad_hoc/knowledge_framework/CLAUDE.md (section 3: Curating).

In summary:

### 1. Check Inbox

Read all `.md` files in `~/ad_hoc/knowledge_framework/_inbox/`. If empty, tell the user there's nothing to curate.

### 2. Process Each Draft

For each file in `_inbox/`:
1. Read the draft
2. Check `index.md` for existing entries on the same topic
3. **If duplicate/overlap:** merge new learnings into the existing entry, update its `updated` date, bump confidence if warranted
4. **If new:** Polish into a full entry using `templates/standard.md` (or `templates/quick.md` for smaller learnings)
5. Place in the appropriate `entries/{category}/` folder
6. Delete the processed draft from `_inbox/`

### 3. Quality Check

For each new/updated entry, verify:
- Self-contained: an agent with zero context could rebuild from this entry
- Has pitfalls section
- Tags are accurate and specific
- Confidence level is set appropriately
- No code dumps without explanation (annotate all code blocks)

### 4. Rebuild Index

```bash
python ~/ad_hoc/knowledge_framework/scripts/rebuild_index.py
```

### 5. Validate

```bash
python ~/ad_hoc/knowledge_framework/scripts/validate.py --all
```

### 6. Commit and Push

```bash
cd ~/ad_hoc/knowledge_framework && git add -A && git commit -m "knowledge: curate — [brief summary]" && git push
```

### 7. Report

Tell the user:
- How many drafts were processed
- What entries were created/updated (titles)
- Current total: entries and tags
