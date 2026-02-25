#!/bin/sh
# Claude Code status line - mirrors Powerlevel10k rainbow theme elements
# Elements: user@host | dir | git branch | model | context usage

input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
model=$(echo "$input" | jq -r '.model.display_name // ""')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# user@host
user=$(whoami)
host=$(hostname -s)

# Shorten home directory to ~
home="$HOME"
short_dir="${cwd/#$home/\~}"

# Git branch (skip optional locks to avoid blocking)
git_branch=""
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git_branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
        || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
fi

# Context usage indicator
ctx_str=""
if [ -n "$used_pct" ]; then
    used_int=$(printf "%.0f" "$used_pct")
    ctx_str=" | ctx: ${used_int}%"
fi

# Git segment
git_str=""
if [ -n "$git_branch" ]; then
    git_str=" | ${git_branch}"
fi

printf "\033[0;36m%s@%s\033[0m | \033[0;33m%s\033[0m%s | \033[0;35m%s\033[0m%s" \
    "$user" "$host" "$short_dir" "$git_str" "$model" "$ctx_str"
