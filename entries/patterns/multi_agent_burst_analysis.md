---
title: "Multi-Agent Burst Analysis for Pre-Implementation Planning"
type: pattern
tags: [multi-agent, burst-analysis, parallel-agents, pre-implementation, orchestration, approval-gate]
domain: software-engineering
created: 2026-02-24
updated: 2026-02-24
confidence: medium
complexity: medium
related: [ai_worker_orchestration_worktree_isolation, reviewer_gate_escalation]
---

# Multi-Agent Burst Analysis for Pre-Implementation Planning

## Problem

You have an AI-assisted development pipeline where agents implement tasks autonomously. Without upfront analysis, agents dive straight into code, leading to poorly planned architectures, missed edge cases, and wasted implementation cycles when the approach turns out to be wrong. You need a structured "think before you act" phase that runs multiple specialist analyses in parallel, produces a unified planning document, and blocks implementation until a human has reviewed and approved the plan.

This pattern is relevant whenever you have autonomous agents that can commit code changes and you want a quality gate that catches architectural flaws, risks, and missing test coverage before any code is written.

## Context

Developed in a consultancy gateway project -- a daemon-based system that orchestrates AI workers to implement tasks from a backlog. The system uses TypeScript, SQLite for persistence, and an LLM gateway service (`OpenCodeService`) for agent interactions. The burst analysis phase was inserted between task intake and worker assignment.

Key constraints that shaped the design:
- **Agents act autonomously** once assigned a task, so catching bad plans after implementation is expensive
- **Multiple analysis dimensions** (architecture, task decomposition, risk, failure prediction, documentation) are independent of each other and can run concurrently
- **Human review is mandatory** -- the system serves a consultancy context where a human must sign off on the approach before resources are committed
- **LLM calls are expensive and slow** (15-minute timeout per agent), so parallel execution is essential for acceptable latency

## Approach

The pattern has four layers: orchestration, controller, agent, and persistence.

### 1. Orchestration Layer (Daemon Tick Loop)

A daemon process runs a periodic tick loop. Within each tick, it checks for tasks in `BURST_PENDING` status, hands them to the burst controller, and manages state transitions. The burst tick runs as one phase of a larger pipeline tick (after intake, before worker execution), so bursts are processed alongside other daemon responsibilities.

The tick processes up to a configurable batch size (e.g., 10 tasks) per cycle, preventing a flood of bursts from monopolizing the daemon.

### 2. Controller Layer (Burst Lifecycle)

The burst controller owns the full lifecycle of a single burst:

1. Creates a burst session record in the database (audit trail)
2. Fires all specialist agents in parallel using `Promise.all`
3. Stores each agent's structured output individually to the database
4. Computes summary statistics from agent outputs (total risks, high-priority task count, weighted complexity score)
5. Assembles a markdown artifact combining all agent outputs into a single planning document
6. Writes the artifact to a well-known path (e.g., `.sisyphus/bursts/{sessionId}/consultancy-burst.md`)

All agents are constructor-injected into the controller via dependency injection, instantiated at application startup. This makes the agent roster explicit and testable.

### 3. Agent Layer (Specialist Analysts)

Five specialist agents run in parallel, each analyzing the task from a different perspective. All agents share an identical interface:

- **Constructor** accepts the LLM gateway service
- **`run(task, context)`** creates an isolated LLM session, sends a role-specific prompt, and returns Zod-validated structured JSON
- **`buildPrompt()`** constructs the role-specific analysis prompt

The five specialist roles:

| Agent | Focus | Key Output Fields |
|-------|-------|-------------------|
| **Architect** | High-level structure | Architecture sketch, key components, interfaces, dependencies, tradeoffs (option/pros/cons) |
| **Program Manager** | Task decomposition | Subtasks with priority/complexity, sequencing order, parallelizable groups |
| **Reviewer** | Pre-implementation risk | Risks with severity/mitigation, security concerns, performance concerns |
| **Debugger** | Failure prediction | Failure cases with probability/detection/recovery, edge cases, test suggestions |
| **Doc Gardener** | Documentation planning | Documentation skeleton (paths/purposes/sections), API docs needed, runbook updates |

Each agent's output is defined as a Zod schema, converted to JSON Schema via a utility (`zodToJsonSchema`), and passed to the LLM as a structured output format constraint. This ensures responses are machine-parseable without fragile text extraction.

### 4. Persistence Layer

Two database tables (SQLite in the reference implementation):

- **`burst_sessions`** -- one row per burst execution: session ID, task ID, status, timestamps, approval metadata (who approved, when)
- **`burst_agent_outputs`** -- one row per agent per burst: agent type, structured JSON output, duration, error field. Foreign key to burst session.

Agent outputs are stored as serialized JSON text. Reading back always wraps `JSON.parse` in error handling because corrupted rows must not crash the read path.

### 5. Approval Gate (State Machine)

The task status state machine enforces human review:

```
BURST_PENDING -> BURST_RUNNING -> BURST_COMPLETED -> BURST_APPROVED -> NEXT
                               \-> FAILED
```

- **BURST_PENDING**: Task is queued for analysis (set by CLI or intake logic)
- **BURST_RUNNING**: Daemon has picked up the task and agents are executing
- **BURST_COMPLETED**: All agents finished; artifact is ready for human review. Task stays here indefinitely until explicitly approved.
- **BURST_APPROVED**: Human has reviewed and approved via CLI command; records `approved_at` and `approved_by` for audit
- **NEXT**: Daemon transitions approved tasks to the next pipeline phase (worker assignment)

The critical property: there is no automatic transition from `BURST_COMPLETED` to `NEXT`. The approval is an explicit human action, not a timeout or auto-advance.

### 6. Artifact Assembly

After all agents complete, the controller assembles their outputs into a single structured markdown document with sections for each agent's analysis, plus a summary block with computed metrics:

- **Total risks** (count from reviewer)
- **High-priority tasks** (count from program manager where priority is "high")
- **Estimated complexity** (weighted average of program manager task complexities: small=1, medium=2, large=3; thresholds at >1.3 for medium, >2.0 for high)

This artifact is what the human reviews before approving. It lives at a predictable file path so it can be opened, diffed, or version-controlled.

## Key Decisions

### Read-only analysis, not code generation

Burst agents produce analysis artifacts only -- no code changes, no file modifications outside the artifact. This was chosen over a "draft implementation" approach because:
- A failed draft implementation leaves behind partial code that must be cleaned up
- Read-only analysis can be freely discarded or re-run with no side effects
- The human reviewer evaluates a plan, not a diff, which is faster to review
- **When to choose differently**: If you have very high confidence in agent code quality and want to reduce total pipeline time, a draft-implementation approach with review-before-merge could work, but it requires robust rollback mechanisms

### `Promise.all` (all-or-nothing) over `Promise.allSettled` (partial success)

If any single agent fails, the entire burst fails. This was deliberate:
- A partial analysis (e.g., architecture without risk assessment) could lead to worse outcomes than no analysis, because it gives false confidence
- It keeps the controller simple -- no logic for "which agents succeeded, is the result useful?"
- **When to choose differently**: If one agent is significantly less reliable than others (e.g., the doc gardener calls an external API), use `Promise.allSettled` and mark the artifact with which sections are missing. This requires the human reviewer to understand which gaps matter.

### Explicit `BURST_APPROVED` state rather than direct `COMPLETED -> NEXT`

The approval step has its own state rather than a flag on the completed state. This was learned the hard way (see Pitfalls). The dedicated state provides:
- Clean querying: "show me all bursts awaiting review" is a single status filter
- Audit trail: approval metadata (who, when) lives on the state transition, not a side-channel
- Pipeline visibility: the daemon can independently process "run pending bursts" and "advance approved bursts" as separate tick phases

### Homogeneous agent interface, heterogeneous prompts

All agents share the exact same code structure (Zod schema, constructor, run method, buildPrompt). Only the schema shape and prompt text differ. This was chosen over a plugin system or agent registry because:
- Adding a new agent is a copy-paste-modify operation with obvious steps
- No dynamic dispatch or registration complexity
- Type safety is preserved end-to-end (each agent has its own typed output)
- **When to choose differently**: If you need dynamic agent composition (e.g., different burst configurations per task type), a registry pattern with a common base class would be more appropriate

## Pitfalls & Gotchas

### 1. Skeleton controllers that pass tests but do nothing

The first implementation of the burst controller had the method signatures, types, and test stubs in place but the `runBurst()` body did not actually call the agents, persist outputs, or assemble the artifact. It passed unit tests because the tests only checked that the method existed and returned a promise. **Detection**: End-to-end integration test that verifies agent outputs appear in the database and the artifact file exists on disk after a burst. **Lesson**: For orchestration controllers, write at least one integration test that checks the full execution path before marking complete.

### 2. Missing intermediate state for human approval gates

The original state machine jumped directly from `BURST_COMPLETED` to `NEXT` when the approval CLI command was run, skipping the `BURST_APPROVED` state. This caused two problems: (a) the daemon could not distinguish "approved but not yet processed" from "still awaiting review," and (b) the audit trail lost the approval event. **Fix**: Add a dedicated `BURST_APPROVED` state between completion and the next phase. **General rule**: Any human-in-the-loop gate in a state machine needs its own explicit state, not just a transition that bypasses intermediate tracking.

### 3. Unsafe JSON deserialization from persistence

Agent outputs stored as JSON text in SQLite were read back with bare `JSON.parse()` -- no try/catch. A single corrupted row (truncated write, encoding issue) would crash the entire read path, preventing display of all agents' outputs, not just the corrupted one. **Fix**: Wrap every `JSON.parse` from persistence in try/catch and degrade gracefully (populate an error field, return partial results). This applies universally: never trust JSON you wrote to storage, because the write or storage layer can corrupt it.

### 4. `Promise.all` short-circuits on first rejection, losing in-flight results

`Promise.all` rejects as soon as any single promise rejects. This means if Agent 2 fails at t=5s while Agents 3-5 are still running, those agents' results are never awaited and never persisted, even though they may complete successfully. The in-flight work is silently discarded. **If you need partial results**: Switch to `Promise.allSettled`, iterate results, persist succeeded ones, and decide whether the partial artifact is useful. **Current mitigation**: Each agent has internal error handling, so rejections should be rare -- but LLM timeouts (15-minute default) are a realistic failure mode.

### 5. Shared context object passes empty codebase content

The `burstContext` object shared across all agents includes a `existingCode` field, but in the controller it is always initialized to an empty string. Agents that reference `context.existingCode` for their analysis are working from the task description alone, with no codebase awareness. **Impact**: Analysis quality degrades significantly for modification tasks (vs. greenfield tasks). **Fix**: Populate `existingCode` with relevant file contents from the worktree before launching the burst. Use heuristics (files mentioned in the task, recently modified files, entry points) to select a representative subset within token limits.

### 6. Per-agent timing is not tracked individually

The `durationMs` recorded for each agent output is the total `Promise.all` wall-clock time, not the individual agent's execution time. The same duration variable is written to all five agent output rows. **Impact**: You cannot identify which agent is the bottleneck when bursts are slow. **Fix**: Wrap each agent call in its own timing measurement before passing to `Promise.all`. For example, wrap each promise in a helper that records `Date.now()` before and after resolution and attaches timing to the result.

## Recipe

1. **Define the agent interface.** Create a base pattern (or abstract class/interface) with:
   - Constructor accepting the LLM service
   - `run(task, context): Promise<AgentOutput>` method
   - Output type defined as a Zod schema (or equivalent validation schema)
   - `buildPrompt(task, context): string` method for role-specific prompt construction

2. **Implement each specialist agent.** For each analysis dimension you need, create an agent file following the interface. Start with these five (architect, program manager, reviewer, debugger, doc planner) and adjust based on your domain. Each agent:
   - Creates its own isolated LLM session (do not share sessions across agents)
   - Sends its prompt with structured output format constraint (Zod-to-JSON-Schema conversion)
   - Returns validated, typed output

3. **Build the burst controller.** The controller accepts all agents via constructor injection and implements `runBurst(taskId)`:
   - Create a session record in the database
   - Build the shared context object (`worktreePath`, `baseBranch`, `existingCode` -- populate `existingCode` with relevant file contents, not an empty string)
   - Fire all agents with `Promise.all` (or `Promise.allSettled` if you need partial success)
   - Persist each agent's output individually to the database with per-agent timing
   - Compute summary statistics from agent outputs
   - Assemble the markdown artifact and write to a well-known path
   - If using `Promise.all`, wrap the entire block in try/catch and transition to FAILED status on error

4. **Set up the persistence layer.** Create two tables:
   - `burst_sessions`: id, task_id, status, created_at, completed_at, approved_at, approved_by
   - `burst_agent_outputs`: id, session_id (FK), agent_type, output_json (text), duration_ms, error (nullable)
   - Always use try/catch when parsing `output_json` back from the database

5. **Implement the state machine.** Add these task statuses: `BURST_PENDING`, `BURST_RUNNING`, `BURST_COMPLETED`, `BURST_APPROVED`. Wire the transitions:
   - Daemon tick: `BURST_PENDING` -> `BURST_RUNNING` (start burst) -> `BURST_COMPLETED` or `FAILED`
   - Human CLI command: `BURST_COMPLETED` -> `BURST_APPROVED` (records approval metadata)
   - Daemon tick: `BURST_APPROVED` -> next pipeline phase

6. **Wire into the daemon tick loop.** Add a `tickBursts()` phase to the daemon's tick cycle that:
   - Queries for tasks in `BURST_PENDING` (batch limit, e.g., 10)
   - Runs bursts for each, transitioning states
   - Queries for tasks in `BURST_APPROVED`
   - Advances approved tasks to the next pipeline phase

7. **Build CLI commands** for human interaction:
   - `run-burst --task <id>`: Queue a task for burst analysis
   - `show-burst --task <id>`: Display burst session details and per-agent outputs
   - `approve-burst --task <id>`: Approve a completed burst (must validate that status is `BURST_COMPLETED` before allowing)

8. **Wire dependency injection at startup.** In the application entry point, instantiate all agents with the shared LLM service, create the controller with all agents + database store + workspace root, and inject the controller into the daemon.

## Verification

- **Agents execute in parallel**: Check that total burst wall-clock time is close to the duration of the slowest single agent, not the sum of all agents. If burst time roughly equals 5x a single agent, the parallelism is broken (likely awaiting sequentially).

- **All five agent outputs are persisted**: Query `burst_agent_outputs` for a completed session and confirm exactly one row per agent type. Missing rows indicate an agent failed silently or was never invoked.

- **Artifact file is written and contains all sections**: After burst completion, verify the markdown file exists at the expected path and contains non-empty sections for architecture, task breakdown, risk assessment, failure prediction, and documentation plan.

- **Approval gate blocks implementation**: Set a task to `BURST_COMPLETED` and verify the daemon does NOT advance it to the next phase on subsequent ticks. Only an explicit `approve-burst` command should unblock it.

- **Approval metadata is recorded**: After running `approve-burst`, check that the session record has `approved_at` (timestamp) and `approved_by` (user identifier) populated.

- **Failed bursts do not produce artifacts**: Trigger a burst where one agent will fail (e.g., invalid task data). Verify the task transitions to `FAILED`, no artifact file is written, and the system does not crash. Check that any successfully-completed agent outputs are still individually queryable from the database (if using `Promise.allSettled`) or that the failure is cleanly logged (if using `Promise.all`).

- **Subtle failure to watch for**: The burst "succeeds" but `existingCode` in the context is empty, so all agent analyses are based solely on the task description. The artifact will look plausible but miss codebase-specific risks and dependencies. Verify by checking that the architect agent's output references actual files or modules from the project, not just generic patterns.
