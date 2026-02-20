#!/usr/bin/env python3
"""Rebuild index.md and tags.md from all entries in the knowledge framework.

Scans all .md files under entries/, parses their YAML frontmatter, and
generates:
  - index.md  : a sorted markdown table of all entries
  - tags.md   : entries grouped under each tag heading

Usage:
    python rebuild_index.py
"""

import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_root() -> Path:
    """Return the knowledge_framework root directory relative to this script."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# YAML frontmatter parser (identical to validate.py -- no pyyaml dependency)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> Optional[Dict]:
    """Parse YAML frontmatter between --- markers. Returns dict or None."""
    lines = text.split("\n")

    if not lines or lines[0].strip() != "---":
        return None

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None

    fm_lines = lines[1:end_idx]
    data: Dict = {}

    for line in fm_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        match = re.match(r"^(\w[\w-]*)\s*:\s*(.*)", line)
        if not match:
            continue

        key = match.group(1).strip()
        raw_value = match.group(2).strip()

        if raw_value.startswith("[") and raw_value.endswith("]"):
            inner = raw_value[1:-1].strip()
            if inner:
                items = [item.strip().strip("'\"") for item in inner.split(",")]
                data[key] = [item for item in items if item]
            else:
                data[key] = []
        elif (raw_value.startswith('"') and raw_value.endswith('"')) or \
             (raw_value.startswith("'") and raw_value.endswith("'")):
            data[key] = raw_value[1:-1]
        else:
            comment_match = re.match(r"^([^#]+?)(?:\s+#.*)?$", raw_value)
            if comment_match:
                data[key] = comment_match.group(1).strip()
            else:
                data[key] = raw_value

    return data


# ---------------------------------------------------------------------------
# Extract summary from the Problem section
# ---------------------------------------------------------------------------

def extract_problem_summary(text: str, max_len: int = 80) -> str:
    """Return the first non-empty line of the ## Problem section, truncated."""
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
        if not body_started and fm_count < 2:
            continue

        if re.match(r"^##\s+Problem\b", line):
            in_problem = True
            continue

        if in_problem:
            # Stop at the next heading
            if re.match(r"^##\s+", line):
                break
            stripped = line.strip()
            if stripped:
                if len(stripped) > max_len:
                    return stripped[: max_len - 3] + "..."
                return stripped

    return ""


# ---------------------------------------------------------------------------
# Scan entries
# ---------------------------------------------------------------------------

def scan_entries(root: Path) -> List[Dict]:
    """Scan all .md files under entries/ and return metadata dicts."""
    entries_dir = root / "entries"
    if not entries_dir.is_dir():
        return []

    results = []
    for md_file in sorted(entries_dir.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            continue

        rel_path = md_file.relative_to(root)
        results.append({
            "path": str(rel_path),
            "title": fm.get("title", md_file.stem),
            "type": fm.get("type", ""),
            "tags": fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
            "domain": fm.get("domain", ""),
            "confidence": fm.get("confidence", ""),
            "summary": extract_problem_summary(text),
        })

    return results


# ---------------------------------------------------------------------------
# Generate index.md
# ---------------------------------------------------------------------------

def generate_index(entries: List[Dict]) -> str:
    """Generate the index.md content as a markdown table."""
    # Sort by domain, then type, then title
    sorted_entries = sorted(entries, key=lambda e: (
        e["domain"].lower(),
        e["type"].lower(),
        e["title"].lower(),
    ))

    lines = [
        "# Knowledge Framework Index",
        "",
        f"_Auto-generated on {date.today().isoformat()}. Do not edit manually._",
        "",
        f"**{len(sorted_entries)} entries**",
        "",
        "| Entry | Type | Tags | Domain | Confidence | Summary |",
        "|-------|------|------|--------|------------|---------|",
    ]

    for entry in sorted_entries:
        title = entry["title"]
        link = f"[{title}]({entry['path']})"
        tags_str = ", ".join(entry["tags"]) if entry["tags"] else ""
        row = (
            f"| {link} "
            f"| {entry['type']} "
            f"| {tags_str} "
            f"| {entry['domain']} "
            f"| {entry['confidence']} "
            f"| {entry['summary']} |"
        )
        lines.append(row)

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generate tags.md
# ---------------------------------------------------------------------------

def generate_tags(entries: List[Dict]) -> str:
    """Generate tags.md content with entries grouped under each tag."""
    # Build tag -> entries mapping
    tag_map: Dict[str, List[Dict]] = {}
    for entry in entries:
        for tag in entry["tags"]:
            tag_map.setdefault(tag, []).append(entry)

    lines = [
        "# Knowledge Framework Tags",
        "",
        f"_Auto-generated on {date.today().isoformat()}. Do not edit manually._",
        "",
        f"**{len(tag_map)} tags across {len(entries)} entries**",
        "",
    ]

    for tag in sorted(tag_map.keys(), key=str.lower):
        lines.append(f"## {tag}")
        lines.append("")
        for entry in sorted(tag_map[tag], key=lambda e: e["title"].lower()):
            lines.append(f"- [{entry['title']}]({entry['path']}) ({entry['type']}, {entry['domain']})")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API (used by curate.py)
# ---------------------------------------------------------------------------

def rebuild(root: Optional[Path] = None) -> Tuple[int, int]:
    """Rebuild index.md and tags.md. Returns (entry_count, tag_count)."""
    if root is None:
        root = get_root()

    entries = scan_entries(root)

    index_content = generate_index(entries)
    tags_content = generate_tags(entries)

    (root / "index.md").write_text(index_content, encoding="utf-8")
    (root / "tags.md").write_text(tags_content, encoding="utf-8")

    # Count unique tags
    all_tags = set()
    for entry in entries:
        all_tags.update(entry["tags"])

    return len(entries), len(all_tags)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    root = get_root()
    entry_count, tag_count = rebuild(root)
    print(f"Rebuilt index.md and tags.md")
    print(f"  {entry_count} entries indexed")
    print(f"  {tag_count} unique tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
