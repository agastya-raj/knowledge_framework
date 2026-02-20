---
title: "Short, specific title — e.g. 'Fix SNMP timeout on FSP3000 GNE queries' not 'SNMP fix'"
type:  # pattern | decision | domain | integration | debug | tool | research
tags: []  # 2-5 lowercase tags, e.g. [snmp, fsp3000, timeout]
domain:  # optical-networking | software-engineering | ml-ai | devops | research-methods
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidence: low  # low = single experience, medium = validated across 2+ projects, high = well-established
complexity: low  # low = quick fix or simple pattern, medium = multi-step or nuanced, high = architectural
related: []  # slugs of other entries, e.g. [snmp-polling-architecture]
---

# {title}

## Problem

One or two sentences: what were you trying to do, and what went wrong or was non-obvious?

Example: "Python `subprocess.run()` with `capture_output=True` silently swallows stderr
when the child process spawns its own subprocesses, making it impossible to debug failures
in a multi-stage build script."

## Solution

The fix, pattern, or approach — concise but complete enough that someone could apply it
without additional research. Include the exact command, config change, code pattern, or
workaround. Use a code block if it helps.

Example:
```python
result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
```

## Why It Works

One to three sentences explaining the underlying cause. This turns a memorised fix into
transferable understanding. If someone hits a *similar* but not identical problem, this
section helps them reason about whether the same fix applies.

Example: "`capture_output=True` creates separate pipes for stdout and stderr. Grandchild
processes inherit these pipes but the parent only waits on the direct child's EOF, so
grandchild writes to stderr can be lost. Merging stderr into stdout with `STDOUT` keeps
everything in one pipe that is fully drained."

## Watch Out For

Caveats, edge cases, or conditions where this solution breaks or needs adjustment.
Things like: version-specific behaviour, platform differences, subtle interactions
with other settings, or signs that the real problem is something else entirely.

Example: "This merges stdout and stderr into a single stream, so you lose the ability
to distinguish between them. If you need them separate, use `Popen` with explicit
pipe management and `communicate()` instead."
