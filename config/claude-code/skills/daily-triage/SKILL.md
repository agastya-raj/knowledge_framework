---
name: daily-triage
description: "Triage ~/Downloads into organized ~/PhD_Work structure, delete junk, and update macOS color tags. Run daily or on demand."
---

# Daily Downloads Triage

You are performing a file triage for Agastya, a PhD researcher at TCD working on optical networking.

## Setup

1. Read `~/.claude/CLAUDE.md` for the current triage rules, project list, and file organization memory.
2. Read `~/.claude/memory/context/file-organization.md` for the full classification rules.

## Step 1: Scan ~/Downloads

List all files and folders in `~/Downloads` (excluding `.DS_Store` and `.localized`). If Downloads is empty, report "Downloads is clean" and skip to Step 4.

## Step 2: Classify and Move Files

For each file/folder found, classify it using these rules (in priority order):

**By keyword match** (check filename against these patterns):
- edfa, booster, gain_spectrum, jocn, nf_data → `~/PhD_Work/projects/edfa_booster_modeling/`
- dlm, ntt, digital_twin, ila, nict, ofc → `~/PhD_Work/projects/digital_twin_ofc26/`
- osaas, ml_module, sensing, ook, ml_network → `~/PhD_Work/projects/osaas_ml_networks/`
- ecoc → `~/PhD_Work/projects/ecoc2025/`
- polatis, switch_diag → `~/PhD_Work/projects/polatis_diagnostics/`
- seascan → `~/PhD_Work/projects/seascan/`
- cable → `~/PhD_Work/projects/cable_monitoring/`
- mydas → `~/PhD_Work/projects/mydas/`
- power_excursion → `~/PhD_Work/projects/power_excursion/`
- ais → `~/PhD_Work/projects/ais_data/`
- visa, irp, immigration → `~/PhD_Work/personal/visa_immigration/`
- receipt, invoice, payment, reimburs → `~/PhD_Work/personal/finance/`
- thesis → `~/PhD_Work/personal/thesis/`

**By file type** (when no keyword match):
- `.dmg`, `.pkg`, `.iso` → DELETE (installers/junk)
- `.pdf` (academic paper) → `~/PhD_Work/publications/papers/`
- `.pdf` (personal/admin) → `~/PhD_Work/personal/`
- `.pptx` → `~/PhD_Work/publications/presentations/`
- `.csv`, `.xlsx` (data files) → `~/PhD_Work/shared_resources/data/`
- `.svg`, `.png`, `.ai`, `.jpg` (figures) → `~/PhD_Work/shared_resources/figures/`
- Code projects (folders with package.json, .git, .py files) → `~/PhD_Work/projects/` or `~/PhD_Work/tools/`

**Junk to delete automatically:**
- Duplicate files (same name with ` (1)`, ` (2)` suffixes)
- Empty folders
- `.DS_Store` files
- Temporary/debug files (`.log`, `*-debug-*`, `*temp*`)

**If uncertain:** Move to `~/PhD_Work/shared_resources/unsorted/` and flag in the report.

## Step 3: Delete Junk

Remove identified junk files. Count deletions.

## Step 4: Update Color Tags

Use `osascript` to update macOS Finder label colors on all project folders based on recency of last-modified file:

- **Red (label index 6):** Modified in last 24 hours
- **Orange (label index 7):** Modified in last week
- **Yellow (label index 5):** Modified in last month
- **Green (label index 2):** Modified in last 3 months
- **Blue (label index 4):** Modified in last 6 months
- **Purple (label index 3):** Modified in last 12 months
- **Gray (label index 1):** Not modified in over a year

Apply to all folders in `~/PhD_Work/projects/` and the top-level folders in `~/PhD_Work/`.

The osascript to set a label on a folder:
```
tell application "Finder" to set label index of (POSIX file "/path/to/folder" as alias) to INDEX
```

Calculate recency by finding the most recently modified file in each folder (excluding `.DS_Store`, `node_modules/`, `.git/`).

## Step 5: Report

Provide a summary including:
- Files moved (with source → destination)
- Files deleted (with reason)
- Files flagged as unsorted
- Color tag updates applied
- Any new patterns noticed (suggest additions to CLAUDE.md triage rules)

## Step 6: Learn

If any files were hard to classify or the user corrects a classification, update:
- `~/.claude/CLAUDE.md` (triage rules table)
- `~/.claude/memory/context/file-organization.md` (classification rules)

## Naming Convention
All moved files should follow snake_case naming. Rename files if needed (replace spaces with underscores, lowercase).
