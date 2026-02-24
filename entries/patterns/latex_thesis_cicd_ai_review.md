---
title: "CI/CD Pipeline for LaTeX Thesis with AI-Powered Academic Review"
type: pattern
tags: [latex, thesis, ci-cd, github-actions, overleaf, ai-review, academic-writing, claude-code-action]
domain: research-methods
created: 2026-02-24
updated: 2026-02-24
confidence: medium
complexity: high
related: []
---

# CI/CD Pipeline for LaTeX Thesis with AI-Powered Academic Review

## Problem

PhD thesis writing in LaTeX suffers from two quality gaps that slow down the final push to submission. First, structural integrity problems (missing figures, broken cross-references, undefined citations) accumulate silently in Overleaf and are only discovered during manual compilation or late-stage review. Second, academic feedback on content quality (argument strength, logical flow, completeness of claims) depends entirely on supervisor availability. You want a system where every change to the thesis is automatically compiled, integrity-checked, and reviewed for academic substance -- with the review acting like a thesis examiner, not a code linter.

An additional complication: the thesis lives on Overleaf for collaborative editing but needs GitHub for CI/CD. Overleaf's Git integration pushes rapidly (potentially every few seconds during active editing), which can overwhelm a naive CI setup.

## Context

- **Project**: PhD thesis at Trinity College Dublin, LaTeX-based, 8+ chapters
- **Primary editor**: Overleaf (used by author and supervisor for collaborative editing)
- **CI platform**: GitHub Actions, with Overleaf's Git bridge pushing to a dedicated `overleaf` branch
- **AI reviewer**: `anthropics/claude-code-action@v1` (GitHub Actions wrapper for Claude Code)
- **LaTeX toolchain**: `xu-cheng/latex-action@v3` with `pdflatex -shell-escape` and `latexmk`
- **Key constraint**: The Overleaf thesis template has pre-existing non-fatal LaTeX errors that produce valid PDFs but non-zero exit codes
- **Assumed knowledge**: Familiarity with GitHub Actions, basic LaTeX, and Overleaf's Git sync feature

## Approach

The pipeline is built as five independent GitHub Actions workflows, each with a single responsibility. They trigger on different events and have clear blocking/non-blocking semantics.

### 1. Overleaf Sync (overleaf-sync.yml)

Triggers on pushes to the `overleaf` branch. Creates or updates a single PR from `overleaf` to `main`. The critical design element is a **debounce pattern** to handle Overleaf's rapid auto-save pushes:

- The workflow uses `concurrency: { group: overleaf-sync, cancel-in-progress: true }` combined with a `sleep 600` (10 minutes) as the first step
- Each new push cancels the previous sleeping run, so only the last push after a 10-minute quiet period actually executes
- The PR creation step checks for existing open PRs from `overleaf` to `main` using `gh pr list` and updates the existing one rather than creating duplicates
- The PR body groups changed files by chapter directory for easy scanning

### 2. LaTeX Build (latex-build.yml) -- Blocking

Triggers on PRs to `main`. Compiles `main.tex` and uploads the thesis PDF as an artifact. Also generates a `latexdiff` PDF showing tracked changes against `main`. The latexdiff step has a two-level fallback chain: try flattened diff first, then main.tex-only diff, then produce a dummy "diff failed" document. The PR fails if compilation fails (with caveats -- see Pitfalls #5 about exit codes).

### 3. Thesis Quality Checks (thesis-checks.yml) -- Partially Blocking

Triggers on PRs to `main`. Runs two check scripts after compilation:

**Bibliography check** (bash script): Parses `main.blg` for undefined citations (blocking), unused bib entries (warning), duplicate BibTeX keys (warning), and other BibTeX warnings. Uses `checkcites` for unused entry detection. Only undefined citations cause PR failure; all other findings are informational.

**Figures and references check** (Python script): Parses all `.tex` files for `\includegraphics`/`\includesvg` paths and verifies they exist on disk (blocking). Checks `\label`/`\ref` integrity -- undefined refs are blocking, unreferenced labels and empty captions are warnings. Crucially, this script **understands figure path macros** by parsing `preamble.tex` for `\newcommand{\xxxfig}[1]{path/#1}` patterns, so it can resolve `\edfafig{gain_spectrum.png}` to `4_edfa_modeling/figures/gain_spectrum.png`.

Both checks post a combined "Thesis Quality Report" as a PR comment, updating the same comment on re-runs by searching for a marker string.

### 4. AI Academic Reviewer (reviewer.yml) -- Never Blocking

Uses `anthropics/claude-code-action@v1` with two modes:

- **Automatic**: On every PR to `main`, assembles context from the reviewer prompt file, thesis metadata, and inline instructions. Claude reads the PR diff, reads per-chapter `CHAPTER_CONTEXT.md` files, reads the full `.tex` content, then posts a review as a thesis examiner would.
- **Interactive**: Responds to `@claude` mentions in PR comments for follow-up questions.

Always runs with `continue-on-error: true` so reviewer failures never block merging. Authenticated via `CLAUDE_CODE_OAUTH_TOKEN`.

### 5. Progress Tracking (progress-update.yml)

Triggers when PRs merge to `main`. Detects which chapter directories were touched and updates `STATUS.md` with the last PR reference and date. Commits as `github-actions[bot]`.

### Context File Hierarchy

Three layers of context files provide progressively specific awareness to both AI reviewers and human contributors:

- **CLAUDE.md** (repo root): Build instructions, repo structure, key conventions, CI overview. Auto-loaded by `claude-code-action`.
- **THESIS.md** (repo root): Thesis metadata (title, supervisor, institution), research questions, chapter overview, notation conventions, style guide, key technical terms.
- **CHAPTER_CONTEXT.md** (per chapter directory): Source publication, key contributions, experimental setup, key results, known issues (e.g., revision markers, reviewer exchange comments), and related chapters.

### Reviewer Prompt Design

The reviewer prompt is the most carefully engineered piece. It must steer Claude away from its default tendency to review `.tex` diffs as code. The prompt includes:

- An explicit "What You Review" section: arguments, claims, technical clarity, logical flow, completeness, academic rigor, language quality
- An explicit "What You Do NOT Review" section: LaTeX syntax, macros, compilation issues, bibliography formatting (CI checks handle those)
- Academic-oriented review tags: `CLARITY`, `ARGUMENT`, `STRUCTURE`, `TECHNICAL`, `CITATION`, `COMPLETENESS`, `STYLE`
- Severity levels: `suggestion`, `important`, `critical`
- Instructions to read full chapter content (not just the diff) and to read `CHAPTER_CONTEXT.md` first
- A target of 5-15 comments per review, prioritizing substance over style

### Helper Scripts

- **strip-latex.sh**: Converts `.tex` to plaintext by stripping comments, commands, environments, math, citations. Keeps prose content. Useful for feeding text to reviewers or word-count tools.
- **review-summary.sh**: Scans `.tex` files for draft annotations (`\todo`, `\fixme`, `\placeholder`, `\source`, etc.) and `% TODO` comments. Reports counts by tag and by file.

## Key Decisions

### Debounce at workflow level vs. branch-level batching
Considered using a scheduled workflow (e.g., every 30 minutes) to batch Overleaf pushes. Chose the `concurrency + sleep` debounce pattern because it is event-driven -- the PR appears within 10 minutes of the last edit, not on a fixed schedule. The tradeoff is that a single stalled sleep holds a GitHub Actions runner for 10 minutes.

### Separate workflows vs. single monolithic workflow
Each of the five concerns (sync, build, checks, review, progress) is a separate workflow file. This was chosen over a single workflow because: (a) they trigger on different events, (b) the reviewer should never block the build, (c) individual workflows can be re-run independently, and (d) the permissions model is cleaner (the reviewer needs different tokens than the build).

### AI reviewer as non-blocking by design
The reviewer workflow uses `continue-on-error: true` at the job level. This was a deliberate choice -- AI review is advisory, not gatekeeping. Build failures and quality check failures (undefined citations, missing figures) are blocking; academic content feedback is not. This prevents flaky API issues or prompt engineering regressions from stalling thesis progress.

### Prompt injection via `prompt` input vs. `--system-prompt`
Attempted to pass the reviewer prompt as a system prompt via `claude_args`. This failed due to shell escaping issues with multiline markdown (see Pitfall #4). The final design uses the `prompt` input parameter and concatenates context files inline: `cat .github/prompts/reviewer.md + THESIS.md + inline instructions`. The action's auto-loading of `CLAUDE.md` provides the baseline repo context.

### `\providecommand` over `\newcommand` for figure path macros
After encountering "Command already defined" errors when chapters defined macros already present in `preamble.tex`, the convention was established to always use `\providecommand` for figure path macros in chapter files. This is safe because `\providecommand` silently skips redefinition while `\newcommand` errors.

### Draft annotation system with compile-time toggle
Seven annotation commands (`\todo`, `\fixme`, `\placeholder`, `\done`, `\note`, `\added`, `\source`) are controlled by a `\drafttrue`/`\draftfalse` toggle. In draft mode, each renders in a distinct color. In final mode, they are suppressed (or pass through text, for `\added`). This was chosen over comment-only annotations because colored in-PDF annotations are visible to collaborators viewing the PDF without source access.

## Pitfalls & Gotchas

### 1. `--allowedTools` crashes claude-code-action
Passing `--allowedTools` via `claude_args` conflicts with the action's internal tool management (it sets `ALLOWED_TOOLS` as an environment variable internally). Claude Code exits with code 1 and no useful error message. Diagnosing this required reading the action's source code. **Fix**: do not pass `--allowedTools` in `claude_args`; use the action's own input parameters if tool restrictions are needed.

### 2. `continue-on-error` at workflow level is silently ignored
GitHub Actions accepts `continue-on-error: true` at the workflow root level without a YAML validation error, but it has no effect. The property only works at the job or step level. The reviewer job failures caused the entire workflow to fail until this was moved to the job definition. **Fix**: always set `continue-on-error` on individual jobs or steps, never at the workflow root.

### 3. `max_turns` parameter instability in claude-code-action
Four iterations were needed to get `max_turns` right. Using it as a dedicated action input may cause AJV schema validation crashes. Moving it to `claude_args: '--max-turns 10'` crashed differently. Increasing the value was insufficient because the review needed more turns than expected. **Fix**: remove `max_turns` entirely and let Claude finish naturally. The default is unlimited, and a thesis review typically completes within a reasonable number of turns.

### 4. `--system-prompt` with multiline markdown breaks shell escaping
Attempting to pass the reviewer prompt (containing backticks, pipes, special characters) as `claude_args: '--system-prompt "${{ steps.context.outputs.SYS_PROMPT }}"'` fails because the content passes through YAML interpolation, then shell expansion, then CLI argument parsing. Each layer interprets different characters. **Fix**: do not use `--system-prompt` in `claude_args`. Use the `prompt` input for injecting context, and let `CLAUDE.md` auto-loading handle baseline instructions.

### 5. `latexmk` exits with code 12 despite producing a valid PDF
Overleaf thesis templates often have pre-existing non-fatal errors (undefined commands from unused packages, deprecated constructs like a `\cosupervisor` command). These cause `latexmk` to exit with code 12 even though a perfectly valid PDF is generated. **Fix**: use the `-f` flag to force `latexmk` through first-pass errors, set `continue-on-error: true` on the compilation step, and add an explicit "Verify PDF was generated" step that checks for `main.pdf` existence. The verification step is the actual quality gate, not the compilation exit code.

### 6. Markdown backticks in JS template literals cause SyntaxError
The check scripts output markdown-formatted reports containing code blocks (triple backticks). When these reports are interpolated directly into `actions/github-script` template literals (`` const report = `${{ outputs.report }}`; ``), the markdown backticks are parsed as JS template literal delimiters, causing errors like "Numeric separators are not allowed." **Fix**: pass reports through environment variables and access them via `process.env`:

```yaml
env:
  BIB_REPORT: ${{ steps.bib_check.outputs.report }}
with:
  script: |
    const bibReport = process.env.BIB_REPORT || '';
```

### 7. `set -e` kills exit code capture in GitHub Actions bash steps
GitHub Actions bash steps run with `set -e` by default. If a script exits non-zero, the shell terminates before `$?` can be captured on the next line. **Fix**: use the `||` pattern to prevent `set -e` from triggering:

```bash
# Wrong: set -e kills the shell before $? is read
bash script.sh > /dev/null 2>&1
echo "exit_code=$?" >> "$GITHUB_OUTPUT"

# Right: || prevents set -e from triggering
ec=0; bash script.sh > /dev/null 2>&1 || ec=$?
echo "exit_code=$ec" >> "$GITHUB_OUTPUT"
```

### 8. Missing `contents: write` permission for PR comments
Claude Code Action needs `contents: write` permission to post PR comments via the `gh` CLI. Providing only `pull-requests: write` is insufficient -- `gh pr comment` requires both. **Fix**: ensure the reviewer workflow has both `contents: write` and `pull-requests: write` in its permissions block.

### 9. AI reviewer defaults to code review on LaTeX diffs
Without explicit steering, Claude reviews `.tex` file diffs by commenting on LaTeX syntax, macro choices, label naming conventions, and citation formatting -- treating LaTeX as code. The first prompt version with a generic `GRAMMAR` tag and generic guidelines produced exactly this behavior. **Fix**: the prompt requires an explicit "What You Do NOT Review" exclusion list, instructions to read the full chapter (not just the diff), per-chapter context files, and academic-oriented review tags (`ARGUMENT`, `COMPLETENESS`). Replace `GRAMMAR` with tags that orient Claude toward examiner-style feedback.

### 10. Reviewer exchange comments leak into compiled PDF
Chapter files may contain uncommented `\textcolor{blue}` inline text from supervisor/student discussions that render in the final PDF. The CI pipeline catches problems flagged by the draft annotation system (`\todo`, `\fixme`, etc.) but does not detect free-form colored text used for reviewer exchanges. **Mitigation**: this is a known gap. Possible future fix: add a CI check that greps for `\textcolor` usage outside of known annotation macros.

### 11. `\newcommand` vs `\providecommand` for figure macros
If a chapter defines a figure path macro with `\newcommand{\edfafig}` and `preamble.tex` also defines it, compilation fails with "Command already defined." Using `\providecommand` avoids this because it silently skips redefinition. **Fix**: always use `\providecommand` (or `\renewcommand` if intentional override is needed) for figure path macros in chapter files. The figure check script handles both variants when parsing macro definitions.

## Recipe

### Prerequisites
- A LaTeX thesis project on Overleaf with Git sync enabled (pushes to an `overleaf` branch on GitHub)
- A GitHub repository with Actions enabled
- A `CLAUDE_CODE_OAUTH_TOKEN` secret for the AI reviewer (obtain from Anthropic's claude-code-action documentation)

### Step 1: Set up the Overleaf sync workflow
Create `.github/workflows/overleaf-sync.yml`. Configure it to trigger on `push` to the `overleaf` branch. Add the concurrency group with `cancel-in-progress: true` and a `sleep 600` as the first step. The main job should use `gh pr list` to check for an existing open PR from `overleaf` to `main` and either create or update it. Grant `contents: write` and `pull-requests: write` permissions.

### Step 2: Set up the LaTeX build workflow
Create `.github/workflows/latex-build.yml`. Trigger on `pull_request` to `main`. Use `xu-cheng/latex-action@v3` with `root_file: main.tex` and `args: -pdf -shell-escape -f` (the `-f` flag is critical for templates with non-fatal errors). Set `continue-on-error: true` on the compilation step. Add a subsequent step that verifies `main.pdf` exists -- this step determines actual build success. Upload the PDF as an artifact. Optionally, add a `latexdiff` step with a fallback chain.

### Step 3: Create the check scripts
Write a bibliography check script (bash) that parses `main.blg` for undefined citations (exit 1) and reports unused entries, duplicate keys, and other warnings (exit 0). Write a figure/reference check script (Python) that parses `preamble.tex` for figure path macro definitions, scans all `.tex` files for `\includegraphics`/`\includesvg` calls with balanced-brace parsing, verifies file existence with extension fallback (.png, .jpg, .pdf, .svg, .eps), and checks `\label`/`\ref` integrity. Both scripts should output their reports in markdown format.

### Step 4: Set up the thesis checks workflow
Create `.github/workflows/thesis-checks.yml`. Trigger on `pull_request` to `main`. Depend on the build workflow completing. Run both check scripts, capturing exit codes with the `ec=0; cmd || ec=$?` pattern. Post a combined "Thesis Quality Report" as a PR comment using `actions/github-script`, passing report content via environment variables (not template literal interpolation). Search for an existing comment by marker text and update it on re-runs.

### Step 5: Create the context file hierarchy
Write `CLAUDE.md` at the repo root with build instructions, repo structure, and conventions. Write `THESIS.md` with thesis metadata, research questions, chapter overview, and style guide. For each chapter directory, write a `CHAPTER_CONTEXT.md` with source publication, contributions, experimental setup, known issues, and related chapters.

### Step 6: Write the reviewer prompt
Create `.github/prompts/reviewer.md` with explicit "What You Review" and "What You Do NOT Review" sections. Define review tags oriented toward academic concerns (`CLARITY`, `ARGUMENT`, `STRUCTURE`, `TECHNICAL`, `CITATION`, `COMPLETENESS`, `STYLE`). Define severity levels. Instruct the reviewer to read `CHAPTER_CONTEXT.md` first, then full chapter content, then provide 5-15 comments prioritizing substance over style.

### Step 7: Set up the reviewer workflow
Create `.github/workflows/reviewer.yml`. Trigger on `pull_request` to `main` and `issue_comment` (for `@claude` mentions). Use `anthropics/claude-code-action@v1`. Set `continue-on-error: true` at the job level. Pass context via the `prompt` input by concatenating the reviewer prompt file and thesis metadata. Grant `contents: write` and `pull-requests: write` permissions. Authenticate with `CLAUDE_CODE_OAUTH_TOKEN`. Do not pass `--allowedTools`, `--system-prompt`, or `--max-turns` via `claude_args`.

### Step 8: Set up the progress tracking workflow
Create `.github/workflows/progress-update.yml`. Trigger on `push` to `main` (i.e., after PR merges). Detect which chapter directories were modified. Update `STATUS.md` with the last PR reference and date. Commit as `github-actions[bot]`.

### Step 9: Establish macro conventions
In `preamble.tex`, define figure path macros using `\providecommand`. Document the convention that chapter files must also use `\providecommand` (never `\newcommand`) for any macros that might conflict with preamble definitions.

### Step 10: Create helper scripts
Write `strip-latex.sh` for converting `.tex` to plaintext (stripping comments, commands, environments, math). Write `review-summary.sh` for scanning draft annotations and reporting counts by tag and file. Place both in a `scripts/` directory.

## Verification

**Overleaf sync debounce**: Make several rapid edits in Overleaf (within a 2-minute window). Verify that only one GitHub Actions run completes for the `overleaf-sync` workflow, and that a single PR is created or updated (not multiple PRs). Check the Actions log to confirm earlier runs show as "cancelled."

**LaTeX build**: Push a change that introduces a deliberate compilation error (e.g., `\undefinedcommand`). Verify the PR shows a failing build check. Fix the error and push again. Verify the build passes and the PDF artifact is downloadable.

**Quality checks**: Introduce a `\ref{fig:nonexistent}` in a chapter file. Verify the PR comment shows a blocking error for an undefined reference. Add a `\cite{nonexistent_key}` and verify the bibliography check flags it as blocking.

**AI reviewer**: Open a PR that modifies chapter content. Verify that Claude posts a review comment with academic-oriented feedback (argument quality, completeness, technical claims) rather than LaTeX syntax comments. Verify the review uses the defined tags (`ARGUMENT`, `CLARITY`, etc.) and severity levels. Comment `@claude Is the argument in Section 3.2 sufficiently supported by the experimental data?` and verify an interactive response.

**Non-blocking reviewer**: Temporarily break the reviewer (e.g., invalid token). Verify the PR's other checks still pass and the PR is mergeable despite the reviewer job failing.

**Subtle failure mode**: The system appears to work but the reviewer is actually doing code review instead of academic review. Check the first few reviews carefully: if comments mention "consider renaming this label" or "this macro could be simplified," the prompt needs stronger steering (see Pitfall #9). The reviewer should comment on things like "this claim in paragraph 3 needs stronger evidence" or "the transition between these two sections is unclear."
