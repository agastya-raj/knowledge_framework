#!/bin/bash
# Knowledge Capture Hook — runs on Claude Code SessionEnd
# Checks if the session's project had significant git changes and logs
# a breadcrumb to the knowledge framework audit queue.
#
# Breadcrumbs are processed by the weekly audit job or manually via /curate.

set -euo pipefail

KB_DIR="$HOME/ad_hoc/knowledge_framework"
AUDIT_DIR="$KB_DIR/_audit_queue"

# Read hook input from stdin
INPUT=$(cat)

# Prevent infinite loops if Stop hook is re-firing
STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$STOP_ACTIVE" = "true" ]; then
  exit 0
fi

CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')

# Skip if no working directory or if we're inside the knowledge framework itself
if [ -z "$CWD" ] || [ "$CWD" = "$KB_DIR" ]; then
  exit 0
fi

# Skip if not a git repo
if ! git -C "$CWD" rev-parse --is-inside-work-tree &>/dev/null; then
  exit 0
fi

# Check for commits made in the last 3 hours (covers most session lengths)
RECENT_COMMITS=$(git -C "$CWD" log --oneline --since="3 hours ago" --all 2>/dev/null | head -30)
COMMIT_COUNT=$(echo "$RECENT_COMMITS" | grep -c . 2>/dev/null || echo "0")

# Skip if fewer than 3 commits (trivial sessions)
if [ "$COMMIT_COUNT" -lt 3 ]; then
  exit 0
fi

# Get project name from directory
PROJECT_NAME=$(basename "$CWD")

# Get changed file stats
DIFF_STAT=$(git -C "$CWD" diff --stat HEAD~"$COMMIT_COUNT"..HEAD 2>/dev/null | tail -1 || echo "unknown")

# Create the breadcrumb
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BREADCRUMB_FILE="$AUDIT_DIR/${TIMESTAMP}_${PROJECT_NAME}.md"

mkdir -p "$AUDIT_DIR"

cat > "$BREADCRUMB_FILE" << EOF
---
project: "$PROJECT_NAME"
project_path: "$CWD"
session_id: "$SESSION_ID"
timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
commit_count: $COMMIT_COUNT
---

## Recent Commits

$RECENT_COMMITS

## Diff Summary

$DIFF_STAT
EOF

exit 0
