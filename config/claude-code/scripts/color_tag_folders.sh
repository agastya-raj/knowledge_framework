#!/bin/bash
# Color-tag folders in PhD_Work/projects based on last-modified recency
# Uses macOS Finder tags via xattr
#
# Color scheme:
#   Red    = modified in last 24 hours
#   Orange = modified in last week
#   Yellow = modified in last month
#   Green  = modified in last 3 months
#   Blue   = modified in last 6 months
#   Purple = modified in last 12 months
#   Gray   = not modified in over a year

set -euo pipefail

PHD_WORK="$HOME/PhD_Work"
NOW=$(date +%s)

# macOS tag colors as plist values
# Format: tag_name\n color_index
# Color indices: 0=None, 1=Gray, 2=Green, 3=Purple, 4=Blue, 5=Yellow, 6=Red, 7=Orange
set_tag() {
    local path="$1"
    local tag_name="$2"
    local tag_color="$3"

    # Clear existing tags
    xattr -d com.apple.metadata:_kMDItemUserTags "$path" 2>/dev/null || true

    # Set new tag using plist format
    xattr -wx com.apple.metadata:_kMDItemUserTags "$(python3 -c "
import plistlib, sys
data = plistlib.dumps(['$tag_name\n$tag_color'], fmt=plistlib.FMT_BINARY)
sys.stdout.buffer.write(data)
" | xxd -p | tr -d '\n')" "$path"
}

color_by_recency() {
    local path="$1"

    # Get most recent modification time of any file in the directory
    local latest
    latest=$(find "$path" -type f -not -name '.DS_Store' -not -path '*/node_modules/*' -not -path '*/.git/*' -exec stat -f '%m' {} + 2>/dev/null | sort -rn | head -1)

    if [ -z "$latest" ]; then
        set_tag "$path" "Gray" "1"
        echo "  $(basename "$path"): Gray (empty)"
        return
    fi

    local age_seconds=$((NOW - latest))
    local age_days=$((age_seconds / 86400))

    if [ $age_days -lt 1 ]; then
        set_tag "$path" "Red" "6"
        echo "  $(basename "$path"): Red (< 24h)"
    elif [ $age_days -lt 7 ]; then
        set_tag "$path" "Orange" "7"
        echo "  $(basename "$path"): Orange (< 1 week)"
    elif [ $age_days -lt 30 ]; then
        set_tag "$path" "Yellow" "5"
        echo "  $(basename "$path"): Yellow (< 1 month)"
    elif [ $age_days -lt 90 ]; then
        set_tag "$path" "Green" "2"
        echo "  $(basename "$path"): Green (< 3 months)"
    elif [ $age_days -lt 180 ]; then
        set_tag "$path" "Blue" "4"
        echo "  $(basename "$path"): Blue (< 6 months)"
    elif [ $age_days -lt 365 ]; then
        set_tag "$path" "Purple" "3"
        echo "  $(basename "$path"): Purple (< 1 year)"
    else
        set_tag "$path" "Gray" "1"
        echo "  $(basename "$path"): Gray (> 1 year)"
    fi
}

echo "Updating color tags based on recency..."
echo ""

# Tag project folders
echo "=== Projects ==="
for dir in "$PHD_WORK/projects"/*/; do
    [ -d "$dir" ] && color_by_recency "$dir"
done

echo ""
echo "=== Top-level folders ==="
for dir in "$PHD_WORK"/*/; do
    dirname=$(basename "$dir")
    # Skip projects (handled above) and hidden dirs
    [ "$dirname" = "projects" ] && continue
    [[ "$dirname" == .* ]] && continue
    color_by_recency "$dir"
done

echo ""
echo "Tags updated at $(date)"
