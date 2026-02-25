#!/bin/bash
# sync_config.sh — Claude Code SessionStart hook
# Pulls latest knowledge_framework and regenerates settings.json if template changed.
# Designed to be fast (<2s) and fail silently (no network = no problem).

set -euo pipefail

REPO_DIR="$HOME/ad_hoc/knowledge_framework"
CONFIG_DIR="$REPO_DIR/config/claude-code"
CLAUDE_DIR="$HOME/.claude"
TEMPLATE="$CONFIG_DIR/settings.template.json"
GENERATED="$CLAUDE_DIR/settings.json"
HASH_FILE="$CLAUDE_DIR/.settings_template_hash"
LOCK_DIR="/tmp/kf_sync_lock"

log() { echo "[sync] $*" >&2; }

# --- Lock (mkdir-based, cross-platform) ---
cleanup() { rmdir "$LOCK_DIR" 2>/dev/null || true; }
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    # Check if stale (>60s old)
    if [ -d "$LOCK_DIR" ]; then
        lock_age=$(( $(date +%s) - $(stat -f %m "$LOCK_DIR" 2>/dev/null || stat -c %Y "$LOCK_DIR" 2>/dev/null || echo 0) ))
        if [ "$lock_age" -gt 60 ]; then
            rmdir "$LOCK_DIR" 2>/dev/null || true
            mkdir "$LOCK_DIR" 2>/dev/null || { log "lock contention, skipping"; exit 0; }
        else
            log "another sync running, skipping"
            exit 0
        fi
    fi
fi
trap cleanup EXIT

# --- Git pull (10s timeout, fail silently) ---
if [ -d "$REPO_DIR/.git" ]; then
    if command -v timeout &>/dev/null; then
        timeout 10 git -C "$REPO_DIR" pull --ff-only --quiet 2>/dev/null || true
    else
        # macOS: use perl alarm as timeout fallback
        perl -e 'alarm 10; exec @ARGV' git -C "$REPO_DIR" pull --ff-only --quiet 2>/dev/null || true
    fi
fi

# --- Regenerate settings.json if template changed ---
if [ -f "$TEMPLATE" ]; then
    current_hash=$(shasum -a 256 "$TEMPLATE" 2>/dev/null | cut -d' ' -f1)
    previous_hash=""
    [ -f "$HASH_FILE" ] && previous_hash=$(cat "$HASH_FILE" 2>/dev/null)

    if [ "$current_hash" != "$previous_hash" ]; then
        log "template changed, regenerating settings.json"
        sed "s|{{HOME}}|$HOME|g" "$TEMPLATE" > "$GENERATED"
        echo "$current_hash" > "$HASH_FILE"
    fi
fi

# --- Symlink integrity check (quick) ---
relink_if_broken() {
    local target="$1"
    local link="$2"
    if [ -e "$target" ]; then
        if [ -L "$link" ]; then
            # Symlink exists — check it points to the right place
            local current_target
            current_target=$(readlink "$link" 2>/dev/null || true)
            if [ "$current_target" != "$target" ]; then
                ln -sf "$target" "$link"
                log "relinked $link"
            fi
        elif [ ! -e "$link" ]; then
            # No file at all — create symlink
            ln -sf "$target" "$link"
            log "linked $link"
        fi
        # If it's a regular file (not symlink), leave it alone — user override
    fi
}

relink_if_broken "$CONFIG_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
relink_if_broken "$CONFIG_DIR/statusline-command.sh" "$CLAUDE_DIR/statusline-command.sh"

# Commands
if [ -d "$CONFIG_DIR/commands" ]; then
    mkdir -p "$CLAUDE_DIR/commands"
    for f in "$CONFIG_DIR/commands"/*.md; do
        [ -f "$f" ] && relink_if_broken "$f" "$CLAUDE_DIR/commands/$(basename "$f")"
    done
fi

# Scripts
if [ -d "$CONFIG_DIR/scripts" ]; then
    mkdir -p "$CLAUDE_DIR/scripts"
    for f in "$CONFIG_DIR/scripts"/*; do
        [ -f "$f" ] && relink_if_broken "$f" "$CLAUDE_DIR/scripts/$(basename "$f")"
    done
fi

# Skills — macOS only
if [ "$(uname -s)" = "Darwin" ] && [ -d "$CONFIG_DIR/skills" ]; then
    for skill_dir in "$CONFIG_DIR/skills"/*/; do
        [ -d "$skill_dir" ] || continue
        skill_name=$(basename "$skill_dir")
        target_dir="$CLAUDE_DIR/skills/$skill_name"
        mkdir -p "$target_dir"
        for f in "$skill_dir"*; do
            [ -f "$f" ] && relink_if_broken "$f" "$target_dir/$(basename "$f")"
        done
    done
fi

log "done"
exit 0
