---
title: "Multi-Agent Research Pipeline for Large Dataset Analysis"
type: pattern
tags: [multi-agent, swarm, research, large-dataset, iterative-analysis, exploration-exploitation]
domain: research-methods
created: 2026-02-20
updated: 2026-02-20
confidence: medium
complexity: high
related: [agent_agnostic_knowledge_management]
---

# Multi-Agent Research Pipeline for Large Dataset Analysis

## Problem

You have a large dataset (hundreds of GBs) that needs exploratory analysis — finding patterns, anomalies, or events — but the dataset is too large for a single agent pass to be thorough, and you don't know exactly what you're looking for yet. Manual iteration is too slow. You need systematic exploration that compounds discoveries across iterations.

## Context

Developed for analyzing ~600 GB of month-long SOP (State of Polarization) telemetry data from submarine cable monitoring. The data was too large to re-read on every iteration, and the analysis required both broad exploration and deep investigation of specific anomalies.

Applicable whenever you have:
- A dataset too large for single-pass analysis
- Open-ended research questions (not a known target)
- Need for both exploration (new patterns) and exploitation (deepening known leads)

## Approach

**Two-phase architecture: Heavy Lift + Iterative Thinking**

**Phase 1 — Comprehensive Base Pass (run once)**
A capable agent (e.g., Codex) does one thorough pass over the full dataset:
- Compute summary statistics, distributions, segmentation
- Generate figures and artifacts into a structured output folder
- Produce a data profile (missingness, time ranges, channel counts, anomalies)

This creates a **stable evidence base** so later agents never need to re-read raw data.

**Phase 2 — Iterative Agent Swarm (run N times)**
Multiple lighter agents iterate over the artifacts:
- Each iteration reads the previous iteration's findings + base artifacts
- Each agent writes findings to a per-iteration folder (`iteration_01/`, `iteration_02/`, ...)
- An exploration-exploitation balance controls agent behavior:
  - **Exploitation agents** (~70%): deepen the most promising leads from prior iterations
  - **Exploration agents** (~30%): intentionally try to break the current narrative, look for overlooked patterns
  - Implement this as an epsilon-greedy probability flag in the agent prompt

**Structured Output Per Iteration:**
Every iteration must produce:
- Top 3 candidate events (with timestamps, severity, confidence, reasoning)
- Top 3 features/patterns discovered (burstiness, periodicity, drift, etc.)
- Next measurement to run (what would reduce uncertainty the most)
- Running narrative summary

**Living Event Ledger:**
A shared CSV/JSON file that every agent appends to:
- One row per candidate event: start/end, duration, severity, channels affected, supporting evidence, which iteration proposed it
- Enables deduplication and ranking across the full swarm

## Key Decisions

**Per-iteration folders over shared mutable state**: Makes the process auditable. You can diff iterations, trace provenance of ideas, and prune bad branches without losing history. Essential for writing methods sections in papers.

**Epsilon-greedy over fully independent agents**: Pure independence leads to redundant discovery. Pure collaboration leads to groupthink. The probability flag gives controlled diversity.

**Structured output alongside free-form narrative**: The structured section (top events, top features, next measurement) enables aggregation across iterations. The narrative captures nuance that structured data misses.

## Pitfalls & Gotchas

**Agent groupthink is the #1 failure mode.** Even with exploration probability, agents anchor on early findings because the previous folder becomes "the truth." Mitigations:
- Force a **red team agent** every N iterations whose only job is to falsify the top hypotheses
- Have exploration agents write first-pass conclusions BEFORE reading prior iteration results, then reconcile

**Artifact bloat and "analysis tourism."** By iteration 50, you'll have hundreds of plots that don't cash out into actionable findings. The structured output format (top 3 events, top 3 patterns) is essential to prevent this.

**Circularity between base artifacts and discoveries.** If the Phase 1 output already includes detection heuristics, later agents will rediscover and rephrase them. Label base artifacts clearly as "raw summaries" vs. "derived detections" so agents can distinguish genuine new findings.

**Running summary drift.** If each iteration rewrites the running summary from scratch, good findings from early iterations can be silently dropped. Use an append-and-consolidate approach: each iteration appends, and a consolidation step periodically merges.

## Recipe

1. **Set up the folder structure:**
   ```
   analysis/
   ├── base_artifacts/        # Phase 1 output (read-only after creation)
   ├── iterations/
   │   ├── 01/
   │   ├── 02/
   │   └── ...
   ├── event_ledger.csv       # Living shared ledger
   └── running_summary.md     # Consolidated findings
   ```

2. **Run Phase 1** with a capable agent. Prompt should include:
   - Read the full dataset (or sample strategy for very large data)
   - Compute distributions, time-series segmentation, missing data analysis
   - Output all figures and stats to `base_artifacts/`
   - Generate an initial data profile document

3. **Create the iteration prompt template** with:
   - Read `base_artifacts/` and previous iteration folder
   - Exploration/exploitation flag (set per agent)
   - Required structured output format
   - Instruction to append to `event_ledger.csv`

4. **Run iterations** — batch of 5-10 at a time, review, adjust prompts, repeat
   - After every 10 iterations, run a consolidation pass
   - After every 5 iterations, run a red team agent

5. **Aggregate results** from event ledger:
   - Deduplicate events by timestamp proximity
   - Rank by frequency of independent discovery, severity, cross-sensor consistency
   - Produce final ranked event catalog

## Verification

- The event ledger grows with each iteration (no stagnation)
- Later iterations find events not in early iterations (exploration is working)
- Red team agents occasionally reject hypotheses (they're not rubber-stamping)
- The final event catalog contains events with multiple independent confirmations
- You can trace any finding back to the iteration that first proposed it (provenance)
