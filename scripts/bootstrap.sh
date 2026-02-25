#!/bin/bash
# bootstrap.sh — Set up Claude Code config synced via knowledge_framework
#
# Usage:
#   bootstrap.sh --import      Copy ~/.claude/ config INTO the repo (first machine)
#   bootstrap.sh               Full setup: backup, generate settings.json, symlink
#   bootstrap.sh --relink-only Just fix broken symlinks (called by sync_config.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="$REPO_DIR/config/claude-code"
CLAUDE_DIR="$HOME/.claude"
TEMPLATE="$CONFIG_DIR/settings.template.json"
PLATFORM="$(uname -s)"
DATE=$(date +%Y%m%d)

log()  { echo "[bootstrap] $*"; }
warn() { echo "[bootstrap] WARN: $*" >&2; }
die()  { echo "[bootstrap] ERROR: $*" >&2; exit 1; }

# ── Helpers ──────────────────────────────────────────────────────────────

safe_symlink() {
    local target="$1"
    local link="$2"

    [ -e "$target" ] || { warn "target missing: $target"; return 1; }

    if [ -L "$link" ]; then
        local current
        current=$(readlink "$link")
        if [ "$current" = "$target" ]; then
            return 0  # already correct
        fi
        rm "$link"
    elif [ -e "$link" ]; then
        # Regular file — back it up
        local backup_dir="$CLAUDE_DIR/backups/pre_bootstrap_$DATE"
        mkdir -p "$backup_dir"
        local rel
        rel=$(python3 -c "import os; print(os.path.relpath('$link', '$CLAUDE_DIR'))")
        mkdir -p "$backup_dir/$(dirname "$rel")"
        mv "$link" "$backup_dir/$rel"
        log "backed up $(basename "$link") → backups/pre_bootstrap_$DATE/$rel"
    fi

    mkdir -p "$(dirname "$link")"
    ln -s "$target" "$link"
    log "linked $(basename "$link")"
}

# ── Mode: --import ───────────────────────────────────────────────────────

do_import() {
    log "Importing ~/.claude/ config into repo..."

    mkdir -p "$CONFIG_DIR"/{commands,scripts,skills/daily-triage}

    # CLAUDE.md
    [ -f "$CLAUDE_DIR/CLAUDE.md" ] && cp "$CLAUDE_DIR/CLAUDE.md" "$CONFIG_DIR/CLAUDE.md" && log "imported CLAUDE.md"

    # statusline
    [ -f "$CLAUDE_DIR/statusline-command.sh" ] && cp "$CLAUDE_DIR/statusline-command.sh" "$CONFIG_DIR/statusline-command.sh" && log "imported statusline-command.sh"

    # commands
    for f in "$CLAUDE_DIR/commands"/*.md; do
        [ -f "$f" ] && cp "$f" "$CONFIG_DIR/commands/" && log "imported commands/$(basename "$f")"
    done

    # scripts (only the ones we want to sync)
    for f in knowledge_capture_hook.sh color_tag_folders.sh fast_tag.py apply_tags_recursive.py; do
        [ -f "$CLAUDE_DIR/scripts/$f" ] && cp "$CLAUDE_DIR/scripts/$f" "$CONFIG_DIR/scripts/$f" && log "imported scripts/$f"
    done

    # skills
    [ -f "$CLAUDE_DIR/skills/daily-triage/SKILL.md" ] && cp "$CLAUDE_DIR/skills/daily-triage/SKILL.md" "$CONFIG_DIR/skills/daily-triage/SKILL.md" && log "imported skills/daily-triage/SKILL.md"

    # Generate template from current settings.json
    if [ -f "$CLAUDE_DIR/settings.json" ]; then
        sed "s|$HOME|{{HOME}}|g" "$CLAUDE_DIR/settings.json" > "$TEMPLATE"
        log "generated settings.template.json from current settings.json"
    fi

    log "Import complete. Review config/claude-code/ then run: bootstrap.sh (no flags) to activate."
}

# ── Mode: --relink-only ─────────────────────────────────────────────────

do_relink() {
    log "Checking symlink integrity..."

    safe_symlink "$CONFIG_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
    safe_symlink "$CONFIG_DIR/statusline-command.sh" "$CLAUDE_DIR/statusline-command.sh"

    # Commands
    for f in "$CONFIG_DIR/commands"/*.md; do
        [ -f "$f" ] && safe_symlink "$f" "$CLAUDE_DIR/commands/$(basename "$f")"
    done

    # Scripts
    for f in "$CONFIG_DIR/scripts"/*; do
        [ -f "$f" ] && safe_symlink "$f" "$CLAUDE_DIR/scripts/$(basename "$f")"
    done

    # Skills (macOS only)
    if [ "$PLATFORM" = "Darwin" ]; then
        for skill_dir in "$CONFIG_DIR/skills"/*/; do
            [ -d "$skill_dir" ] || continue
            skill_name=$(basename "$skill_dir")
            for f in "$skill_dir"*; do
                [ -f "$f" ] && safe_symlink "$f" "$CLAUDE_DIR/skills/$skill_name/$(basename "$f")"
            done
        done
    fi

    log "Relink complete."
}

# ── Mode: full setup (default) ──────────────────────────────────────────

do_setup() {
    log "Full setup — platform: $PLATFORM, home: $HOME"

    # Preflight
    [ -d "$CONFIG_DIR" ] || die "config/claude-code/ not found in repo. Run --import first."
    [ -f "$TEMPLATE" ] || die "settings.template.json not found. Run --import first."
    mkdir -p "$CLAUDE_DIR"

    # 1. Generate settings.json from template
    log "Generating settings.json..."
    if [ -f "$CLAUDE_DIR/settings.json" ] && [ ! -L "$CLAUDE_DIR/settings.json" ]; then
        # Back up existing (only if it's a real file, not already a generated one)
        local backup_dir="$CLAUDE_DIR/backups/pre_bootstrap_$DATE"
        mkdir -p "$backup_dir"
        cp "$CLAUDE_DIR/settings.json" "$backup_dir/settings.json"
        log "backed up settings.json"
    fi
    sed "s|{{HOME}}|$HOME|g" "$TEMPLATE" > "$CLAUDE_DIR/settings.json"
    log "generated settings.json"

    # Store template hash so sync_config.sh knows the baseline
    shasum -a 256 "$TEMPLATE" | cut -d' ' -f1 > "$CLAUDE_DIR/.settings_template_hash"

    # 2. Preserve settings.local.json (never touch it)
    if [ -f "$CLAUDE_DIR/settings.local.json" ]; then
        log "settings.local.json preserved (not touched)"
    else
        log "no settings.local.json found (that's fine)"
    fi

    # 3. Create symlinks
    do_relink

    # 4. Make scripts executable
    chmod +x "$CONFIG_DIR/scripts"/*.sh 2>/dev/null || true
    chmod +x "$CONFIG_DIR/statusline-command.sh" 2>/dev/null || true
    chmod +x "$REPO_DIR/scripts/sync_config.sh" 2>/dev/null || true
    chmod +x "$REPO_DIR/scripts/bootstrap.sh" 2>/dev/null || true

    log ""
    log "Setup complete! Verify with:"
    log "  ls -la ~/.claude/CLAUDE.md"
    log "  cat ~/.claude/settings.json"
    log "  ls -la ~/.claude/commands/"
    log "  ls -la ~/.claude/scripts/"
    log ""
    log "Start a new Claude Code session to trigger the SessionStart sync hook."
}

# ── Main ─────────────────────────────────────────────────────────────────

case "${1:-}" in
    --import)
        do_import
        ;;
    --relink-only)
        do_relink
        ;;
    --help|-h)
        echo "Usage: bootstrap.sh [--import | --relink-only]"
        echo ""
        echo "  (no args)      Full setup: backup, generate settings.json, create symlinks"
        echo "  --import        Copy ~/.claude/ config into the repo (first machine only)"
        echo "  --relink-only   Fix broken symlinks only"
        ;;
    "")
        do_setup
        ;;
    *)
        die "Unknown option: $1 (try --help)"
        ;;
esac
