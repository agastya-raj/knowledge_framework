---
title: "Iterative Multi-Agent Generation with Visual Feedback Loop"
type: pattern
tags: [multi-agent, visualizer-critic, iterative-generation, svg, feedback-loop, vlm, pipeline]
domain: software-engineering
created: 2026-02-24
updated: 2026-02-24
confidence: medium
complexity: high
related: [opencode_sdk_backend_abstraction, security_hardening_ai_agent_systems]
---

# Iterative Multi-Agent Generation with Visual Feedback Loop

## Problem

When using LLMs to generate visual artifacts (SVG figures, diagrams, layouts), the generator never sees its own rendered output. It produces markup based on textual understanding of spatial relationships, but has no visual confirmation of whether elements overlap, text is readable, colors clash, or the layout matches the intent. Errors in placement, sizing, and composition persist silently across generations because there is no feedback mechanism connecting the rendered result back to the generator.

You need a pipeline where generated visual artifacts are rendered, evaluated by a vision-capable model, and iteratively refined -- closing the loop between "what the code says" and "what the human sees."

## Context

- **Source project:** SVG PaperBanana -- a multi-agent SVG figure generation system
- **Stack:** Python (FastAPI backend), with agent backends in Python and Node.js (ESM), subprocess-based agent protocol
- **Models:** Any combination of text LLMs (generation, planning) and VLMs (critique, analysis) -- the pipeline is model-agnostic via a subprocess protocol
- **Scale:** Up to 9 specialist agent roles, 1-10 iteration cycles per generation run
- **Constraint:** Agents are untrusted in the sense that their output (especially SVG) may contain malformed markup, injection vectors, or non-JSON stdout noise -- the pipeline must be defensive at every boundary
- **Deployment:** Single-machine, exposed over Tailscale for private access; FastAPI with SSE streaming for real-time iteration progress

## Approach

The pipeline executes in three phases: pre-loop setup, an iterative generation-critique loop, and post-loop refinement.

### Phase 1: Pre-loop (run once)

Two optional agents prepare structured context before any SVG is generated:

1. **Decomposer** -- breaks the user's natural-language prompt into ordered sub-tasks, sequenced background-to-foreground (painter's algorithm). Output is JSON with `sub_tasks`, `complexity`, and `notes`.
2. **Planner** -- produces a structured figure specification: title, figure type, dimensions, positioned elements, color palette, layout notes, text elements. If decomposition exists, it feeds into the planner as additional context.

Both are optional. When disabled, the generator works directly from the user prompt.

### Phase 2: Iteration loop (N cycles)

Each iteration executes these steps in sequence:

1. **Generator** -- produces SVG from a combined prompt that accumulates all available context: decomposition, plan, example guidance, the previous iteration's SVG (as seed), critique history, analysis history, and custom user instructions (appended last with highest priority). On iterations 2+, the prompt explicitly instructs: "You are revising the previous SVG. Do not start from a blank canvas. Preserve working structure and only change parts needed to satisfy the latest feedback."

2. **Sanitizer** (built-in, not an agent) -- strips dangerous SVG elements (`<script>`, `<foreignObject>`, `<iframe>`, `<animate>`) and attributes (event handlers, external URL references). Only internal fragment references like `url(#grad)` are permitted. This runs on every SVG entering the pipeline, without exception.

3. **Debugger** (optional agent) -- validates SVG structure, fixes missing `viewBox`, unclosed tags, missing `xmlns`, elements outside the viewBox. Its output is re-sanitized; if re-sanitization fails, the pipeline silently falls back to the pre-debugger SVG.

4. **Renderer** (built-in) -- converts SVG to PNG using the first available backend from a probe order: resvg (CLI), rsvg-convert (CLI), cairosvg (Python). Results are cached; cache is invalidated when all backends fail.

5. **Critic** -- receives the rendered PNG (base64-encoded) along with the SVG source and original prompt. Returns structured JSON with a 1-10 score (following a defined rubric), an issues list, suggestions list, and summary. Skipped on the final iteration since no subsequent generation would use its feedback.

6. **Specialist analysts** (optional) -- layout analysis (alignment, spacing, overlap, margins), color/style analysis (palette coherence, WCAG contrast, color-blind safety), and an evaluator (multi-dimensional metrics). Each returns domain-specific JSON with scores and issue lists. Like the critic, these skip the final iteration.

After each iteration, the sanitized SVG becomes the seed for the next iteration. Critique and analysis outputs accumulate in history lists that are included in subsequent generator prompts.

**Persistent issue detection:** When critique history has 2+ entries, the pipeline compares the latest critique against earlier ones. Issues appearing in both are flagged as "Persistent issues" with extra emphasis in the generator prompt, increasing pressure on the generator to address them.

### Phase 3: Post-loop (run once)

An optional **Refiner** agent receives the final SVG plus a combined feedback summary aggregating all critique scores, issues, suggestions, and analysis dimensions from every iteration. It produces one final improved SVG, which is re-sanitized and re-rendered.

### Backend Protocol

Every agent is a subprocess that reads JSON from stdin and writes JSON to stdout. The contract:

- **Input fields** (vary by role): `prompt`, `svg`, `image_base64`, `feedback_summary`
- **Output:** `{"svg": "..."}` for generators/debugger/refiner; `{"text": "..."}` for critics/analysts

This is the key extensibility mechanism. Any language, model, or tool can serve as a backend by implementing a script that follows this stdin/stdout JSON protocol. The pipeline orchestrator handles subprocess lifecycle, timeout enforcement, stderr capture (truncated to 300 chars for log sanity), and duration tracking.

### Dashboard and Streaming

The FastAPI application provides SSE-streamed iteration events so the UI updates in real time. Jobs are stored in-memory with TTL-based eviction (1 hour) and a hard cap (200 jobs). A "refine" endpoint seeds a new pipeline run from a completed job's final SVG, plan, and critique history. Generation history is persisted to disk with JSON metadata plus SVG/PNG artifacts per iteration.

## Key Decisions

### Subprocess protocol over in-process agents
- **Decision:** Each agent is an independent subprocess communicating via stdin/stdout JSON, rather than an in-process function call or SDK integration.
- **Alternatives considered:** Direct SDK calls (tighter coupling, faster), HTTP microservices (heavier infrastructure), plugin architecture with shared interfaces.
- **Why chosen:** Maximum language and runtime flexibility. The same pipeline orchestrator works with Python scripts calling the Anthropic SDK, Node.js scripts using the OpenCode SDK, or simple echo stubs for testing. Adding a new model provider means writing a single script, not modifying the orchestrator.
- **When to reconsider:** If latency from subprocess spawn becomes a bottleneck (it is not significant for LLM calls that take seconds), or if you need shared GPU memory between agents.

### Skipping critic on the final iteration
- **Decision:** The critic and all analysis agents are skipped on the last iteration of the loop.
- **Alternatives considered:** Always running the critic (provides a final quality score), running a lightweight score-only pass.
- **Why chosen:** The critic's purpose is to drive the next generation. On the final iteration, there is no next generation, so critique output would be wasted compute. The refiner (post-loop) serves the role of final quality improvement.
- **When to reconsider:** If you need a final quality score for automated acceptance/rejection gating, add a score-only critic pass that does not feed back into generation.

### Seed-and-revise over generate-from-scratch
- **Decision:** Each iteration receives the previous iteration's SVG as seed, with explicit instructions to preserve working structure and only modify what the feedback targets.
- **Alternatives considered:** Generating from scratch each iteration (simpler prompt), providing only a diff of changes needed.
- **Why chosen:** From-scratch generation loses improvements made in earlier iterations. The seed approach accumulates quality across iterations. The explicit "do not start from a blank canvas" instruction is necessary because LLMs default to generating complete new outputs.
- **When to reconsider:** If the seed SVG becomes so large that it dominates the context window, or if early iterations produce fundamentally flawed structure that poisons later iterations (in which case a "restart from scratch" escape hatch would help).

### Upfront command resolution to prevent settings drift
- **Decision:** All agent commands, model selections, and timeouts are resolved once at pipeline start, before the iteration loop begins.
- **Alternatives considered:** Resolving per-iteration (would pick up mid-run settings changes).
- **Why chosen:** A dashboard user changing settings mid-run could cause inconsistent behavior -- e.g., switching the generator model between iteration 3 and 4. Snapshot-at-start gives deterministic runs.
- **When to reconsider:** If you want a "live tuning" mode where the operator can adjust parameters mid-run (would need explicit opt-in and careful state management).

### Centralized prompt definitions
- **Decision:** All system prompts live in a single `prompts.py` module rather than being embedded in backend scripts or configuration files.
- **Alternatives considered:** Per-backend prompt files, prompts in YAML/JSON config, prompts embedded in each backend script.
- **Why chosen:** When prompts are scattered, they drift. Centralizing them means a single place to audit, version, and update the instructions given to every agent role. Backend scripts receive the prompt as input, not as their own responsibility.
- **When to reconsider:** If different backend modes need fundamentally different prompting strategies (e.g., a fine-tuned model that needs minimal prompting vs. a general model that needs detailed instructions).

## Pitfalls & Gotchas

1. **Debugger output fallback is non-negotiable.** The debugger agent may return invalid SVG, SVG wrapped in XML declarations (`<?xml ...?>`), or SVG with markdown fencing. The pipeline must strip XML declarations, re-sanitize, and fall back to the pre-debugger SVG if re-sanitization fails. Without this fallback, a misbehaving debugger crashes the entire pipeline. Track this with an `accepted_output: False` flag in debug traces so you can monitor debugger reliability over time.

2. **Subprocess stdout must be pure JSON.** If any backend script writes non-JSON content to stdout (debug prints, warnings, library banners), the orchestrator's JSON parse fails and the agent call errors out. All backends must use stderr for diagnostics, never stdout. Echo/stub backends must be carefully minimal. This is the single most common failure mode when adding a new backend.

3. **Analysis agents skip resolution when iterations=1.** If optional agents (layout, color, evaluator) are enabled but iterations is set to 1, their command environment variables are never resolved. This is intentional -- it prevents failing on a misconfigured-but-unused agent. But it means you cannot catch configuration errors for optional agents in single-iteration mode; they only surface when iterations > 1.

4. **Persistent issue detection requires 2+ critique entries.** The persistent-issue comparison only activates when critique history has at least 2 entries, meaning iterations must be >= 3 (iteration 1 produces critique 1, iteration 2 produces critique 2, iteration 3 is the first to benefit from persistent-issue emphasis). With only 2 iterations, persistent issues are never flagged.

5. **Custom instructions must be appended last.** User-provided custom instructions are placed at the end of the generator prompt with explicit framing: "If any earlier visual or design guidance conflicts, follow these custom instructions." If they are placed earlier, planner output or example guidance injected afterward may override them. Prompt ordering is semantic priority for LLMs.

6. **SVG sanitization must be non-negotiable and universal.** Every SVG entering the pipeline -- from generators, debuggers, refiners, and user uploads -- must pass through sanitization. It is tempting to skip sanitization for "trusted" internal agents, but LLMs can be prompted to produce `<script>` tags or event handlers, and the output is rendered in a browser. Treat every SVG as untrusted input.

7. **Render backend cache invalidation is one-directional.** The renderer caches which backends are available after the first successful probe. The cache is only invalidated when all backends fail. This means a newly installed preferred renderer (e.g., resvg installed after the process started) will not be detected until either all current backends fail or the process restarts. If you need hot-reloading of renderer backends, add a manual cache-clear endpoint.

8. **Atomic file writes for history persistence.** Writing generation history directly to the target file risks corruption on crash. Write to a `.tmp` file first, then atomically rename. Additionally, when pruning old history entries, validate that entry IDs resolve to paths within the assets directory before calling `rmtree` -- a corrupted entries file with crafted IDs could otherwise delete arbitrary directories.

9. **Refiner feedback summary must aggregate, not just concatenate.** The refiner receives a summary built from all critique history and analysis history. Simply concatenating all feedback produces a noisy, contradictory prompt. The summary builder should structure feedback by dimension (layout issues, color issues, completeness) and highlight which issues persisted vs. which were resolved across iterations.

## Recipe

1. **Define the agent roles and their I/O contracts.** Enumerate each agent role (decomposer, planner, generator, debugger, critic, layout analyst, color analyst, evaluator, refiner) and specify for each: what JSON fields it receives on stdin, what JSON fields it returns on stdout, and whether it is required or optional. Document this in a single protocol specification.

2. **Implement the subprocess invocation layer.** Write a function (e.g., `invoke_backend(command, input_data, timeout)`) that serializes input to JSON, spawns the subprocess, writes to stdin, reads stdout, parses JSON output, captures stderr (truncated for log sanity), enforces a timeout, and tracks duration. This function is the only interface between the orchestrator and agents.

3. **Build stub/echo backends first.** For each agent role, create a deterministic stub that returns canned JSON responses. These require no API keys, no model access, and no network. Use them to develop and test the full pipeline end-to-end before integrating real models.

4. **Implement the sanitizer.** Build an SVG sanitizer that operates on parsed XML (not regex). Define an allowlist of safe elements and attributes. Strip everything not on the allowlist. Reject external URL references in href/src/data attributes; permit only internal fragment references (`#id`, `url(#id)`). Run this on every SVG at every pipeline boundary.

5. **Implement the renderer.** Write a renderer that probes for available SVG-to-PNG backends in preference order (resvg > rsvg-convert > cairosvg). Cache the probe result. Invalidate the cache when all backends fail. The renderer takes SVG string input and returns PNG bytes.

6. **Build the iteration loop.** Implement the core loop: for each iteration, call the generator, sanitize, optionally debug (with fallback), render to PNG, then (if not the final iteration) call the critic and optional analysts. Accumulate critique history and analysis history. Feed the sanitized SVG as seed to the next iteration. After the loop, optionally call the refiner with an aggregated feedback summary.

7. **Add persistent issue detection.** After accumulating 2+ critique entries, compare the latest critique's issues against earlier ones. Flag matches as persistent issues and inject them with extra emphasis into the generator prompt for the next iteration.

8. **Resolve all agent commands upfront.** Before entering the iteration loop, resolve every agent's command path, model selection, and timeout from the current settings. Store these resolved values and use them throughout the run. Do not re-read settings mid-pipeline.

9. **Write centralized system prompts.** Define all agent system prompts in a single module. Each prompt should specify the exact output format (JSON schema), evaluation criteria (for critics), and behavioral constraints (for generators: "do not start from a blank canvas," "40px edge padding," "explicit fill/stroke on every element").

10. **Add the streaming dashboard.** Wrap the pipeline in a web server (e.g., FastAPI) with SSE streaming for real-time iteration progress. Implement job management with TTL-based eviction. Add a "refine" endpoint that seeds a new pipeline run from a completed job's final state. Persist generation history to disk with atomic writes.

11. **Implement real model backends.** For each model provider you want to support, write a backend script that follows the subprocess JSON protocol. For VLM-based critics, construct multimodal messages with the base64 PNG as an image content block. For text-based generators, construct prompts from the input fields. Each backend is a standalone script with no dependency on the orchestrator code.

12. **Add security hardening.** Validate all file uploads (SVG via XML parse, PNG via signature bytes, size cap). Guard against path traversal in any file operations using `resolve()` and `relative_to()` checks. Use separate locks for each shared mutable resource (settings, jobs, history). Bind to Tailscale IP for private network deployment.

## Verification

- **End-to-end with echo backends:** Run the full pipeline with echo/stub backends and verify that all phases execute, SSE events stream correctly, history is persisted, and the final SVG/PNG artifacts are written. This validates orchestration logic without any model dependency.

- **Sanitizer coverage:** Pass known-malicious SVG through the sanitizer (containing `<script>`, `onclick`, external `href`, `<foreignObject>`) and verify all are stripped. Pass valid SVG with internal fragment refs (`url(#gradient)`) and verify they are preserved.

- **Debugger fallback:** Feed the debugger a backend that returns invalid XML. Verify the pipeline falls back to the pre-debugger SVG and logs `accepted_output: False` in the debug trace, without crashing.

- **Iteration accumulation:** Run a 3+ iteration pipeline and verify that: (a) critique history grows with each iteration, (b) the generator prompt for iteration N includes all N-1 previous critiques, (c) persistent issues are flagged starting from iteration 3, (d) the seed SVG changes between iterations.

- **Settings snapshot:** Start a multi-iteration run, change settings via the dashboard mid-run, and verify the running pipeline is unaffected (uses the settings captured at start).

- **Atomic history writes:** Kill the process mid-write (or simulate with a test) and verify the history file is either the old version or the new version, never a partial write.

- **Subtle failure to watch for:** The pipeline "works" but quality does not improve across iterations. This usually means the generator is ignoring the critique history (prompt too long, critique buried in context) or the seed SVG instruction is missing (generator starts fresh each time). Check that critique history and the "do not start from blank canvas" instruction are present in the generator's actual input by enabling debug mode and inspecting the trace events.
