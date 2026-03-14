---
description: Google Search via Gemini CLI — use for any web search, API docs lookup, or internet research
allowed-tools: Bash(gemini:*), Bash(set:*)
---

You are performing a Google Search–grounded query using the Gemini CLI in headless mode.

## Instructions

The user (or you, as the orchestrating agent) needs information from the web. Use Gemini CLI's built-in Google Search integration to find it.

### Input

The argument `$ARGUMENTS` contains the search query or research question.

### Execute

Run the following command:

```bash
set -o pipefail
gemini -p "$ARGUMENTS" --output-format json -y 2>&1 | python3 -c '
import sys, json
raw = sys.stdin.read()
if not raw.strip():
    print("ERROR: gemini returned no output", file=sys.stderr)
    raise SystemExit(1)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print(raw, end="")
    raise SystemExit(0)
value = data.get("response") if isinstance(data, dict) else data
if isinstance(value, str):
    print(value)
else:
    print(json.dumps(value, ensure_ascii=False, indent=2))
'
```

If the query needs file context, pipe it in using input redirection:

```bash
set -o pipefail
gemini -p "$ARGUMENTS" --output-format json -y < "relevant_file.py" 2>&1 | python3 -c '
import sys, json
raw = sys.stdin.read()
if not raw.strip():
    print("ERROR: gemini returned no output", file=sys.stderr)
    raise SystemExit(1)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print(raw, end="")
    raise SystemExit(0)
value = data.get("response") if isinstance(data, dict) else data
if isinstance(value, str):
    print(value)
else:
    print(json.dumps(value, ensure_ascii=False, indent=2))
'
```

### Output

- Present the results concisely to the user
- If Gemini returned search-grounded information, note that it came from Google Search
- If the results are insufficient, suggest refining the query
