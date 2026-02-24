---
title: "Autonomous AI Worker Orchestration with Git Worktree Isolation"
type: pattern
tags: [ai-agents, worker-orchestration, git-worktree, process-isolation, task-management, lease-based-recovery]
domain: software-engineering
created: 2026-02-24
updated: 2026-02-24
confidence: medium
complexity: high
related: [multi_agent_burst_analysis, reviewer_gate_escalation, security_hardening_ai_agent_systems, opencode_sdk_backend_abstraction]
---

# Autonomous AI Worker Orchestration with Git Worktree Isolation

## Problem

You want to build a control-plane daemon that autonomously dispatches AI coding agents to work on software development tasks -- from intake through code review and merge -- without human intervention for routine work. The core challenges are:

- **Isolation**: multiple AI workers editing the same repository simultaneously will collide on branches, working directories, and git index locks unless each gets a clean, independent workspace.
- **Crash recovery**: long-running AI agents (10-15 minute turns) can crash, hang, or be killed. The system must detect this, reclaim the work, and resume without orphaning resources.
- **Lifecycle management**: tasks move through a multi-stage pipeline (queued, running, review, blocked, done) and each transition must be auditable, observable, and safe against concurrent mutation.
- **Operational visibility**: an unattended system running AI agents needs circuit breakers, health checks, and self-healing to avoid silently accumulating failures.

## Context

- **Project**: A TypeScript control-plane daemon ("gateway") orchestrating AI workers powered by an LLM-backed SDK (OpenCode). Workers execute software tasks against real git repositories.
- **Stack**: TypeScript, Node.js, SQLite (better-sqlite3), git worktrees, Discord (notifications), GitHub (PRs/merges).
- **Constraints**: Must support multiple concurrent workers against the same repo. Must survive daemon restarts and worker crashes gracefully. Workers must not be able to push to remote or execute network operations directly.
- **Scale**: Tens of tasks per day per repository, 1-5 concurrent workers, turn durations of 5-15 minutes each.

## Approach

The architecture has five major subsystems: worktree management, leased worker execution, a tick-based event loop, operational health tooling, and event telemetry.

### 1. Deterministic Worktree Management

Each task gets its own git worktree with a **deterministic name derived from task metadata**, not a random identifier. Given a task ID and title:

- Branch: `agent/task-{taskId}-{slug(title).slice(0,42)}`
- Path: `.worktrees/task-{taskId}-{slug(title).slice(0,42)}`

Determinism is the key property. If a worker crashes and the task is retried, it reuses the same worktree path and branch rather than creating orphans. The worktree provisioning method handles three cases:

1. **Path exists, branch matches** -- idempotent reuse (the common crash-recovery case).
2. **Path exists, branch mismatches** -- throw a collision error. This means two different tasks computed the same path, which requires human judgment.
3. **Branch checked out at a different path** -- throw a collision error. Git enforces single-checkout-per-branch, so this is unrecoverable without pruning the other worktree.

Collision errors carry structured remediation data: a `detail` field (what went wrong) and a `nextAction` field (what the operator should do). This "errors that carry their own fix instructions" pattern propagates through Discord notifications and escalation records, which means operators get actionable alerts rather than opaque failures.

### 2. Leased Worker Execution

Workers operate under a **lease-based crash recovery model**, similar to distributed lock patterns in systems like etcd or ZooKeeper, but implemented in SQLite:

- **Lease acquisition**: `tryAcquireWorkerRunLease(runId, owner, ttlSeconds)` performs an atomic SQLite update. Only one process can hold a lease at a time.
- **Heartbeat renewal**: A `setInterval` timer renews the lease every N seconds (default 15s) during execution.
- **Lease TTL**: Defaults to 180 seconds. If the worker process dies without releasing the lease, it expires naturally.
- **Turn timeout**: Defaults to 900 seconds (15 minutes). If the AI agent exceeds this, the worker is terminated.
- **Crash recovery**: When the daemon restarts, it finds expired leases and re-queues the associated tasks. The deterministic worktree ensures the retry picks up where the crash left off.

The worker validates AI agent output against a dual schema: a JSON Schema literal (passed to the LLM as an `outputSchema` constraint) and a Zod schema (for runtime TypeScript validation). These must be kept in sync -- see Pitfalls.

Worker results have three terminal statuses:
- **OK** -- work completed, triggers automated review (see `reviewer_gate_escalation` entry).
- **BLOCKED** -- worker hit an impediment, persists questions for operator review.
- **FAILED** -- unrecoverable error, creates an escalation record.

A normalization step catches workers that claim OK but left dirty git status (uncommitted changes), forcibly downgrading the result to BLOCKED. This is a trust-but-verify safeguard against LLM hallucination of success.

### 3. Tick-Based Event Loop

The gateway daemon runs a periodic tick (configurable interval) that advances all active work:

1. **Check engagement states** -- are any engagements ready for new task assignment?
2. **Dispatch ready tasks** -- assign workers to queued tasks that have available capacity.
3. **Poll running workers** -- check lease status, detect timeouts and crashes.
4. **Advance reviews** -- process completed reviews, handle approvals and rejections.
5. **Poll delegated tasks** -- check if parent tasks waiting on children can resume.
6. **Execute GitHub operations** -- push branches, create PRs, merge approved work.
7. **Sync task board** -- update the KANBAN.md mirror (see below).

Each tick is budget-bounded: it processes a maximum number of state transitions before yielding, preventing any single tick from running unboundedly.

### 4. Non-Blocking Task Delegation

Tasks can spawn subtasks (e.g., a refactoring task that decomposes into per-module subtasks). The delegation model treats **subtasks as first-class tasks** with their own worktrees, branches, worker runs, and review cycles:

- Parent transitions to `WAITING_FOR_CHILDREN` and returns control to the tick loop immediately.
- Each tick polls whether all children have reached terminal states.
- When all children complete, the parent moves to `AGGREGATING` (merges child branches) then `REVIEW_PENDING`.
- A depth limit (default 2) prevents runaway recursive delegation.

This replaced an earlier blocking model where subtasks ran in the parent's worktree with a synchronous wait -- see Pitfalls for why that failed.

### 5. Worker Sandboxing

Each worker gets a task-scoped home directory inside its worktree (`.worktrees/.agent_home/<runId>/`) with restricted tooling. The sandboxing approach includes command-level policy wrappers and network isolation at the SDK session level. For details on the security model (git command interception, policy wrappers, PATH shadowing), see the `security_hardening_ai_agent_systems` entry.

### 6. Automated Code Review

Completed worker output goes through an automated AI-powered review cycle against acceptance criteria before any branch push or merge. The review system uses a separate AI agent with read-only intent, severity-graded feedback, and escalation paths. For the full review gate pattern, see the `reviewer_gate_escalation` entry.

### 7. Operational Health Tooling

Three complementary tools maintain system health:

**Doctor command** (read-only audit with opt-in fix):
- Compares DB worktree records against disk (`git worktree list --porcelain`).
- Finds DB records missing on disk and disk worktrees not in DB.
- Detects stale task references (worktree path gone, task not RUNNING, no active lease).
- Lists expired engagement locks and worker leases.
- In `--fix` mode: runs `git worktree prune`, clears expired leases/locks, marks stale DB records as deleted.

**Reconcile service** (deep state reconciliation with severity tiers):
- `report-only` -- audit discrepancies between DB, disk, and git state.
- `fix-safe` -- clear expired locks/leases, cleanup terminal-task worktrees, regenerate KANBAN.md.
- `fix-unsafe` -- delete orphan worker runs, prune untracked disk worktrees.

**Invariant checker** (hard constraint verification):
- No orphan worker runs referencing deleted tasks.
- No RUNNING tasks without a worker_run_id.
- No stale leases on running tasks.
- No REVIEW_PENDING without a pending review record.
- No BLOCKED without a blocked_reason.
- No tasks with multiple active worker runs.
- No active tasks on paused repos.

### 8. Circuit Breaker (Panic Mode)

Automatic system pause after a configurable failure threshold (default: 5 failures in a 300-second sliding window). Each task FAILED or BLOCKED increments the counter; window expiry resets it. When the threshold is reached, the daemon sets `gateway.paused = true` and requires manual `resume-gateway` to restart.

### 9. Kanban Mirror and Audit Trail

`KANBAN.md` is a git-committed, auto-generated markdown file that mirrors the SQLite task table into kanban columns (Backlog, Next, Doing, Blocked, Review, Done, Failed). Every task status change triggers a sync-and-commit with a reason slug (e.g., `task-42-worker-review_pending`). This creates a git-visible audit trail of all task lifecycle transitions, readable without database access.

### 10. Event Telemetry

Events are dual-written to SQLite (queryable) and append-only JSONL files (durable, per-engagement and per-worker-run). Worker lifecycle events follow a schema: `worker.started`, `opencode.prompt.sent`, `opencode.response.received`, `worker.completed`, `worker.failed`. Discord notifications are transition-based with deduplication -- a `last_notified_state` field ensures each state is reported exactly once.

## Key Decisions

**Deterministic worktree names vs. random UUIDs**: Deterministic names enable crash recovery without orphan cleanup. The tradeoff is that slug collisions between similarly-named tasks are possible (mitigated by including the task ID). Random UUIDs would be collision-free but require explicit orphan-tracking and cleanup logic.

**SQLite lease-based recovery vs. filesystem locks**: SQLite leases survive process restarts because the lease state persists in the database with an expiry timestamp. Filesystem locks (flock) are released on process death, which sounds good but means you cannot distinguish "process died cleanly" from "process is still running but slow." TTL-based leases give a clear expiry semantic. The tradeoff is the heartbeat overhead.

**Non-blocking delegation vs. inline subtask execution**: Subtasks as independent tasks with their own worktrees avoids the single-worktree bottleneck and tick-loop blocking. The cost is merge complexity when aggregating child branches back into the parent. But the blocking alternative was catastrophic -- see Pitfalls.

**Dual-write events (SQLite + JSONL)**: SQLite enables queries ("show me all failed tasks this week") while JSONL provides durable append-only logs that survive database corruption and are easy to ship to external systems. The cost is write amplification and the need to keep both in sync conceptually.

**Git-committed KANBAN.md vs. dashboard-only visibility**: The kanban mirror makes task state visible to anyone with repo access and creates an implicit audit trail in git history. The cost is commit volume (hundreds of tiny commits per day in a busy system). A separate tracking branch or commit squashing would reduce noise.

**Panic mode without auto-recovery**: Intentional. The system halts to avoid compounding failures in an autonomous context where bad AI output could cause cascading damage. The risk is that transient failures permanently halt an unattended system. A configurable cooldown-and-resume timer would be a reasonable enhancement.

## Pitfalls & Gotchas

1. **Dual schema maintenance burden**: The worker output uses both a JSON Schema literal (for the LLM `outputSchema` parameter) and a Zod schema (for runtime validation). These must be kept in sync manually. The codebase uses `// SYNC:` comments to flag the pair. A `zodToJsonSchema` converter exists in the utils and is used by the reviewer service, but not by the worker runner. If you build this pattern, either generate one from the other at build time or use a single source of truth with a build step. Divergence between the two schemas causes silent data loss where the LLM produces valid-per-JSON-Schema output that fails Zod validation.

2. **Worktree collision is non-retryable by design**: Tasks blocked by `WORKTREE_COLLISION` stay BLOCKED permanently until an operator resolves and re-queues. This prevents thrashing (repeated collision-crash-retry loops) but means unattended systems accumulate stuck tasks. The doctor `--fix` command handles the common case (stale metadata referencing cleaned-up worktrees), but genuine cross-task collisions need human judgment about which task owns the branch.

3. **KANBAN.md commit volume**: Every task status change produces a git commit. A busy system generates hundreds of kanban sync commits per day, polluting `git log`. Mitigation options: use a dedicated orphan branch for kanban commits, squash them periodically, or switch to a non-committed status file read from the database directly.

4. **Worker HOME directory is inside the worktree**: The `.worktrees/.agent_home/<runId>` path lives inside the task worktree. If the AI agent writes temp files to absolute paths outside this directory, it escapes isolation. The command wrappers only restrict git remote operations and network access -- they do not enforce filesystem boundaries. A more robust approach would use a separate tmpdir outside the worktree or a containerized environment.

5. **Blocking subtask execution froze the entire system**: The original delegation implementation ran subtasks in the parent's worktree with a synchronous 30-minute poll-wait inside the tick loop. This blocked all other task processing across the entire daemon. The fix was the non-blocking `WAITING_FOR_CHILDREN` model described above. Lesson: in a tick-based event loop, never block on child work. Treat subtasks as independent state machines polled by the tick.

6. **Panic mode has no auto-recovery**: Once triggered, the system stays paused until manual `resume-gateway`. The `checkAndRecover()` method exists but only logs -- it does not implement automatic cooldown. In an unattended deployment, a burst of transient failures (e.g., LLM API rate limiting) permanently halts the system. Consider adding a configurable cooldown period after which the daemon automatically resumes with a reduced concurrency limit.

7. **Workers that claim success with dirty git state**: An AI agent may report `status: OK` while leaving uncommitted changes in the worktree. Without the `normalizeWorkerResultForContract()` check (which runs `git status` and downgrades to BLOCKED if dirty), these false-success results would proceed to review and potentially merge incomplete work. Always validate the workspace state independently of the agent's self-reported status.

## Recipe

### Prerequisites
- Node.js/TypeScript project with SQLite (better-sqlite3 or equivalent).
- A git repository where workers will operate.
- An LLM-backed coding agent SDK that can be invoked programmatically with structured output schemas.

### Step 1: Define the Domain Model

Create Zod-validated types for the core entities:
- **Task**: id, engagement_id, title, status (TODO, NEXT, RUNNING, BLOCKED, WAITING_FOR_CHILDREN, AGGREGATING, REVIEW_PENDING, REVIEW_APPROVED, REVIEW_REJECTED, COMPLETED, PUSHED, MERGED, FAILED), priority, parent_task_id, blocked_reason, worker_run_id.
- **WorkerRun**: id, task_id, status (PENDING, RUNNING, COMPLETED, BLOCKED, FAILED), lease_owner, lease_expires_at, last_notified_state.
- **WorktreeRecord**: task_id, branch_name, worktree_path, status (active, deleted).
- **Engagement**: id, repo_url, status, paused flag.

### Step 2: Implement Worktree Manager

Build a `WorktreeManager` class with:
- `ensureTaskWorktree(repoPath, taskId, taskTitle)` -- computes deterministic branch/path, handles the three cases (reuse, collision-same-path, collision-same-branch), calls `git worktree add` if needed.
- `removeTaskWorktree(worktreePath)` -- calls `git worktree remove --force`, updates DB record to deleted.
- `listWorktrees(repoPath)` -- parses `git worktree list --porcelain` output.
- `pruneWorktrees(repoPath)` -- calls `git worktree prune`.

The slug function should be deterministic: lowercase, replace non-alphanumeric with hyphens, collapse runs, trim to a max length. Include the task ID in the branch name to guarantee uniqueness even for identically-titled tasks.

### Step 3: Implement Worker Runner with Lease

Build a `WorkerRunner` class:
1. `tryAcquireWorkerRunLease(runId, owner, ttlSeconds)` -- atomic SQLite UPDATE with WHERE clause checking current lease is either unset or expired.
2. Create the worktree via the worktree manager.
3. Set up the sandboxed home directory with command wrappers (see `security_hardening_ai_agent_systems`).
4. Start a heartbeat interval that renews the lease every `heartbeatInterval` ms.
5. Invoke the AI agent SDK with the task prompt, output schema, and worktree as working directory.
6. On completion: validate output against Zod schema, check `git status` for cleanliness, compute final status (OK/BLOCKED/FAILED).
7. Clear the heartbeat interval and release the lease.
8. On crash/timeout: the heartbeat stops, the lease expires naturally, and the next daemon tick detects the expired lease and re-queues.

### Step 4: Build the Tick-Based Event Loop

The gateway daemon runs a `tick()` function on a configurable interval:
1. Skip if `gateway.paused` is true.
2. For each active engagement: advance tasks through their state machine.
3. Dispatch workers to tasks in NEXT status (respecting concurrency limits).
4. Poll RUNNING tasks: check lease expiry, detect timeouts.
5. Poll WAITING_FOR_CHILDREN tasks: check if all child tasks are terminal.
6. Process completed reviews: advance REVIEW_APPROVED to push/merge, re-queue REVIEW_REJECTED.
7. Sync the kanban mirror.
8. Check panic mode threshold.

Budget-bound each tick: process at most N state transitions before returning, to prevent a single tick from running indefinitely.

### Step 5: Add Operational Health Tools

Implement three health tools:
- **Doctor**: compare DB state vs. disk state vs. git state. Report discrepancies. In fix mode, prune stale records and expired leases.
- **Reconcile**: deeper version of doctor with tiered severity (report-only, fix-safe, fix-unsafe).
- **Invariant checker**: verify hard constraints (no orphan runs, no tasks in impossible states). Run this after every reconcile and on daemon startup.

### Step 6: Wire Up Telemetry and Notifications

- Dual-write events to SQLite `event_log` table and append-only JSONL files.
- Implement transition-based Discord/webhook notifications with `last_notified_state` deduplication.
- Add the panic mode circuit breaker: count failures in a sliding window, pause the system when the threshold is exceeded.

### Step 7: Add the Kanban Mirror

Implement `TaskBoardSync.syncAndCommit(reason)`:
1. Query all tasks, group by status into kanban columns.
2. Render markdown with task ID, priority, title, and blocked reason.
3. Write to `KANBAN.md` and commit with message `kanban: sync task board ({reason})`.
4. Call this method on every task status transition.

## Verification

**Worktree isolation is working**:
- Run two tasks simultaneously against the same repo. Verify each gets a distinct `.worktrees/task-{id}-*` directory with an independent git index. Running `git status` in each should show independent changes.
- Kill a worker mid-execution. Restart the daemon. Verify the task is re-queued and the retry reuses the same worktree path (not a new one).

**Lease recovery is working**:
- Start a worker, then kill the worker process (not the daemon). Wait for the lease TTL to expire. Verify the daemon's next tick detects the expired lease and transitions the task back to a retriable state.
- Verify the `worker_runs` table shows the original run with a FAILED status and a new run with PENDING/RUNNING.

**Tick loop is non-blocking**:
- Start a task that delegates subtasks. Verify the parent enters WAITING_FOR_CHILDREN immediately (within one tick interval) and other tasks continue to be dispatched and executed concurrently.

**Doctor and invariant checker are comprehensive**:
- Manually create an orphan worktree on disk (not tracked in DB). Run `doctor` in read-only mode. Verify it reports the orphan. Run `doctor --fix`. Verify it prunes the orphan.
- Manually set a task to RUNNING with no worker_run_id. Run the invariant checker. Verify it flags the violation.

**Panic mode triggers correctly**:
- Configure a low threshold (e.g., 2 failures in 60 seconds). Cause two task failures in quick succession. Verify the daemon pauses. Verify new tasks are not dispatched until manual resume.

**Event telemetry is consistent**:
- Complete a full task lifecycle. Verify the JSONL file contains the full event sequence (worker.started through worker.completed). Verify the SQLite event_log contains matching records. Verify Discord received exactly one notification per state transition (no duplicates).
