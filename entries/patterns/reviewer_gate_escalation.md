---
title: "Reviewer Gate and Escalation Pattern for AI Agent Quality Control"
type: pattern
tags: [ai-agents, quality-gate, code-review, escalation, orchestration, human-in-the-loop]
domain: software-engineering
created: 2026-02-24
updated: 2026-02-24
confidence: medium
complexity: medium
related: [ai_worker_orchestration_worktree_isolation, multi_agent_burst_analysis]
---

# Reviewer Gate and Escalation Pattern for AI Agent Quality Control

## Problem

When AI agents autonomously generate code in an orchestrated pipeline, there is no guarantee that a worker agent's self-reported "done" status reflects actual quality. An agent may report success while leaving uncommitted changes, producing code that does not meet acceptance criteria, or even generating subtly incorrect output that appears correct on the surface. Without an independent verification step, low-quality or incomplete work flows downstream -- into git branches, pull requests, and eventually production -- with no checkpoint for catching it.

The core challenge: how do you build a mandatory quality gate into an autonomous agent pipeline such that (a) no worker output bypasses review, (b) the reviewer itself cannot corrupt the work it is reviewing, and (c) problems that exceed AI capabilities are reliably surfaced to a human operator?

## Context

This pattern was discovered in a consultancy gateway project that orchestrates multiple AI agents (workers, reviewers, architects) through a daemon tick loop. The system uses:

- A daemon process (`GatewayDaemon`) that drives a tick loop, advancing tasks through their lifecycle each tick
- AI sessions via OpenCode (could be adapted to any AI coding tool that supports session creation)
- A relational database tracking task status, worker runs, reviews, escalations, and agent threads
- Git worktrees for isolated workspaces per task
- Discord webhooks for human notification of escalations

The pattern is applicable to any system where AI agents produce artifacts (code, documents, analysis) that need quality assurance before being accepted. The specific tools (OpenCode, Discord) are interchangeable; the structural pattern is what matters.

## Approach

The pattern has three interlocking layers: a **status state machine** that enforces the review gate, a **reviewer service** that performs independent verification, and an **escalation service** that routes failures to humans.

### Layer 1: Status State Machine with Mandatory Review Gate

Every task follows a status progression where worker completion never leads directly to "done." The review-related flow is:

```
RUNNING --> worker reports OK --> REVIEW_PENDING
REVIEW_PENDING --> reviewer approves --> REVIEW_APPROVED --> COMPLETED
REVIEW_PENDING --> reviewer rejects --> REVIEW_REJECTED (terminal, needs human)
```

The critical design constraint: there is **no auto-complete path**. A worker that reports `status: "OK"` is always routed to `REVIEW_PENDING`, never directly to `COMPLETED`. This is enforced at the status transition layer, not by convention.

Worker output uses a structured schema with exactly three statuses: `OK`, `BLOCKED`, and `FAILED`. Only `OK` triggers the review path. `BLOCKED` and `FAILED` bypass review entirely (there is nothing to review if the worker could not complete the task).

An additional safety net: if a worker reports `OK` but has uncommitted changes (detected via `git status --porcelain`), the status is silently normalized to `BLOCKED` with reason `dirty_git_status`. This prevents unreviewed uncommitted work from entering the review pipeline.

### Layer 2: Independent Reviewer Service

The reviewer is a separate AI session -- a completely independent thread with no shared context from the worker session. This independence is architecturally important: the reviewer cannot be influenced by the worker's reasoning chain or intermediate state.

The review execution follows five steps:

1. **Create a review record** immediately when a worker reports `OK`. This record links the task ID, worker run ID, and a `pending` status. The review record's existence is what keeps the task in `REVIEW_PENDING`.

2. **Assemble review context** from git artifacts, not from the worker's self-report. The reviewer receives:
   - Task title, description, and acceptance criteria (from the original task spec)
   - Git commits since merge-base (`git log --oneline base..HEAD`)
   - Diff summary (`git diff base --stat`)
   - Changed file list (`git diff --name-status base..HEAD`)
   - An explicit instruction: "Do NOT modify any code. This is a read-only review."

3. **Execute the review** in its own AI session. The reviewer returns structured JSON: `{ approved: boolean, summary: string, issues: Array<{severity, description}>, suggestions: string[] }`.

4. **Verify worktree cleanliness** after the reviewer session completes. Even though the reviewer is instructed not to modify code, the system defensively checks `git status --porcelain`. If the worktree is dirty, the review is **force-rejected** regardless of the AI's approval decision, with a high-severity issue appended. Prompt instructions alone are not a reliable control against an AI modifying files.

5. **Apply the decision** to update both the review record and the task status. Approval transitions the task through `REVIEW_APPROVED` then immediately to `COMPLETED` (two sequential status writes). Rejection transitions to `REVIEW_REJECTED` with the issues serialized into `blocked_reason` and `blocked_detail`.

### Layer 3: Escalation Service with Multiple Trigger Points

Escalation is a separate concern from the review decision. The escalation service maintains records with severity levels (`low`, `medium`, `high`, `critical`) and integrates with a notification channel (Discord in this case) to alert humans.

Escalation triggers are distributed throughout the daemon, not centralized in the review service:

| Trigger | Severity | Where It Fires | Condition |
|---------|----------|-----------------|-----------|
| Review rejection | high | `tickReviews()` | Any review that returns `approved: false` |
| Stale review | medium | `tickReviews()` | Review pending for >30 minutes |
| Orphan review | high | `tickReviews()` | Task in `REVIEW_PENDING` with no associated worker run (invariant violation) |
| Worktree collision | medium | `WorkerRunner` | Another task already owns the target worktree path |
| Structured output parse failure | high | `WorkerRunner` | Worker AI returned malformed JSON |
| General runner error | medium | `WorkerRunner` | Any other worker crash |
| Child task failure | high | `tickWaitingForChildren()` | Parent waiting on children; a child is `FAILED`, `BLOCKED`, or `REVIEW_REJECTED` |

Each escalation trigger includes deduplication logic to avoid flooding the notification channel. The notification layer processes up to 10 unresolved escalations per daemon tick, marks each as notified after sending, and enforces a minimum interval between sends (2 seconds) to avoid API rate limits.

### Operator Interaction Model

Not all statuses are operator-settable. The system distinguishes between system-managed and operator-managed statuses:

- **System-managed (operator cannot set directly):** `REVIEW_PENDING`, `REVIEW_APPROVED` -- these are owned by the review lifecycle
- **Operator-managed (human can override):** `REVIEW_REJECTED` -- the human can move this back to `NEXT` (to re-run the worker) or to `BLOCKED` (to park it)

This means `REVIEW_REJECTED` is the designed human intervention point. The system escalates, the human assesses, and the human decides the next step.

## Key Decisions

**Independent AI session for review, not the same agent re-checking its own work.** The alternative -- having the worker self-review -- was rejected because an agent that produced flawed output is likely to approve its own flawed output for the same reasoning. Using a separate session ensures no shared context or confirmation bias. The cost is an additional AI invocation per task.

**Git artifacts as review input, not the worker's self-reported summary.** The reviewer sees what actually changed in the repository, not what the worker claims it changed. This prevents a worker from misrepresenting its output. The tradeoff is that the reviewer lacks the worker's reasoning context, which can occasionally lead to false rejections on intentional but unusual changes.

**Defensive worktree check over prompt-only control.** The reviewer is told not to modify files, but the system also verifies this mechanically. This defense-in-depth was clearly a learned lesson -- prompt instructions alone are insufficient to prevent an AI from modifying files it has access to.

**Rejection as a terminal state requiring human intervention, not an auto-retry.** The alternative -- automatically re-running the worker on rejection -- risks infinite loops and masks systemic problems. By making rejection terminal, the system forces human visibility into quality issues. Under conditions where rejection rates are very low and well-understood, adding a single automatic retry with a different prompt could be justified, but the default should be conservative.

**Two-step write for approval (REVIEW_APPROVED then COMPLETED).** This allows downstream logic (such as branch pushing) to gate on either status, providing a brief window where "approved but not yet finalized" is a distinct state. The alternative of a single atomic write would be simpler but loses this intermediate observability.

## Pitfalls & Gotchas

1. **Reviewer modifying the worktree despite instructions.** Telling an AI "do NOT modify any code" in the prompt is necessary but not sufficient. AI agents may still edit files if they interpret the task as requiring changes. The mechanical check (`git status --porcelain` after the reviewer session) is the actual enforcement. Any system that relies solely on prompt instructions for security-relevant constraints is vulnerable. Always verify mechanically.

2. **The REVIEW_APPROVED to COMPLETED transition window.** The `applyDecision` method writes `REVIEW_APPROVED` then immediately writes `COMPLETED` in two separate database calls. Any code that triggers on task status must accept both `REVIEW_APPROVED` and `COMPLETED` as valid "done" states, or it will miss the brief intermediate state. New feature code that checks "is this task done?" must check for both.

3. **Silent normalization of dirty worker output.** When a worker reports `OK` but has uncommitted changes, the system overrides the status to `BLOCKED` with reason `dirty_git_status`. The worker's self-reported summary and commit list are preserved but the status is changed. This can be confusing when debugging: a task appears blocked but has a summary that reads as if the work was completed. Always check `blocked_reason` when diagnosing a `BLOCKED` task that has a populated summary.

4. **Hard-coded stale review timeout.** The 30-minute timeout for stale reviews is not configurable. Large diffs on complex tasks may legitimately take longer to review, creating spurious escalations that train operators to ignore the notification channel. If adapting this pattern, make the timeout configurable and consider scaling it with diff size.

5. **Inconsistent escalation deduplication strategies.** Stale reviews deduplicate by review ID (`getUnresolvedEscalationByReviewId`). Orphan reviews deduplicate by exact string match on the reason field against all unresolved escalations for that task. These two strategies in the same service create subtle bugs: changes to the reason string format can break deduplication for orphan reviews, while stale review deduplication is stable. Prefer a uniform deduplication strategy -- keying on a combination of task ID, escalation type enum, and optional reference ID.

6. **No automatic retry after rejection.** `REVIEW_REJECTED` is effectively terminal. A human must intervene to move the task back to `NEXT` or close it. This is intentional (see Key Decisions), but it means that a single flawed review can block an entire pipeline if the human is not monitoring the notification channel. Ensure your notification channel has high reliability and that operators have clear SLAs for responding to escalations.

7. **Operator status permissions are asymmetric.** Operators can move tasks out of `REVIEW_REJECTED` but cannot override `REVIEW_PENDING` or `REVIEW_APPROVED` (except to `BLOCKED`). This means if a review is stuck in `REVIEW_PENDING` due to a bug, the only operator escape hatch is forcing to `BLOCKED`, which loses the review context. Consider adding an operator escape for cancelling a pending review.

## Recipe

To implement this pattern in a new agent orchestration system:

1. **Define the task status state machine.** Add `REVIEW_PENDING`, `REVIEW_APPROVED`, `REVIEW_REJECTED` to your task status enum. Enforce at the transition layer that a worker reporting success always transitions to `REVIEW_PENDING`, never to `COMPLETED`. Make `REVIEW_REJECTED` operator-settable; make `REVIEW_PENDING` and `REVIEW_APPROVED` system-managed only.

2. **Add a worker output normalization step.** Before accepting a worker's `OK` status, check for uncommitted changes in the working directory (`git status --porcelain` or equivalent). If dirty, override to `BLOCKED` with a reason indicating dirty state. Preserve the worker's summary for debugging.

3. **Implement the review record.** Create a data model linking task ID, worker run ID, reviewer thread/session ID, status (`pending`, `approved`, `rejected`), structured issues array, and timestamps. Create the review record immediately when the worker reports success.

4. **Build the reviewer invocation.** Spawn an independent AI session (separate from the worker session) with read-only instructions. Feed it git-derived artifacts: commits since merge-base, diff stats, changed file list, plus the original task spec and acceptance criteria. Require structured JSON output with `approved`, `summary`, `issues[]`, and `suggestions[]`.

5. **Add the worktree cleanliness check.** After the reviewer session completes, verify the working directory is clean. If it is not, force-reject the review regardless of the AI's decision. Log the dirty files as a high-severity issue in the review record.

6. **Implement the decision application.** On approval: update review status to `approved`, transition task to `REVIEW_APPROVED`, then immediately to `COMPLETED`. On rejection: update review status to `rejected`, transition task to `REVIEW_REJECTED`, populate `blocked_reason` and `blocked_detail` from the review issues.

7. **Build the escalation service.** Create an escalation data model with severity levels, task reference, reason, context, and notification tracking. Distribute escalation triggers across the system: review rejections (high), stale reviews (medium, with configurable timeout), invariant violations (high), worker errors (medium/high). Implement deduplication using a uniform strategy (task ID + escalation type + optional reference ID).

8. **Connect the notification channel.** Integrate with your notification system (Discord, Slack, email). Process escalations in batches per tick, mark as notified after sending, enforce rate limits between sends. Include escalation ID, task reference, severity, reason, and truncated context in each notification.

9. **Wire it into your daemon tick loop.** Order matters: run worker launches before reviews, reviews before escalation notifications. Budget-check between phases if you have concurrency limits. The recommended ordering is: task dispatch, review execution, child task management, escalation notification.

## Verification

**The review gate is enforced (no bypass path exists):**
- Create a task, run a worker to completion with `OK` status. Verify the task transitions to `REVIEW_PENDING`, not to `COMPLETED`. Check that a review record exists with `pending` status.
- Attempt to manually set a `REVIEW_PENDING` task to `COMPLETED` via the operator interface. This should fail (status is system-managed).

**The reviewer cannot corrupt the work:**
- Run a review where the reviewer AI modifies a file in the worktree (you may need to craft a prompt that triggers this). Verify the review is force-rejected with an issue citing "modified worktree files," regardless of what the AI's approval decision was.

**Dirty worker output is caught:**
- Run a worker that reports `OK` but leaves uncommitted changes. Verify the task transitions to `BLOCKED` (not `REVIEW_PENDING`) with `blocked_reason` containing `dirty_git_status`.

**Escalations fire and notify correctly:**
- Reject a review and verify a `high` severity escalation is created and a notification is sent to the configured channel.
- Leave a review in `pending` beyond the stale timeout and verify a `medium` severity escalation is created (only once, not duplicated on subsequent ticks).
- Create a `REVIEW_PENDING` task with no associated worker run and verify a `high` severity escalation is created.

**Operator recovery works:**
- Move a `REVIEW_REJECTED` task back to `NEXT` via the operator interface. Verify the worker re-runs and produces a new review cycle.
- Verify that `REVIEW_PENDING` cannot be moved to `NEXT` by an operator (only to `BLOCKED`).

**End-to-end happy path:**
- Submit a task, let the worker complete, let the reviewer approve. Verify the task progresses: `RUNNING` -> `REVIEW_PENDING` -> `REVIEW_APPROVED` -> `COMPLETED`. Verify no escalations were created.
