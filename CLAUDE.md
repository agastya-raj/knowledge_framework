# Knowledge Framework

This is a shared knowledge base for all agents working on Agastya's projects. Every project should use it to avoid re-solving solved problems and to capture new learnings.

**Location:** `~/ad_hoc/knowledge_framework` (GitHub: knowledge_framework)

---

## When Working in This Repo

You are inside the knowledge framework itself. Your job may involve:
- Curating drafts into polished entries
- Writing or editing knowledge entries
- Improving templates or repo structure

Always follow the entry format defined in `templates/standard.md` (full entries) or `templates/quick.md` (small learnings).

## When Referenced from Another Project

If you were directed here from another project's CLAUDE.md or by a user:

### 1. Searching (Pull) — Do This When Starting Non-Trivial Tasks

Before building something significant, check if relevant knowledge exists:

1. **Read `index.md`** — a compact table of all entries with titles, types, tags, and one-line summaries
2. **Identify matches** by scanning titles and tags for relevance to your current task
3. **Read the full entry** from `entries/{category}/{slug}.md` for any matches
4. **Adapt, don't copy** — use the knowledge to inform your approach. The entry describes patterns and decisions; you generate fresh code tailored to the current project

If `index.md` is large, scan by category:
- `entries/patterns/` — architecture recipes, how-to guides
- `entries/decisions/` — design choices and tradeoffs
- `entries/domain/` — domain expertise (optical networking, ML, etc.)
- `entries/integrations/` — API/tool/library integration knowledge
- `entries/debugging/` — solutions to hard bugs
- `entries/tools/` — tool usage and configuration knowledge
- `entries/research/` — research methods and approaches

### 2. Capturing (Push) — Do This When You Complete Significant Work

When you do something non-trivial — new integration, hard bug fix, architectural decision, novel approach — capture it:

1. **Create a draft** in `_inbox/` named `YYYYMMDD_short_slug.md`
2. **Use the draft template** from `templates/draft.md` — intentionally lightweight
3. **Capture the essence** — what problem, what approach, what pitfalls, what tags. Don't polish.
4. **Continue your main work** — the draft will be curated later

#### What's Worth Capturing
- Built something that took real effort to figure out
- Made a design decision with non-obvious tradeoffs
- Solved a bug that wasted significant time
- Discovered that a tool/library/approach works (or doesn't) in a specific context
- Developed a research method or analysis pipeline
- Integrated with an unfamiliar API or system

#### What's NOT Worth Capturing
- Trivial fixes (typos, config tweaks)
- Highly project-specific logic with no reuse potential
- Information already well-documented elsewhere (link to it instead)

### 3. Curating — When Asked to "Curate the Knowledge Base"

When Agastya asks you to curate, or when you notice `_inbox/` has accumulated entries:

**Step 1: Process Drafts**

For each file in `_inbox/`:
1. Read the draft
2. Check `index.md` for existing entries on the same topic
3. **If duplicate/overlap**: merge new learnings into the existing entry — update its `updated` date and bump confidence if warranted
4. **If new**: polish into a full entry using `templates/standard.md` (or `templates/quick.md` for smaller learnings), place in the appropriate `entries/{category}/` folder
5. Delete the processed draft from `_inbox/`

**Step 2: Quality Check**

For each new/updated entry, verify:
- **Self-contained**: an agent with zero context could rebuild the system from this entry alone
- **Has pitfalls section**: the expensive lessons are the most valuable knowledge
- **Boundary conditions stated**: when does this approach NOT work?
- **Tags are accurate**: someone searching for this topic would find it
- **No code dumps**: explain patterns and approaches, not raw implementation
- **Confidence level set**: `low` (single experience), `medium` (confirmed in 2+ projects), `high` (well-established)
- **One entry per concept**: don't combine unrelated learnings, split if needed
- **Be specific over generic**: "Use batch size 32 with Adam lr=1e-3 for EDFA gain models" beats "tune hyperparameters"

**Step 3: Rebuild Index**

Regenerate `index.md` and `tags.md` by reading all entries in `entries/`:
- `index.md`: markdown table with columns — Entry (linked), Type, Tags, Summary
- `tags.md`: entries grouped by tag, each tag as a heading with linked entry list
- Update the totals and "Last curated" date at the bottom of each file

**Step 4: Commit and Push**
```
git add -A
git commit -m "knowledge: curate — [brief summary of what was added/updated]"
git push
```

## Entry Format Reference

### Frontmatter (YAML)
```yaml
title: "Human-readable title"
type: pattern | decision | domain | integration | debugging | tool | research
tags: [tag1, tag2, tag3]  # 2-5 lowercase tags
domain: software-engineering | optical-networking | ml-ai | research-methods | devops | general
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidence: high | medium | low
complexity: low | medium | high
related: [slug_of_related_entry_1, slug_of_related_entry_2]
```

### Required Sections (standard template)
1. **Problem** — what problem does this solve? when would you need this?
2. **Context** — what situation, constraints, environment?
3. **Approach** — the pattern/method, step by step
4. **Key Decisions** — why certain choices were made, alternatives considered
5. **Pitfalls & Gotchas** — what went wrong, what to watch out for
6. **Recipe** — concrete steps to rebuild from scratch
7. **Verification** — how to know it's working

### Quick template sections
1. **Problem** — what happened?
2. **Solution** — the fix or pattern
3. **Why It Works** — underlying cause
4. **Watch Out For** — caveats and edge cases
