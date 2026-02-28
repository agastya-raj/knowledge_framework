#!/usr/bin/env python3
"""Generate a summary statistics report for the knowledge framework.

Scans all entries under entries/, parses YAML frontmatter, and produces:
  - Entry count, per-category and per-domain breakdowns
  - Tag frequency distribution
  - Confidence distribution
  - Most/least recently updated entries
  - Entries missing optional fields
  - Tag density metrics

Usage:
    python scripts/stats.py              # formatted terminal output
    python scripts/stats.py --markdown   # write STATS.md to repo root
"""

import argparse
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers (mirrors validate.py / rebuild_index.py conventions)
# ---------------------------------------------------------------------------

def get_root() -> Path:
    """Return the knowledge_framework root directory relative to this script."""
    return Path(__file__).resolve().parent.parent


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
# Entry scanning
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
        # Category is the immediate subdirectory of entries/
        parts = rel_path.parts
        category = parts[1] if len(parts) > 2 else ""

        tags = fm.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        related = fm.get("related", [])
        if not isinstance(related, list):
            related = [] if not related else [related]

        results.append({
            "path": str(rel_path),
            "title": fm.get("title", md_file.stem),
            "type": fm.get("type", ""),
            "tags": tags,
            "domain": fm.get("domain", ""),
            "confidence": fm.get("confidence", ""),
            "complexity": fm.get("complexity", ""),
            "created": fm.get("created", ""),
            "updated": fm.get("updated", ""),
            "related": related,
            "category": category,
        })

    return results


# ---------------------------------------------------------------------------
# Statistics computation
# ---------------------------------------------------------------------------

def compute_stats(entries: List[Dict]) -> Dict:
    """Compute all statistics from the list of entry metadata dicts."""

    total = len(entries)

    # 1. Per-category counts
    category_counts: Counter = Counter()
    for e in entries:
        category_counts[e["category"] or "(uncategorized)"] += 1

    # 2. Per-domain counts
    domain_counts: Counter = Counter()
    for e in entries:
        domain_counts[e["domain"] or "(unknown)"] += 1

    # 3. Tag frequency
    tag_counter: Counter = Counter()
    for e in entries:
        for tag in e["tags"]:
            tag_counter[tag] += 1

    total_unique_tags = len(tag_counter)
    total_tag_uses = sum(len(e["tags"]) for e in entries)
    avg_tags = total_tag_uses / total if total else 0.0

    # 4. Confidence distribution
    confidence_counts: Counter = Counter()
    for e in entries:
        confidence_counts[e["confidence"] or "(unset)"] += 1

    # 5. Date-sorted lists — use updated if present, else created
    def effective_date(e: Dict) -> str:
        return e["updated"] if e["updated"] else e["created"]

    dated = [(effective_date(e), e) for e in entries]
    dated_valid = [(d, e) for d, e in dated if d]
    dated_sorted = sorted(dated_valid, key=lambda x: x[0], reverse=True)

    top5_recent = dated_sorted[:5]
    top5_oldest = list(reversed(dated_sorted[-5:])) if len(dated_sorted) >= 5 else list(reversed(dated_sorted))

    # 6. Missing optional fields
    missing_updated = [e for e in entries if not e["updated"]]
    missing_complexity = [e for e in entries if not e["complexity"]]
    missing_related = [e for e in entries if not e["related"]]

    return {
        "total": total,
        "category_counts": category_counts,
        "domain_counts": domain_counts,
        "tag_counter": tag_counter,
        "total_unique_tags": total_unique_tags,
        "avg_tags": avg_tags,
        "confidence_counts": confidence_counts,
        "top5_recent": top5_recent,
        "top5_oldest": top5_oldest,
        "missing_updated": missing_updated,
        "missing_complexity": missing_complexity,
        "missing_related": missing_related,
    }


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------

def render_terminal(stats: Dict) -> str:
    lines: List[str] = []

    def section(title: str) -> None:
        lines.append("")
        lines.append(title)
        lines.append("-" * len(title))

    lines.append("=" * 50)
    lines.append("Knowledge Framework Statistics")
    lines.append(f"Generated: {date.today().isoformat()}")
    lines.append("=" * 50)

    # Overview
    section("Overview")
    lines.append(f"  Total entries      : {stats['total']}")
    lines.append(f"  Unique tags        : {stats['total_unique_tags']}")
    lines.append(f"  Avg tags per entry : {stats['avg_tags']:.1f}")

    # Per-category
    section("Entries by Category")
    for cat, count in sorted(stats["category_counts"].items()):
        lines.append(f"  {cat:<20} {count}")

    # Per-domain
    section("Entries by Domain")
    for domain, count in sorted(stats["domain_counts"].items(), key=lambda x: -x[1]):
        lines.append(f"  {domain:<30} {count}")

    # Confidence distribution
    section("Confidence Distribution")
    for level in ("high", "medium", "low", "(unset)"):
        count = stats["confidence_counts"].get(level, 0)
        lines.append(f"  {level:<10} {count}")

    # Tag frequency
    section("Tag Frequency (top 20)")
    tag_counter: Counter = stats["tag_counter"]
    for tag, count in tag_counter.most_common(20):
        lines.append(f"  {tag:<35} {count}")

    # Recent
    section("Top 5 Most Recently Updated")
    for eff_date, e in stats["top5_recent"]:
        lines.append(f"  {eff_date}  {e['title']}")

    # Oldest
    section("Top 5 Least Recently Updated")
    for eff_date, e in stats["top5_oldest"]:
        lines.append(f"  {eff_date}  {e['title']}")

    # Missing fields
    section("Entries Missing Optional Fields")
    lines.append(f"  missing 'updated'    : {len(stats['missing_updated'])}")
    if stats["missing_updated"]:
        for e in stats["missing_updated"]:
            lines.append(f"    - {e['title']}")

    lines.append(f"  missing 'complexity' : {len(stats['missing_complexity'])}")
    if stats["missing_complexity"]:
        for e in stats["missing_complexity"]:
            lines.append(f"    - {e['title']}")

    lines.append(f"  missing 'related'    : {len(stats['missing_related'])}")
    if stats["missing_related"]:
        for e in stats["missing_related"]:
            lines.append(f"    - {e['title']}")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def render_markdown(stats: Dict) -> str:
    lines: List[str] = []

    lines.append("# Knowledge Framework Statistics")
    lines.append("")
    lines.append(f"_Generated: {date.today().isoformat()}_")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total entries | {stats['total']} |")
    lines.append(f"| Unique tags | {stats['total_unique_tags']} |")
    lines.append(f"| Avg tags per entry | {stats['avg_tags']:.1f} |")
    lines.append("")

    # Per-category
    lines.append("## Entries by Category")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    for cat, count in sorted(stats["category_counts"].items()):
        lines.append(f"| {cat} | {count} |")
    lines.append("")

    # Per-domain
    lines.append("## Entries by Domain")
    lines.append("")
    lines.append("| Domain | Count |")
    lines.append("|--------|-------|")
    for domain, count in sorted(stats["domain_counts"].items(), key=lambda x: -x[1]):
        lines.append(f"| {domain} | {count} |")
    lines.append("")

    # Confidence
    lines.append("## Confidence Distribution")
    lines.append("")
    lines.append("| Level | Count |")
    lines.append("|-------|-------|")
    for level in ("high", "medium", "low", "(unset)"):
        count = stats["confidence_counts"].get(level, 0)
        lines.append(f"| {level} | {count} |")
    lines.append("")

    # Tag frequency
    lines.append("## Tag Frequency (top 20)")
    lines.append("")
    lines.append("| Tag | Count |")
    lines.append("|-----|-------|")
    tag_counter: Counter = stats["tag_counter"]
    for tag, count in tag_counter.most_common(20):
        lines.append(f"| {tag} | {count} |")
    lines.append("")

    # Recent
    lines.append("## Top 5 Most Recently Updated")
    lines.append("")
    for eff_date, e in stats["top5_recent"]:
        lines.append(f"- **{eff_date}** — [{e['title']}]({e['path']})")
    lines.append("")

    # Oldest
    lines.append("## Top 5 Least Recently Updated")
    lines.append("")
    for eff_date, e in stats["top5_oldest"]:
        lines.append(f"- **{eff_date}** — [{e['title']}]({e['path']})")
    lines.append("")

    # Missing fields
    lines.append("## Entries Missing Optional Fields")
    lines.append("")
    lines.append(f"**Missing `updated`** ({len(stats['missing_updated'])})")
    lines.append("")
    if stats["missing_updated"]:
        for e in stats["missing_updated"]:
            lines.append(f"- [{e['title']}]({e['path']})")
    else:
        lines.append("_None_")
    lines.append("")

    lines.append(f"**Missing `complexity`** ({len(stats['missing_complexity'])})")
    lines.append("")
    if stats["missing_complexity"]:
        for e in stats["missing_complexity"]:
            lines.append(f"- [{e['title']}]({e['path']})")
    else:
        lines.append("_None_")
    lines.append("")

    lines.append(f"**Missing `related`** ({len(stats['missing_related'])})")
    lines.append("")
    if stats["missing_related"]:
        for e in stats["missing_related"]:
            lines.append(f"- [{e['title']}]({e['path']})")
    else:
        lines.append("_None_")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate summary statistics for the knowledge framework."
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Write statistics to STATS.md in the repo root instead of stdout.",
    )
    args = parser.parse_args()

    root = get_root()
    entries = scan_entries(root)
    stats = compute_stats(entries)

    if args.markdown:
        content = render_markdown(stats)
        out_path = root / "STATS.md"
        out_path.write_text(content, encoding="utf-8")
        print(f"Written to {out_path}")
    else:
        print(render_terminal(stats))

    return 0


if __name__ == "__main__":
    sys.exit(main())
