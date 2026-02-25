---
description: Deep knowledge introspection — thorough analysis with code, configs, and architectural detail
argument-hint: [--full for entire project analysis]
allowed-tools: Read, Write, Glob, Grep, Bash(git:*, python:*)
---

You are performing a deep knowledge introspection for the knowledge base at ~/ad_hoc/knowledge_framework.

This is NOT a quick capture. This is a thorough, comprehensive extraction of everything worth knowing — including actual code, configurations, and architectural detail.

## Mode

- **Default (no argument):** Analyze the current session's work — what was changed, built, or fixed
- **`--full`:** Analyze the entire project/repo — architecture, patterns, integration points, everything worth preserving

The argument is: $ARGUMENTS

## Step 1: Deep Analysis

**For session mode (default):**
- Run `git diff --stat` to see scope of changes
- Run `git diff` to read the actual code changes
- Run `git log --oneline -10` for recent commit context
- Read key files that were created or significantly modified
- Review the conversation history for decisions, approaches tried, dead ends, and pivots

**For full project mode (`--full`):**
- Run `ls` and explore the directory structure to understand the architecture
- Read: README, config files (Dockerfile, docker-compose, package.json, pyproject.toml, etc.), main entry points
- Identify the core modules and how they connect
- Find integration points: APIs, databases, external services, auth mechanisms
- Check for patterns: error handling, data flow, state management, testing strategy
- Look at CI/CD, deployment configs, environment setup

## Step 2: Identify Knowledge Topics

From your analysis, identify distinct knowledge topics. Each becomes a separate entry. Look for:

- **Architecture patterns**: System structure, layers, component communication, data flow
- **Key code**: Non-obvious algorithms, clever solutions, hard-won correctness, tricky implementations
- **Integration knowledge**: External API contracts, auth flows, data formats, webhook handling
- **Configuration**: Docker/infra setup, environment variables, build configs that took effort
- **Design decisions**: Why X over Y, tradeoffs evaluated, constraints that shaped the design
- **Debugging knowledge**: Bugs that wasted hours, root causes that weren't obvious, diagnostic techniques
- **Research methods**: Data pipelines, analysis approaches, experiment setups

## Step 3: Create Polished Entries

For each topic, create a **full entry** directly in `~/ad_hoc/knowledge_framework/entries/{category}/` (NOT in _inbox/ — these are already polished).

Filename: `snake_case_slug.md`

Category mapping: pattern→patterns, decision→decisions, domain→domain, integration→integrations, debugging→debugging, tool→tools, research→research

### Entry Format

```yaml
---
title: "Descriptive title"
type: pattern
tags: [2-5 lowercase tags]
domain: software-engineering
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidence: medium
complexity: high
related: []
---
```

### Required Sections

1. **Problem** — what this solves, when you'd need it
2. **Context** — project, constraints, environment, tools involved
3. **Approach** — the architecture/method, step by step
4. **Key Decisions** — why certain choices were made, alternatives rejected
5. **Key Code** — actual code blocks with annotations explaining WHY not just WHAT:
   - Critical implementation snippets
   - Configuration files that took effort to get right
   - API contracts, data schemas, type definitions
   - Build/deploy commands that aren't obvious
   - Annotate each block: what it does, why it's this way, what breaks if you change it
6. **Pitfalls & Gotchas** — what went wrong, what was non-obvious, what would waste time
7. **Recipe** — concrete steps to rebuild from scratch
8. **Verification** — how to know it's working

### Key Code Section Guidelines

This is what makes /reflect different from /capture. Include actual code when:
- The implementation embodies non-obvious logic that can't be described abstractly
- Configuration values matter (ports, timeouts, buffer sizes, model hyperparameters)
- The exact API contract or data schema is the knowledge
- A code pattern is reusable but subtle enough that regenerating it from description would lose fidelity

Format code blocks with language tags and inline annotations:

```python
# WHY: Batch normalization before ReLU gives 0.3 dB better gain prediction
# because the EDFA gain distribution is not zero-centered
model = nn.Sequential(
    nn.Linear(n_channels * 2, 256),
    nn.BatchNorm1d(256),  # Critical: before activation, not after
    nn.ReLU(),
    ...
)
```

## Step 4: Rebuild Index

After creating all entries:
```bash
python ~/ad_hoc/knowledge_framework/scripts/rebuild_index.py
```

## Step 5: Validate

```bash
python ~/ad_hoc/knowledge_framework/scripts/validate.py --all
```

Fix any validation errors before finishing.

## Step 6: Report

Summarize to the user:
- Number of entries created, with titles
- Topics covered
- Total code blocks preserved
- Any areas where you think the user should add more detail (you'll flag these with TODO comments in the entries)
- Suggest running `git add -A && git commit -m "knowledge: reflect — [summary]" && git push` in the knowledge_framework repo
