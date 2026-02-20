# Setup Guide

This guide is for AI agents setting up the Knowledge Framework for a user. Follow these steps in order.

## Step 1: Clone the Repository

Clone to a stable, accessible location:

```bash
git clone https://github.com/agastya-raj/knowledge_framework ~/knowledge_framework
```

If the user already has the repo, skip this step.

## Step 2: Clear Seed Entries (Optional)

The repo ships with example entries from the author's optical networking research. If the user wants a clean start:

```bash
rm -f ~/knowledge_framework/entries/patterns/*.md
rm -f ~/knowledge_framework/entries/domain/*.md
python ~/knowledge_framework/scripts/rebuild_index.py
```

If the user wants to keep the examples as reference, skip this step.

## Step 3: Set Up Your Agent

Detailed setup guides for each agent are in the `agents/` directory:

| Agent | Guide | Features |
|-------|-------|----------|
| **Claude Code** | [agents/claude-code/setup.md](agents/claude-code/setup.md) | CLAUDE.md auto-integration + `/capture`, `/reflect`, `/curate` slash commands |
| **Codex (OpenAI)** | [agents/codex/setup.md](agents/codex/setup.md) | AGENTS.md integration + equivalent prompt workflows |
| **OpenCode** | [agents/opencode/setup.md](agents/opencode/setup.md) | instructions.md integration + equivalent prompt workflows |

### Quick Setup (any agent)

At minimum, add this to your agent's instruction file:

```markdown
## Knowledge Base
A shared knowledge base exists at ~/knowledge_framework.
- Before non-trivial tasks: read index.md, find relevant entries, read them
- After significant work: write a draft to _inbox/YYYYMMDD_slug.md
```

### Claude Code Slash Commands

Claude Code supports three slash commands. Install them:

```bash
mkdir -p ~/.claude/commands
cp ~/knowledge_framework/agents/claude-code/commands/*.md ~/.claude/commands/
```

| Command | What it does |
|---------|-------------|
| `/capture` | Quick knowledge capture — drafts what was learned this session into `_inbox/` |
| `/reflect` | Deep introspection — thorough analysis with code blocks, configs, architecture. Use `/reflect --full` for entire project. |
| `/curate` | Process inbox — polish drafts into entries, rebuild index, commit and push |

**Update paths:** If your knowledge base is not at `~/ad_hoc/knowledge_framework`, update the paths in the copied command files.

## Step 4: Customize for the User

### Update domains (if needed)

The default valid domains in `scripts/validate.py` are:
- `software-engineering`, `optical-networking`, `ml-ai`, `devops`, `research-methods`, `general`

If the user works in different domains, update the `VALID_DOMAINS` set in `scripts/validate.py` and document them in `CLAUDE.md`.

### Update entry categories (if needed)

Default categories: `patterns`, `decisions`, `domain`, `integrations`, `debugging`, `tools`, `research`.

To add a new category:
1. `mkdir entries/new_category && touch entries/new_category/.gitkeep`
2. Add the type mapping in `scripts/curate.py` (`TYPE_TO_CATEGORY` dict)
3. Add the type to `VALID_TYPES` in `scripts/validate.py`
4. Document it in `CLAUDE.md`

## Step 5: Verify

```bash
cd ~/knowledge_framework
python scripts/validate.py --all    # Should pass with 0 failures
python scripts/rebuild_index.py     # Should complete without errors
```

Then start a new agent session and ask: "What's in my knowledge base?" — the agent should find and summarize `index.md`.

## Step 6: Git Remote (Optional)

```bash
cd ~/knowledge_framework
git remote add origin <your-github-url>
git push -u origin main
```

The `curate.py --commit` flag handles commit+push during curation.

## Troubleshooting

**Agent doesn't search the knowledge base:**
Verify the path in your agent's config file matches the actual repo location.

**`curate.py` import errors:**
Run from the repo root: `cd ~/knowledge_framework && python scripts/curate.py`

**Validation failures:**
Check that frontmatter `type` and `domain` values are in the valid lists. Run `python scripts/validate.py <file>` for specific errors.

**Slash commands not showing in Claude Code:**
Verify files exist at `~/.claude/commands/capture.md`, `reflect.md`, `curate.md`. Restart Claude Code.
