#!/bin/sh
# Claude Code status line
# ✦ user@host  branch  [model]  Ctxt [bar]

input=$(cat)

# ── Parse JSON ───────────────────────────────────────────────────────────────
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
model_name=$(echo "$input" | jq -r '.model.display_name // ""')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# ── ANSI ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── Bar builder ──────────────────────────────────────────────────────────────
make_bar() {
    filled=$1; total=$2; fill=$3; empty=$4; color=$5
    bar=""; i=0
    while [ "$i" -lt "$total" ]; do
        if [ "$i" -lt "$filled" ]; then
            bar="${bar}${color}${fill}${RESET}"
        else
            bar="${bar}${DIM}${empty}${RESET}"
        fi
        i=$((i + 1))
    done
    printf "%s" "$bar"
}

pct_color() {
    pct=$1
    if [ -z "$pct" ]; then printf "%s" "$DIM"; return; fi
    int=$(printf "%.0f" "$pct")
    if   [ "$int" -ge 85 ]; then printf "%s" "$RED"
    elif [ "$int" -ge 60 ]; then printf "%s" "$YELLOW"
    else                         printf "%s" "$GREEN"
    fi
}

BAR_WIDTH=12

# ── user@host ────────────────────────────────────────────────────────────────
user_host="${CYAN}${BOLD}$(whoami)${RESET}${DIM}@${RESET}${CYAN}$(hostname -s)${RESET}"

# ── Git branch ───────────────────────────────────────────────────────────────
branch_str=""
if [ -n "$cwd" ] && git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git_branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
        || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
    if [ -n "$git_branch" ]; then
        branch_str=" ${GREEN} ${git_branch}${RESET}"
    fi
fi

# ── Model badge ──────────────────────────────────────────────────────────────
model_badge=""
if [ -n "$model_name" ]; then
    model_badge=" ${MAGENTA}${BOLD}[${model_name}]${RESET}"
fi

# ── Context window bar ──────────────────────────────────────────────────────
if [ -n "$used_pct" ]; then
    c_color=$(pct_color "$used_pct")
    c_filled=$(echo "$used_pct $BAR_WIDTH" | awk '{n=int($1/100*$2+0.5); if(n>$2)n=$2; print n}')
    c_bar=$(make_bar "$c_filled" "$BAR_WIDTH" "█" "░" "$c_color")
    c_int=$(printf "%.0f" "$used_pct")
    ctx_str=" ${DIM}Ctxt${RESET} ${c_bar} ${DIM}${c_int}%${RESET}"
else
    c_bar=$(make_bar 0 "$BAR_WIDTH" "█" "░" "$DIM")
    ctx_str=" ${DIM}Ctxt${RESET} ${c_bar}"
fi

# ── Output (single line) ─────────────────────────────────────────────────────
# ✦ user@host  branch  [model]  Ctxt [bar]
printf "${MAGENTA}${BOLD}\342\234\246${RESET} %b%b%b%b" \
    "$user_host" "$branch_str" "$model_badge" "$ctx_str"
