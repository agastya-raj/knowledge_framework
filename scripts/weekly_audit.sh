#!/bin/bash
# Weekly Knowledge Audit — scans all projects for uncaptured knowledge
# Designed to run via launchd (weekly) or manually.
#
# What it does:
# 1. Collects breadcrumbs from _audit_queue/ (left by SessionEnd hooks)
# 2. Scans all known project dirs for recent git activity
# 3. Invokes Claude CLI to draft missing knowledge entries
# 4. Cleans up processed breadcrumbs
#
# Usage: bash scripts/weekly_audit.sh [--dry-run]

set -euo pipefail

KB_DIR="$HOME/ad_hoc/knowledge_framework"
AUDIT_DIR="$KB_DIR/_audit_queue"
INBOX_DIR="$KB_DIR/_inbox"
LOG_FILE="$KB_DIR/scripts/audit.log"
DRY_RUN="${1:-}"

# Known project directories to scan
PROJECT_DIRS=(
  "$HOME/PhD_Work/projects/edfa_booster_modeling"
  "$HOME/PhD_Work/projects/digital_twin_ofc26"
  "$HOME/PhD_Work/projects/osaas_ml_networks"
  "$HOME/PhD_Work/projects/ecoc2025"
  "$HOME/PhD_Work/projects/ais_data"
  "$HOME/PhD_Work/projects/polatis_diagnostics"
  "$HOME/PhD_Work/projects/seascan"
  "$HOME/PhD_Work/projects/cable_monitoring"
  "$HOME/PhD_Work/projects/mydas"
  "$HOME/PhD_Work/projects/power_excursion"
  "$HOME/PhD_Work/projects/single_channel_provisioning"
  "$HOME/PhD_Work/projects/consultancy"
  "$HOME/PhD_Work/projects/thesis"
  "$HOME/ad_hoc/svg_paperbanana"
  "$HOME/ad_hoc/knowledge_framework"
)

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG_FILE"
}

mkdir -p "$(dirname "$LOG_FILE")"

log "=== Weekly Knowledge Audit Starting ==="

# --- Step 1: Collect breadcrumbs ---
BREADCRUMB_COUNT=0
BREADCRUMB_SUMMARY=""

if [ -d "$AUDIT_DIR" ]; then
  for breadcrumb in "$AUDIT_DIR"/*.md; do
    [ -f "$breadcrumb" ] || continue
    BREADCRUMB_COUNT=$((BREADCRUMB_COUNT + 1))
    BREADCRUMB_SUMMARY+="$(cat "$breadcrumb")"$'\n---\n'
  done
fi

log "Found $BREADCRUMB_COUNT breadcrumbs in audit queue"

# --- Step 2: Scan project dirs for recent activity (last 7 days) ---
ACTIVITY_SUMMARY=""
ACTIVE_PROJECTS=0

for dir in "${PROJECT_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  if ! git -C "$dir" rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    continue
  fi

  RECENT=$(git -C "$dir" log --oneline --since="7 days ago" --all 2>/dev/null | head -20)
  COUNT=$(echo "$RECENT" | grep -c . 2>/dev/null || echo "0")

  if [ "$COUNT" -gt 2 ]; then
    ACTIVE_PROJECTS=$((ACTIVE_PROJECTS + 1))
    PROJECT_NAME=$(basename "$dir")
    ACTIVITY_SUMMARY+="### $PROJECT_NAME ($dir)"$'\n'
    ACTIVITY_SUMMARY+="$COUNT commits in last 7 days:"$'\n'
    ACTIVITY_SUMMARY+="$RECENT"$'\n\n'
  fi
done

log "Found $ACTIVE_PROJECTS active projects"

# --- Step 3: Check existing entries ---
EXISTING_ENTRIES=""
if [ -f "$KB_DIR/index.md" ]; then
  EXISTING_ENTRIES=$(cat "$KB_DIR/index.md")
fi

EXISTING_DRAFTS=""
for draft in "$INBOX_DIR"/*.md; do
  [ -f "$draft" ] || continue
  [ "$(basename "$draft")" = ".gitkeep" ] && continue
  EXISTING_DRAFTS+="- $(basename "$draft")"$'\n'
done

# --- Step 4: Invoke Claude to analyze and draft ---
if [ "$ACTIVE_PROJECTS" -eq 0 ] && [ "$BREADCRUMB_COUNT" -eq 0 ]; then
  log "No activity found. Nothing to audit."
  exit 0
fi

if [ "$DRY_RUN" = "--dry-run" ]; then
  log "DRY RUN — would invoke Claude with:"
  log "  Breadcrumbs: $BREADCRUMB_COUNT"
  log "  Active projects: $ACTIVE_PROJECTS"
  echo "$ACTIVITY_SUMMARY"
  exit 0
fi

PROMPT=$(cat << 'PROMPT_EOF'
You are auditing recent project activity to identify knowledge that should be captured in the knowledge framework at ~/ad_hoc/knowledge_framework.

## Existing Knowledge Base Index
EXISTING_INDEX_PLACEHOLDER

## Existing Drafts in _inbox/
EXISTING_DRAFTS_PLACEHOLDER

## Session Breadcrumbs (from hook)
BREADCRUMB_PLACEHOLDER

## Recent Project Activity (last 7 days)
ACTIVITY_PLACEHOLDER

## Your Task

1. Compare recent activity against existing entries and drafts
2. Identify significant NEW knowledge that isn't already captured
3. For each gap, create a draft in _inbox/ using the draft template
4. Skip anything trivial, already captured, or too project-specific to reuse

Use the /capture skill or write drafts directly to ~/ad_hoc/knowledge_framework/_inbox/YYYYMMDD_slug.md

Focus on patterns, architectural decisions, hard-won debugging insights, and integration knowledge that would help across projects.
PROMPT_EOF
)

# Substitute placeholders
PROMPT="${PROMPT/EXISTING_INDEX_PLACEHOLDER/$EXISTING_ENTRIES}"
PROMPT="${PROMPT/EXISTING_DRAFTS_PLACEHOLDER/$EXISTING_DRAFTS}"
PROMPT="${PROMPT/BREADCRUMB_PLACEHOLDER/$BREADCRUMB_SUMMARY}"
PROMPT="${PROMPT/ACTIVITY_PLACEHOLDER/$ACTIVITY_SUMMARY}"

log "Invoking Claude CLI for knowledge audit..."

# Run Claude in non-interactive mode against the knowledge framework
claude --print -p "$PROMPT" --cwd "$KB_DIR" 2>>"$LOG_FILE" || {
  log "ERROR: Claude CLI invocation failed (exit $?)"
  exit 1
}

# --- Step 5: Clean up processed breadcrumbs ---
if [ -d "$AUDIT_DIR" ]; then
  for breadcrumb in "$AUDIT_DIR"/*.md; do
    [ -f "$breadcrumb" ] || continue
    rm "$breadcrumb"
    log "Cleaned up breadcrumb: $(basename "$breadcrumb")"
  done
fi

log "=== Weekly Knowledge Audit Complete ==="
