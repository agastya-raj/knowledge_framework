#!/usr/bin/env python3
"""Lint tags in knowledge framework entries for consistency issues.

Checks:
  1. Non-kebab-case tags (not matching ^[a-z0-9]+(-[a-z0-9]+)*$)
  2. Orphan tags (used in exactly 1 entry)
  3. Near-duplicate tags (similar spelling, plural/singular, substrings)
  4. Entries with too few (<2) or too many (>7) tags

Usage:
    python scripts/lint_tags.py          # report all issues
    python scripts/lint_tags.py --fix    # also auto-fix non-kebab-case tags
"""

import argparse
import difflib
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MIN_TAGS = 2
MAX_TAGS = 7
NEAR_DUP_RATIO = 0.85


def get_root() -> Path:
    """Return the knowledge_framework root directory relative to this script."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# YAML frontmatter parser (pattern from validate.py)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> Tuple[Optional[Dict], List[str]]:
    """Parse YAML frontmatter between --- markers.

    Returns (parsed_dict_or_None, list_of_parse_errors).
    """
    errors: List[str] = []
    lines = text.split("\n")

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

    return data, errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_kebab_case(tag: str) -> str:
    """Convert a tag to kebab-case: lowercase, underscores/spaces become hyphens."""
    tag = tag.lower()
    tag = tag.replace("_", "-").replace(" ", "-")
    tag = re.sub(r"-+", "-", tag)
    return tag.strip("-")


def load_entries(root: Path) -> List[Tuple[Path, List[str]]]:
    """Return list of (path, tags) for every .md file under entries/."""
    results = []
    for path in sorted((root / "entries").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if fm is None:
            continue
        raw = fm.get("tags", [])
        tags = [str(t) for t in raw] if isinstance(raw, list) else []
        results.append((path, tags))
    return results


def fix_tags_in_file(path: Path, new_tags: List[str]) -> None:
    """Rewrite the tags: line in-place, preserving all other content."""
    text = path.read_text(encoding="utf-8")
    new_line = "tags: [" + ", ".join(new_tags) + "]"
    new_text, count = re.subn(r"^tags\s*:.*$", new_line, text, count=1, flags=re.MULTILINE)
    if count == 0:
        print(f"  WARNING: could not locate tags line in {path.name}, skipping")
        return
    path.write_text(new_text, encoding="utf-8")


def find_near_duplicates(all_tags: Set[str]) -> List[Tuple[str, str, str]]:
    """Return (tag_a, tag_b, reason) for near-duplicate pairs."""
    tag_list = sorted(all_tags)
    pairs: List[Tuple[str, str, str]] = []
    seen: Set[Tuple[str, str]] = set()

    for i, a in enumerate(tag_list):
        for b in tag_list[i + 1:]:
            key = (a, b)
            if key in seen:
                continue
            seen.add(key)

            if a + "s" == b or b + "s" == a:
                reason = "plural/singular"
            elif len(a) >= 3 and len(b) >= 3 and (a in b or b in a):
                reason = "substring"
            else:
                ratio = difflib.SequenceMatcher(None, a, b).ratio()
                if ratio >= NEAR_DUP_RATIO:
                    reason = f"similar (ratio={ratio:.2f})"
                else:
                    continue

            pairs.append((a, b, reason))

    return pairs


# ---------------------------------------------------------------------------
# Lint runner
# ---------------------------------------------------------------------------

def lint(root: Path, fix: bool) -> int:
    """Run all tag lint checks. Returns 0 if clean, 1 if issues found."""
    entries = load_entries(root)
    if not entries:
        print("No entries found.")
        return 0

    def rel(p: Path) -> str:
        return str(p.relative_to(root))

    # Build tag -> [entry paths] index
    tag_to_entries: Dict[str, List[Path]] = defaultdict(list)
    for path, tags in entries:
        for tag in tags:
            tag_to_entries[tag].append(path)

    all_tags: Set[str] = set(tag_to_entries.keys())
    issues_found = False

    # ------------------------------------------------------------------
    # 1. Non-kebab-case tags
    # ------------------------------------------------------------------
    bad: List[Tuple[Path, str, str]] = []
    for path, tags in entries:
        for tag in tags:
            if not KEBAB_RE.match(tag):
                bad.append((path, tag, to_kebab_case(tag)))

    print("=== Non-kebab-case tags ===")
    if bad:
        issues_found = True
        for path, tag, fixed in bad:
            action = f"  -> '{fixed}'" if fix else f"  (would fix: '{fixed}')"
            print(f"  {rel(path)}: '{tag}'{action}")

        if fix:
            # Group by file and apply
            file_fixes: Dict[Path, Dict[str, str]] = defaultdict(dict)
            for path, tag, fixed in bad:
                file_fixes[path][tag] = fixed
            for path, tags in entries:
                if path not in file_fixes:
                    continue
                mapping = file_fixes[path]
                new_tags = [mapping.get(t, t) for t in tags]
                fix_tags_in_file(path, new_tags)
                print(f"  FIXED {rel(path)}")
    else:
        print("  (none)")
    print()

    # ------------------------------------------------------------------
    # 2. Orphan tags (used in exactly 1 entry)
    # ------------------------------------------------------------------
    orphans = {tag: paths[0] for tag, paths in tag_to_entries.items() if len(paths) == 1}

    print("=== Orphan tags (used in exactly 1 entry) ===")
    if orphans:
        issues_found = True
        for tag in sorted(orphans):
            print(f"  '{tag}' -> {rel(orphans[tag])}")
    else:
        print("  (none)")
    print()

    # ------------------------------------------------------------------
    # 3. Near-duplicate tags
    # ------------------------------------------------------------------
    near_dupes = find_near_duplicates(all_tags)

    print("=== Near-duplicate tags ===")
    if near_dupes:
        issues_found = True
        for a, b, reason in near_dupes:
            ea = ", ".join(rel(p) for p in tag_to_entries[a])
            eb = ", ".join(rel(p) for p in tag_to_entries[b])
            print(f"  '{a}' <-> '{b}'  [{reason}]")
            print(f"    '{a}': {ea}")
            print(f"    '{b}': {eb}")
    else:
        print("  (none)")
    print()

    # ------------------------------------------------------------------
    # 4. Tag count out of range
    # ------------------------------------------------------------------
    count_issues: List[Tuple[Path, int, str]] = []
    for path, tags in entries:
        n = len(tags)
        if n < MIN_TAGS:
            count_issues.append((path, n, f"too few ({n} < {MIN_TAGS})"))
        elif n > MAX_TAGS:
            count_issues.append((path, n, f"too many ({n} > {MAX_TAGS})"))

    print("=== Tag count issues ===")
    if count_issues:
        issues_found = True
        for path, n, msg in count_issues:
            print(f"  {rel(path)}: {msg}")
    else:
        print("  (none)")
    print()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"Scanned {len(entries)} entries, {len(all_tags)} unique tags.")
    if issues_found:
        return 1
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint tags in knowledge framework entries for consistency issues.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Checks performed:
  1. Non-kebab-case tags  -- not matching ^[a-z0-9]+(-[a-z0-9]+)*$
  2. Orphan tags          -- used in exactly 1 entry
  3. Near-duplicate tags  -- similar spelling, plural/singular, substring
  4. Tag count            -- entries with <2 or >7 tags

--fix rewrites non-kebab-case tags in place.
Near-duplicates, orphans, and count issues are reported only (manual review).
""",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix non-kebab-case tags in place (other issues: report only)",
    )
    args = parser.parse_args()

    root = get_root()
    if not (root / "entries").is_dir():
        print(f"ERROR: entries/ directory not found at {root / 'entries'}", file=sys.stderr)
        return 1

    return lint(root, fix=args.fix)


if __name__ == "__main__":
    sys.exit(main())
