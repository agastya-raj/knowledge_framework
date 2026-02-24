---
title: "OpenCode SDK Integration and Multi-Backend AI Agent Abstraction"
type: integration
tags: [opencode-sdk, codex-sdk, backend-abstraction, sdk-migration, ai-agents, structured-output]
domain: software-engineering
created: 2026-02-24
updated: 2026-02-24
confidence: medium
complexity: medium
related: [ai_worker_orchestration_worktree_isolation, iterative_visual_generation_pipeline]
---

# OpenCode SDK Integration and Multi-Backend AI Agent Abstraction

## Problem

You need to integrate an AI agent backend into a multi-service application -- one where several components (intake interviewer, task worker, code reviewer, SVG generator, etc.) all need to send prompts and receive structured responses from an LLM. The requirements include:

- **Structured output** with schema validation (not just free-text responses)
- **Backend portability** -- the ability to swap between providers (OpenCode, Codex, direct Anthropic/OpenAI API) without rewriting business logic
- **Server lifecycle management** -- reliably starting, health-checking, and stopping a local SDK server process
- **Session persistence** -- crash recovery and resumption of long-running agent conversations
- **Testability** -- running the full pipeline without making real API calls

Solving these individually is straightforward. Solving them together, while migrating from an older SDK (Codex) to a newer one (OpenCode), creates a web of integration concerns that this entry addresses.

## Context

This knowledge was developed across two projects:

1. **Consultancy gateway daemon** (TypeScript/Node.js) -- orchestrates intake interviews, task workers, and automated code reviews. Originally built on `@openai/codex-sdk`, migrated to `@opencode-ai/sdk`. Uses SQLite for event persistence and session tracking.

2. **SVG generation pipeline** (Python + Node.js subprocess backends) -- an iterative visual generation system where nine pipeline roles (gen, critic, debugger, planner, decomposer, evaluator, layout, colorstyle, refiner) each need an LLM backend. Supports runtime backend switching via environment variables.

Key tool versions and dependencies:
- `@opencode-ai/sdk` (v2 client API) -- the primary SDK going forward
- `@openai/codex-sdk` -- the legacy SDK, retained for backward compatibility during migration
- Zod v4 with native `toJSONSchema()` -- for schema generation (not the third-party `zod-to-json-schema` package)
- Python `subprocess` module -- for the cross-language backend protocol

The core constraint was that both projects needed to run with any backend, including a zero-cost test backend, without any code changes to the consuming business logic.

## Approach

The solution has three layers: a server lifecycle manager, a unified prompt interface, and a subprocess-based backend abstraction for cross-language pipelines.

### Layer 1: Server Lifecycle Manager (TypeScript)

The OpenCode SDK requires a running `opencode serve` process. A dedicated `OpenCodeService` class manages this with a defensive startup sequence:

1. **Check first, spawn second.** Before starting a new server, hit the health endpoint (`GET {baseUrl}/global/health`). If a server is already running (perhaps from another process or a previous crash), connect to it instead of spawning a duplicate.

2. **Spawn with captured output.** If no server is found, spawn `opencode serve --port {port} --hostname {hostname}` with `stdio: ["ignore", "pipe", "pipe"]` and `detached: false`. Capture stdout/stderr for diagnostics.

3. **Poll with exponential backoff.** After spawning, poll the health endpoint starting at 100ms intervals, doubling up to a 2-second cap, with a configurable total timeout (default 10 seconds). The health response shape is `{ healthy: boolean, version?: string }`.

4. **Track ownership.** Record whether this process spawned the server (via a non-null process handle). On shutdown, only kill the server if this process owns it -- never kill a shared server.

5. **Cache the client.** Create the SDK client once via `createOpencodeClient({ baseUrl })` and reuse it for all sessions.

### Layer 2: Structured Prompt Interface (TypeScript)

Each consumer (interviewer, worker, reviewer) follows the same pattern:

1. **Create or resume a session** via `client.session.create({ body: { title } })`. Persist the session ID to a database for crash recovery.

2. **Build the prompt** with parts array: `[{ type: "text", text: "..." }]`, a model specified as a `providerID/modelID` pair (e.g., `openai/gpt-5-codex`), an optional system prompt, and an optional structured output format.

3. **Send with timeout racing.** Race the SDK's `client.session.prompt()` against an `AbortController` timeout (default 15 minutes). This is necessary because the SDK may not enforce its own timeout for long-running prompts.

4. **Parse the response.** Extract text from `response.parts`, with a defensive fallback: if parts are empty but a message ID exists, fetch the assistant message separately via `client.session.message()`.

5. **Record events.** Dual-write every interaction (session created, prompt sent, response received, errors) to both SQLite and a JSONL file for audit trail and debugging.

For structured output, Zod schemas are converted to JSON Schema at construction time using a utility that wraps Zod v4's native `toJSONSchema()`:

```typescript
import { z, toJSONSchema as zodToJsonSchemaInternal } from "zod";

export function zodToJsonSchema<T>(zodSchema: z.ZodType<T>): OpenCodeJsonSchema {
  const jsonSchema = zodToJsonSchemaInternal(zodSchema, { target: "draft-07" });
  delete jsonSchema.$schema;  // OpenCode rejects this key
  return {
    type: "json_schema",
    schema: { ...jsonSchema, additionalProperties: false },
  };
}
```

The format is then passed as `format: zodToJsonSchema(myZodSchema)` in the prompt call. Always define schemas in Zod and derive JSON Schema -- never maintain hand-written JSON schemas alongside Zod schemas, as they inevitably drift.

### Layer 3: Subprocess Backend Abstraction (Python)

For cross-language pipelines, a subprocess protocol decouples backend selection from business logic entirely:

1. **Uniform protocol.** Every backend is a standalone executable (Python or Node.js) that reads a JSON object from stdin (`{"prompt": "...", "svg": "...", "image_base64": "..."}`) and writes a JSON response to stdout (`{"text": "..."}` or `{"svg": "..."}`).

2. **Environment-driven selection.** Each pipeline role has an environment variable (e.g., `SVG_GEN_CMD`, `SVG_CRITIC_CMD`) pointing to the backend script. The invoker resolves the command via `shlex.split()` on the env var value, allowing full command composition including interpreter paths.

3. **Four backend tiers per role:**
   - **Echo** (Python) -- returns deterministic fixtures for testing. Zero API calls.
   - **OpenCode** (Node.js) -- routes through the OpenCode server via the SDK v2 client.
   - **Codex** (Node.js) -- routes through the legacy Codex SDK. Retained during migration.
   - **Direct API** (Python) -- calls Anthropic or OpenAI APIs directly via their Python SDKs.

4. **Central invocation.** A single `invoke_backend()` function handles JSON serialization, `subprocess.run()` with timeout enforcement, stderr capture (truncated to 300 characters for log readability), and duration tracking.

## Key Decisions

### Zod-first schema generation vs. hand-written JSON Schema

**Decision:** Always define schemas in Zod and derive JSON Schema programmatically.

**Alternatives considered:** (a) Hand-written JSON Schema objects, (b) maintaining both in parallel with sync comments.

**Why Zod-first wins:** Option (b) was tried in one service (`workerRunner.ts`) and immediately created a maintenance burden -- the Zod schema and JSON Schema had `// SYNC` comments that were ignored during edits. A second service (`intakeInterviewer.ts`) used the cleaner Zod-first approach and never had a schema drift bug. The cost of the converter utility is trivial compared to debugging silent validation mismatches.

**When hand-written might be better:** If you have no TypeScript in the stack and are working purely in Python or another language without a Zod equivalent. In that case, use Pydantic with `model_json_schema()`.

### Subprocess protocol vs. in-process SDK calls

**Decision:** Use a JSON-over-stdin/stdout subprocess protocol for the multi-backend SVG pipeline.

**Alternatives considered:** (a) In-process Python SDK calls with adapter classes, (b) HTTP microservices per backend, (c) subprocess protocol.

**Why subprocess wins:** The pipeline mixes Python and Node.js backends. In-process adapters would require either rewriting all backends in one language or embedding a JS runtime. HTTP microservices add deployment complexity for what is fundamentally a local dev tool. Subprocess protocol lets each backend be a standalone script in its native language, testable in isolation with `echo '{}' | python backend.py`.

**When in-process is better:** If all backends are in the same language and you need sub-millisecond latency between prompt and response (the subprocess overhead is ~10-50ms per invocation).

### Connect-or-spawn server lifecycle

**Decision:** Always check for an existing server before spawning a new one.

**Alternatives considered:** (a) Always spawn a fresh server, (b) require the user to start the server manually, (c) check-then-spawn.

**Why check-then-spawn wins:** In development, multiple processes often share one server. Always-spawn creates port conflicts. Manual-start is fragile. The health check adds ~50ms to startup and prevents duplicate servers.

### Dual event persistence (SQLite + JSONL)

**Decision:** Write every OpenCode interaction event to both a SQLite database and a JSONL file.

**Why both:** SQLite enables structured queries for dashboards and recovery (e.g., "find all sessions for task X"). JSONL provides a human-readable, append-only log that survives database corruption and is trivial to `grep` during debugging. The write cost is negligible compared to LLM latency.

## Pitfalls & Gotchas

### 1. Empty response parts race condition

**What happens:** `client.session.prompt()` returns a response where `parts` is an empty array, even though the LLM did produce output. The `info.id` field is populated.

**Why it's unexpected:** The SDK response object appears complete -- no error, valid structure -- but the content is missing.

**Resolution:** If `parts` is empty and `info.id` exists, fetch the assistant message separately via `client.session.message({ sessionID, messageID: info.id })`. This is a known race condition in the SDK where the response arrives before message parts are fully populated.

### 2. `$schema` key causes silent structured output failure

**What happens:** When Zod's `toJSONSchema()` generates a JSON Schema, it includes a `$schema` meta-key. OpenCode's structured output validator rejects schemas containing this key, but the failure is silent -- you get unstructured text instead of a validation error.

**Resolution:** Always `delete jsonSchema.$schema` after generation, before passing to the OpenCode format wrapper. Use `target: "draft-07"` as the schema target -- OpenCode expects Draft-07, not later drafts.

### 3. SDK import path divergence between `@opencode-ai/sdk` and `@opencode-ai/sdk/v2/client`

**What happens:** Importing `createOpencodeClient` from the top-level `@opencode-ai/sdk` works in isolation, but when both old and new SDK client APIs coexist in `node_modules` (common during migration), the import resolves to the v1 API.

**Resolution:** Use the explicit deep import `@opencode-ai/sdk/v2/client` when the v1 SDK may be present. Once migration is complete, the top-level import is fine.

### 4. Server process ownership -- killing shared servers

**What happens:** If your service connects to an already-running OpenCode server (started by another process or manually), and your shutdown code kills that server, all other consumers lose their backend.

**Resolution:** Track whether you spawned the server (non-null process handle). In `stopServer()`, only send SIGTERM if you own the process. If you connected to an existing server, shutdown is a no-op.

### 5. Environment variable passthrough to spawned workers

**What happens:** When the gateway daemon spawns worker subprocesses, those workers fail silently on non-default deployments because OpenCode-related environment variables (`OPENCODE_SERVER_URL`, `OPENCODE_SERVER_PORT`, `OPENCODE_DEFAULT_MODEL`, etc.) are not in the subprocess environment.

**Why it's unexpected:** The workers fall back to defaults (localhost:4096) which may happen to work in development but fail in staging/production. No error is thrown -- the worker just can't reach the server.

**Resolution:** Explicitly allowlist and forward all `OPENCODE_*` environment variables when spawning subprocesses. Don't rely on the default `process.env` inheritance if you're constructing a custom env object.

### 6. Timeout racing is mandatory for long prompts

**What happens:** The SDK's built-in timeout may not fire for very long-running prompts (e.g., complex code generation tasks that take 10+ minutes).

**Resolution:** Always race `client.session.prompt()` against an `AbortController` with your own timeout. Default to 15 minutes (`900_000ms`). This ensures your application doesn't hang indefinitely on a stuck prompt.

### 7. Legacy column naming after SDK migration

**What happens:** Database columns like `codex_thread_id` now store OpenCode session IDs. The naming mismatch causes confusion for anyone reading the schema or writing queries.

**Resolution:** Accept the naming debt during migration and document it with comments. Renaming requires a database migration that touches every query referencing the column. Schedule the rename for a dedicated cleanup pass, not during the SDK migration itself.

### 8. OpenCode authentication modes

**What happens:** The SDK supports three authentication patterns, and using the wrong one produces opaque 401 errors.

**Resolution:** The three modes, in priority order: (1) explicit `OPENCODE_AUTH_HEADER` environment variable -- used as-is in the `Authorization` header, (2) `OPENCODE_SERVER_USERNAME` + `OPENCODE_SERVER_PASSWORD` -- composed into a Basic auth header, (3) `OPENCODE_BASIC_AUTH` -- accepts either `password` or `user:password` format for backward compatibility. Check which mode your deployment expects and set the corresponding env vars.

## Recipe

### Setting up the OpenCode server lifecycle manager

1. **Install the SDK.** Add `@opencode-ai/sdk` to your project. If migrating from Codex, keep `@openai/codex-sdk` temporarily but use the deep import `@opencode-ai/sdk/v2/client` to avoid resolution conflicts.

2. **Create a service class** with these responsibilities: server process reference (nullable), client reference (cached), and configuration (hostname, port, startup timeout, default model).

3. **Implement `startServer()`.** First, construct the base URL from hostname and port. Fetch `GET {baseUrl}/global/health` with a 5-second `AbortSignal.timeout`. If `{ healthy: true }` is returned, cache the client and return. Otherwise, spawn `opencode serve --port {port} --hostname {hostname}` with `stdio: ["ignore", "pipe", "pipe"]` and `detached: false`.

4. **Implement health polling.** After spawning, poll the health endpoint with exponential backoff: start at 100ms, double each attempt, cap at 2 seconds, abort after the configured timeout (default 10 seconds). If polling fails, kill the spawned process and throw.

5. **Implement `stopServer()`.** Check if `this.serverProcess` is non-null. If so, send SIGTERM. If null (connected to an existing server), do nothing.

6. **Create the client** via `createOpencodeClient({ baseUrl })` after health check passes. Cache it as an instance property.

### Setting up structured prompts with Zod

7. **Define your output schema in Zod.** For example, a task result schema with `summary`, `status`, and `commits` fields.

8. **Build the schema converter.** Import `toJSONSchema` from `zod` (v4 native, not the third-party package). Call it with `{ target: "draft-07" }`, delete the `$schema` key from the result, wrap in `{ type: "json_schema", schema: { ...result, additionalProperties: false } }`.

9. **Send a prompt.** Call `client.session.create()` to get a session, then `client.session.prompt()` with `parts`, `model` (as `{ providerID, modelID }` -- split on first `/`), optional `system`, and `format` from step 8.

10. **Handle empty parts.** After receiving the response, check if `parts` is empty. If so and `info.id` exists, call `client.session.message()` to fetch the content separately.

### Setting up the subprocess backend abstraction

11. **Define the protocol.** Each backend reads a JSON object from stdin and writes a JSON object to stdout. Agree on the payload keys (e.g., `prompt`, `svg`, `image_base64` for input; `text` or `svg` for output).

12. **Write backend scripts.** For each pipeline role, create one script per backend tier. The echo backend returns hardcoded fixtures. The OpenCode backend imports the SDK client, sends the prompt, and writes the response. The direct API backend calls the provider SDK.

13. **Write the invoker.** A Python function that reads the backend command from an environment variable, splits it with `shlex.split()`, calls `subprocess.run()` with `input=json_payload`, `capture_output=True`, `timeout=configured_timeout`, and parses the stdout JSON.

14. **Configure via environment.** Set `SVG_GEN_CMD=python echo_gen.py` for testing, `SVG_GEN_CMD=node opencode_gen.mjs` for OpenCode, etc. No code changes needed to switch backends.

### Event recording (optional but recommended)

15. **Define event types.** At minimum: `session.created`, `prompt.sent`, `response.received`, `error`. Include `timestamp`, `source`, `event_type`, and `payload` (with token usage: `input_tokens`, `output_tokens`, `cached_input_tokens`).

16. **Dual-write.** Append events to a JSONL file (human-readable, greppable) and insert into a SQLite table (queryable for dashboards and recovery). Persist session IDs in a dedicated table for crash recovery.

## Verification

### Server lifecycle

- **Health check:** `curl http://127.0.0.1:4096/global/health` should return `{"healthy":true,"version":"..."}`.
- **Ownership tracking:** Start your service, confirm it connects to or spawns the server. Start a second instance -- it should connect to the existing server, not spawn a duplicate. Stop the second instance -- the server should remain running. Stop the first (owning) instance -- the server should shut down.

### Structured output

- **Schema conversion:** Pass a Zod schema through the converter and inspect the output. Verify no `$schema` key is present. Verify `additionalProperties: false` is set at the top level.
- **Round-trip test:** Send a prompt with a structured format and verify the response parses against the original Zod schema without errors. A common subtle failure: the response looks like valid JSON but contains extra fields that Zod's `.parse()` strips -- use `.strict()` during testing to catch this.

### Subprocess backends

- **Echo backend isolation test:** `echo '{"prompt":"test"}' | python echo_gen.py` should return valid JSON with deterministic content. No network calls should be made (verify with network monitoring or by running offline).
- **Backend switching:** Run the pipeline with `SVG_GEN_CMD=python echo_gen.py`, then switch to `SVG_GEN_CMD=node opencode_gen.mjs` and run again. Business logic code should be identical -- only the env var changes.
- **Timeout enforcement:** Set a very short timeout (e.g., 2 seconds) and send a prompt that would normally take longer. Verify the subprocess is killed and an appropriate error is raised.

### Event recording

- **JSONL integrity:** After a prompt round-trip, `tail -1 events.jsonl | python -m json.tool` should produce valid JSON with the expected event structure.
- **SQLite query:** `SELECT COUNT(*) FROM events WHERE event_type = 'opencode.response.received'` should match the number of prompts sent.
- **Session recovery:** Kill the process mid-conversation, restart it, and verify it resumes the existing session rather than creating a new one (check that the session ID from the database matches the one used in the resumed prompt).
