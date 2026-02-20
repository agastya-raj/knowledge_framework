---
title: "Short, descriptive title — a person scanning a list should immediately know what this entry covers"
type:  # pattern | decision | domain | integration | debug | tool | research
tags: []  # 2-5 lowercase tags for discoverability, e.g. [edfa, transfer-learning, pytorch]
domain:  # optical-networking | software-engineering | ml-ai | devops | research-methods
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidence: low  # low = single experience, medium = validated across 2+ projects, high = well-established
complexity: medium  # low = quick fix or simple pattern, medium = multi-step or nuanced, high = architectural or cross-system
related: []  # slugs of other entries, e.g. [edfa-gain-modeling, docker-compose-patterns]
---

# {title}

## Problem

Describe the specific problem this entry solves. Write it as a situation someone would recognise:
what are they trying to do, and what is blocking them or making it hard? Be concrete enough that
an agent can match this entry to a future task by comparing problem descriptions.

Example: "When deploying a multi-container optical monitoring stack, the Grafana container cannot
reach the SNMP exporter because Docker Compose service names don't resolve across custom networks."

## Context

State the environment, constraints, and assumptions that shaped the approach:
- What project or system was this discovered in?
- What tools, versions, or platforms were involved?
- Were there hard constraints (latency, memory, compatibility, deadline)?
- What did the operator/researcher already know or assume going in?

This section prevents someone from blindly applying advice that only works under specific conditions.

## Approach

Explain the architecture, pattern, or method that solved the problem. Walk through it
step by step at a conceptual level. Focus on the *structure* of the solution, not raw
code. Use code snippets only where they clarify a non-obvious interface or configuration.

If the approach has distinct phases (e.g., data prep, model training, deployment), use
sub-headings or a numbered list to make the flow scannable.

## Key Decisions

Document the forks in the road. For each significant choice:
- What was the decision?
- What alternatives were considered?
- Why was this option chosen over the others?
- Under what conditions would a different choice be better?

This is the section that saves future agents from re-evaluating the same tradeoffs.

## Pitfalls & Gotchas

List the things that went wrong, were surprisingly hard, or wasted time. For each:
- What happened?
- Why was it unexpected?
- How was it resolved?

Be specific. "Docker networking is tricky" is not useful. "Docker Compose v2 silently
ignores `network_mode: host` on macOS — containers get bridge networking instead, which
breaks UDP multicast discovery" is useful.

## Recipe

Concrete, ordered steps an agent could follow to rebuild this from scratch in a new project.
Write these as if the reader has general technical competence but zero context about this
specific solution. Each step should be independently verifiable.

1. Step one — what to do and what the expected outcome is
2. Step two — include exact commands, file paths, or config values where precision matters
3. Step three — note any ordering dependencies ("this must happen before X")
4. ...

If a step has a common failure mode, note it inline: "If you see error X, it means Y —
fix by doing Z."

## Verification

How to confirm the solution is working correctly. Provide concrete checks:
- What command to run, what output to expect
- What behaviour to observe in the UI or logs
- What metric or test to check
- What a subtle failure looks like (it *seems* to work but is actually broken when...)

A good verification section lets someone distinguish "working" from "appears to work."
