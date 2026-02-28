#!/usr/bin/env python3
"""Search knowledge entries by keyword, tag, domain, type, and confidence.

Usage:
    python search.py --tag edfa
    python search.py --domain optical-networking --confidence high
    python search.py --query "digital twin"
    python search.py --type pattern --tag multi-agent

Multiple flags are ANDed together.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers (copied from validate.py — scripts are standalone)
# ---------------------------------------------------------------------------

def get_root() -> Path:
    """Return the knowledge_framework root directory relative to this script."""
    return Path(__file__).resolve().parent.parent


def parse_frontmatter(text: str) -> Tuple[Optional[Dict], List[str]]:
    """Parse YAML frontmatter between --- markers.

    Returns (parsed_dict_or_None, list_of_parse_errors).
    """
    errors: List[str] = []
    lines = text.split("\n")

    # Find opening ---
    if not lines or lines[0].strip() != "---":
        return None, ["No YAML frontmatter found (file must start with ---)"]

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, ["YAML frontmatter not closed (missing closing ---)"]

    fm_lines = lines[1:end_idx]
    data: Dict = {}

    for line in fm_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Handle key: value
        match = re.match(r"^(\w[\w-]*)\s*:\s*(.*)", line)
        if not match:
            continue

        key = match.group(1).strip()
        raw_value = match.group(2).strip()

        # Parse list values: [item1, item2, ...]
        if raw_value.startswith("[") and raw_value.endswith("]"):
            inner = raw_value[1:-1].strip()
            if inner:
                items = [item.strip().strip("'\"") for item in inner.split(",")]
                data[key] = [item for item in items if item]
            else:
                data[key] = []
        # Parse quoted strings
        elif (raw_value.startswith('"') and raw_value.endswith('"')) or \
             (raw_value.startswith("'") and raw_value.endswith("'")):
            data[key] = raw_value[1:-1]
        # Plain value
        else:
            # Handle inline comment: value  # comment
            comment_match = re.match(r"^([^#]+?)(?:\s+#.*)?$", raw_value)
            if comment_match:
                data[key] = comment_match.group(1).strip()
            else:
                data[key] = raw_value

    return data, errors


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------

def get_body(text: str) -> str:
    """Return the markdown body after the frontmatter."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text

    fm_count = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            fm_count += 1
            if fm_count == 2:
                return "\n".join(lines[i + 1:])

    return text


def get_summary(text: str) -> str:
    """Extract the first non-empty line from the ## Problem section, truncated.

    Falls back to the first meaningful body line if no Problem section found.
    """
    lines = text.split("\n")
    in_problem = False
    fm_count = 0
    body_started = False

    for line in lines:
        if line.strip() == "---":
            fm_count += 1
            if fm_count == 2:
                body_started = True
            continue
        if not body_started:
            continue

        if re.match(r"^##\s+Problem\b", line):
            in_problem = True
            continue

        if in_problem:
            if re.match(r"^##\s+", line):
                break
            stripped = line.strip()
            if stripped:
                if len(stripped) > 120:
                    return stripped[:117] + "..."
                return stripped

    # Fallback: first non-heading body line
    body = get_body(text)
    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if len(stripped) > 120:
            return stripped[:117] + "..."
        return stripped

    return "(no summary)"


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------

def load_entries(root: Path) -> List[Tuple[Path, Dict, str]]:
    """Load all .md entries from entries/ and return (path, frontmatter, text)."""
    entries_dir = root / "entries"
    if not entries_dir.is_dir():
        return []

    results = []
    for md_file in sorted(entries_dir.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if fm is not None:
            results.append((md_file, fm, text))
    return results


def matches_filter(
    fm: Dict,
    text: str,
    tag: Optional[str],
    domain: Optional[str],
    entry_type: Optional[str],
    confidence: Optional[str],
    query: Optional[str],
) -> bool:
    """Check whether an entry matches all provided filters (AND logic)."""
    if tag is not None:
        tags = fm.get("tags", [])
        if not isinstance(tags, list):
            tags = [tags]
        if tag.lower() not in [t.lower() for t in tags]:
            return False

    if domain is not None:
        if fm.get("domain", "").lower() != domain.lower():
            return False

    if entry_type is not None:
        if fm.get("type", "").lower() != entry_type.lower():
            return False

    if confidence is not None:
        if fm.get("confidence", "").lower() != confidence.lower():
            return False

    if query is not None:
        if query.lower() not in text.lower():
            return False

    return True


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_result(root: Path, path: Path, fm: Dict, text: str) -> str:
    """Format a single search result for display."""
    rel = path.relative_to(root)
    title = fm.get("title", rel.stem)
    tags = fm.get("tags", [])
    if isinstance(tags, list):
        tag_str = ", ".join(tags)
    else:
        tag_str = str(tags)
    summary = get_summary(text)

    lines = [
        f"Title      : {title}",
        f"Path       : {rel}",
        f"Type       : {fm.get('type', '')}",
        f"Domain     : {fm.get('domain', '')}",
        f"Confidence : {fm.get('confidence', '')}",
        f"Tags       : {tag_str}",
        f"Problem    : {summary}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search knowledge entries by keyword, tag, domain, type, and confidence.",
    )
    parser.add_argument("--tag", help="Match entries containing this tag")
    parser.add_argument("--domain", help="Match entries with this domain")
    parser.add_argument("--type", help="Match entries with this type")
    parser.add_argument("--confidence", help="Match entries with this confidence level")
    parser.add_argument("--query", "-q", help="Full-text search in file content")

    args = parser.parse_args()

    # If no filters provided, show help
    if not any([args.tag, args.domain, args.type, args.confidence, args.query]):
        parser.print_help()
        return 0

    root = get_root()
    entries = load_entries(root)

    if not entries:
        print("No entries found in entries/")
        return 1

    matches = []
    for path, fm, text in entries:
        if matches_filter(fm, text, args.tag, args.domain, args.type, args.confidence, args.query):
            matches.append((path, fm, text))

    if not matches:
        print("No matching entries found.")
        return 1

    print(f"Found {len(matches)} match(es):\n")
    for i, (path, fm, text) in enumerate(matches):
        print(format_result(root, path, fm, text))
        if i < len(matches) - 1:
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
