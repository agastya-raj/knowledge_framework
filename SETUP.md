# Setup Guide

This guide is for AI agents setting up the Knowledge Framework for a user. Follow these steps in order.

## Step 1: Clone the Repository

Clone to a stable, accessible location. Recommended: `~/knowledge_framework` or within the user's workspace.

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

## Step 3: Integrate with Agent Configuration

The knowledge base needs a small pointer in the agent's configuration so it knows the knowledge base exists. This is the **only setup step that's agent-specific**.

### Claude Code

Add the following to the user's `~/.claude/CLAUDE.md` (or the project's `CLAUDE.md`):

```markdown
## Knowledge Base
Shared knowledge base at ~/knowledge_framework (GitHub: knowledge_framework).
- **Before non-trivial tasks:** scan `index.md` for relevant entries, read full entries if matched
- **After significant work:** drop a draft in `_inbox/` using the draft template
- **On request:** curate drafts into polished entries per CLAUDE.md instructions in that repo
```

### Codex (OpenAI)

Add to the project's `AGENTS.md` or task instructions:

```markdown
## Knowledge Base
Before starting non-trivial tasks, check ~/knowledge_framework/index.md for relevant past knowledge.
After completing significant work, write a knowledge draft to ~/knowledge_framework/_inbox/ following the template in ~/knowledge_framework/templates/draft.md.
```

### OpenCode / Other Agents

Add to the agent's system prompt or project instructions (same content as the Codex section above). The key information is:
- **Path:** `~/knowledge_framework`
- **Search:** Read `index.md`, then read full entries from `entries/`
- **Capture:** Write drafts to `_inbox/` using `templates/draft.md`

### Cursor

Add the knowledge_framework directory as a workspace folder. Add to `.cursorrules`:

```
When starting non-trivial tasks, check @knowledge_framework/index.md for relevant knowledge entries.
After significant work, create a draft in @knowledge_framework/_inbox/.
```

## Step 4: Customize for the User

### Update domains (if needed)

The default valid domains in `scripts/validate.py` are:
- `software-engineering`
- `optical-networking`
- `ml-ai`
- `devops`
- `research-methods`
- `general`

If the user works in different domains, update the `VALID_DOMAINS` set in `scripts/validate.py` and document the new domains in `CLAUDE.md`.

### Update entry categories (if needed)

The default categories in `entries/` are: `patterns`, `decisions`, `domain`, `integrations`, `debugging`, `tools`, `research`. To add a new category:

1. Create the directory: `mkdir entries/new_category`
2. Add a `.gitkeep`: `touch entries/new_category/.gitkeep`
3. Add the type mapping in `scripts/curate.py` (the `TYPE_TO_CATEGORY` dict)
4. Add the type to `VALID_TYPES` in `scripts/validate.py`
5. Document it in `CLAUDE.md`

## Step 5: Create First Knowledge Entry

To verify the setup works, create a test entry:

1. Write a draft to `_inbox/`:
   ```bash
   cp ~/knowledge_framework/templates/draft.md ~/knowledge_framework/_inbox/20260220_test_setup.md
   ```

2. Edit the draft with real content (title, tags, what was learned).

3. Run the curator:
   ```bash
   python ~/knowledge_framework/scripts/curate.py
   ```

4. Verify the entry was promoted to `entries/` and appears in `index.md`.

5. If it works, delete the test entry or keep it as your first real entry.

## Step 6: Set Up Git Push (Optional)

If the user wants changes synced to GitHub:

```bash
cd ~/knowledge_framework
git remote add origin <github-url>
git push -u origin main
```

The `curate.py --commit` flag handles commit and push automatically during curation.

## Verification

After setup, verify:
- [ ] `python scripts/validate.py --all` passes with 0 failures
- [ ] `python scripts/rebuild_index.py` completes without errors
- [ ] The agent configuration file (CLAUDE.md / AGENTS.md) contains the knowledge base pointer
- [ ] Starting a new session with the agent, it can find and read `index.md`

## Troubleshooting

**Agent doesn't auto-search the knowledge base:**
The agent config pointer might not be loaded. Verify the path in CLAUDE.md/AGENTS.md matches the actual repo location.

**`curate.py` fails with import errors:**
Run from the scripts directory or ensure Python can find sibling modules:
```bash
cd ~/knowledge_framework && python scripts/curate.py
```

**Entries fail validation unexpectedly:**
Check that the frontmatter `type` and `domain` values match the valid options. Run `python scripts/validate.py <file>` for specific error messages.
