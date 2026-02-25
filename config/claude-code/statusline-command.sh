#!/bin/sh
# Claude Code status line — beautified
# Line 1: [weekly bar] [session bar]  [model badge]  [time]  [branch]
# Line 2: [context window bar]

input=$(cat)

# ── Parse JSON ──────────────────────────────────────────────────────────────
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
model_name=$(echo "$input" | jq -r '.model.display_name // ""')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
remaining_pct=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')

# Usage limit fields (may be absent in some versions)
session_used=$(echo "$input" | jq -r '.usage.session.used // empty')
session_limit=$(echo "$input" | jq -r '.usage.session.limit // empty')
weekly_used=$(echo "$input" | jq -r '.usage.weekly.used // empty')
weekly_limit=$(echo "$input" | jq -r '.usage.weekly.limit // empty')

# ── ANSI helpers ─────────────────────────────────────────────────────────────
# Colors
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── Visual bar builder ───────────────────────────────────────────────────────
# make_bar <filled_blocks> <total_blocks> <fill_char> <empty_char> <color>
make_bar() {
    filled=$1
    total=$2
    fill_char=$3
    empty_char=$4
    color=$5

    bar=""
    i=0
    while [ "$i" -lt "$total" ]; do
        if [ "$i" -lt "$filled" ]; then
            bar="${bar}${color}${fill_char}${RESET}"
        else
            bar="${bar}${DIM}${empty_char}${RESET}"
        fi
        i=$((i + 1))
    done
    printf "%s" "$bar"
}

# ── Color for a percentage (low=good for context remaining, high=bad) ────────
# pct_color <pct_used> → prints color code
pct_color_used() {
    pct=$1
    if [ -z "$pct" ]; then printf "%s" "$DIM"; return; fi
    int=$(printf "%.0f" "$pct")
    if   [ "$int" -ge 85 ]; then printf "%s" "$RED"
    elif [ "$int" -ge 60 ]; then printf "%s" "$YELLOW"
    else                         printf "%s" "$GREEN"
    fi
}

# ── Model badge (short form) ─────────────────────────────────────────────────
model_badge=""
if [ -n "$model_name" ]; then
    # Shorten common display names
    badge=$(echo "$model_name" | sed \
        -e 's/Claude //' \
        -e 's/ Sonnet/S/' \
        -e 's/ Haiku/H/' \
        -e 's/ Opus/O/' \
        -e 's/ Latest//' \
        -e 's/ (.*)$//')
    model_badge="${MAGENTA}${BOLD}[${badge}]${RESET}"
fi

# ── Time ─────────────────────────────────────────────────────────────────────
time_str="${DIM}$(date +%H:%M)${RESET}"

# ── Git branch ───────────────────────────────────────────────────────────────
git_branch=""
if [ -n "$cwd" ] && git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git_branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
        || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
fi
branch_str=""
if [ -n "$git_branch" ]; then
    branch_str="${CYAN} ${git_branch}${RESET}"
fi

# ── Usage bars (weekly + session) ────────────────────────────────────────────
BAR_WIDTH=10

# Weekly bar
weekly_str=""
if [ -n "$weekly_used" ] && [ -n "$weekly_limit" ] && [ "$weekly_limit" -gt 0 ] 2>/dev/null; then
    w_pct=$(echo "$weekly_used $weekly_limit" | awk '{printf "%.1f", ($1/$2)*100}')
    w_filled=$(echo "$w_pct $BAR_WIDTH" | awk '{n=int($1/100*$2+0.5); if(n>$2)n=$2; print n}')
    w_color=$(pct_color_used "$w_pct")
    w_bar=$(make_bar "$w_filled" "$BAR_WIDTH" "█" "░" "$w_color")
    weekly_str="${DIM}W:${RESET}${w_bar}${DIM} $(printf "%.0f" "$w_pct")%%${RESET}"
else
    # No data — show placeholder dimmed bar
    w_bar=$(make_bar 0 "$BAR_WIDTH" "█" "░" "$DIM")
    weekly_str="${DIM}W:${RESET}${w_bar}${DIM} -${RESET}"
fi

# Session bar
session_str=""
if [ -n "$session_used" ] && [ -n "$session_limit" ] && [ "$session_limit" -gt 0 ] 2>/dev/null; then
    s_pct=$(echo "$session_used $session_limit" | awk '{printf "%.1f", ($1/$2)*100}')
    s_filled=$(echo "$s_pct $BAR_WIDTH" | awk '{n=int($1/100*$2+0.5); if(n>$2)n=$2; print n}')
    s_color=$(pct_color_used "$s_pct")
    s_bar=$(make_bar "$s_filled" "$BAR_WIDTH" "█" "░" "$s_color")
    session_str="${DIM}S:${RESET}${s_bar}${DIM} $(printf "%.0f" "$s_pct")%%${RESET}"
else
    s_bar=$(make_bar 0 "$BAR_WIDTH" "█" "░" "$DIM")
    session_str="${DIM}S:${RESET}${s_bar}${DIM} -${RESET}"
fi

# ── Context window bar ────────────────────────────────────────────────────────
ctx_line=""
if [ -n "$used_pct" ]; then
    ctx_color=$(pct_color_used "$used_pct")
    ctx_filled=$(echo "$used_pct $BAR_WIDTH" | awk '{n=int($1/100*$2+0.5); if(n>$2)n=$2; print n}')
    ctx_bar=$(make_bar "$ctx_filled" "$BAR_WIDTH" "▓" "░" "$ctx_color")
    ctx_int=$(printf "%.0f" "$used_pct")
    ctx_line="${DIM}ctx:${RESET}${ctx_bar}${DIM} ${ctx_int}% used${RESET}"
else
    ctx_bar=$(make_bar 0 "$BAR_WIDTH" "▓" "░" "$DIM")
    ctx_line="${DIM}ctx:${RESET}${ctx_bar}${DIM} waiting…${RESET}"
fi

# ── Assemble output ───────────────────────────────────────────────────────────
# Line 1: weekly bar  session bar   model   time   branch
printf "%b  %b   %b  %b%b\n" \
    "$weekly_str" "$session_str" "$model_badge" "$time_str" "$branch_str"
# Line 2: context bar
printf "%b" "$ctx_line"
