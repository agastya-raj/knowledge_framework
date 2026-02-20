#!/usr/bin/env python3
"""Validate knowledge entries against the knowledge framework schema.

Checks YAML frontmatter fields and required markdown sections.
Standard entries require: Problem, Approach, Recipe.
Quick entries (complexity: low or type: debug/tool) require: Problem, Solution.

Usage:
    python validate.py <file>         # validate a single file
    python validate.py --all          # validate all entries in entries/
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TYPES = {"pattern", "decision", "domain", "integration", "debugging", "tool", "research"}
VALID_DOMAINS = {"optical-networking", "software-engineering", "ml-ai", "devops", "research-methods", "general"}
VALID_CONFIDENCE = {"low", "medium", "high"}
REQUIRED_FRONTMATTER = {"title", "type", "tags", "domain", "created", "confidence"}

STANDARD_REQUIRED_SECTIONS = {"Problem", "Approach", "Recipe"}
QUICK_REQUIRED_SECTIONS = {"Problem", "Solution"}
QUICK_TYPES = {"debugging", "tool"}


def get_root() -> Path:
    """Return the knowledge_framework root directory relative to this script."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# YAML frontmatter parser (no pyyaml dependency)
# ---------------------------------------------------------------------------

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
# Section parser
# ---------------------------------------------------------------------------

def parse_sections(text: str) -> set:
    """Return the set of ## heading names found in the markdown body."""
    sections = set()
    # Skip frontmatter
    lines = text.split("\n")
    in_frontmatter = False
    body_started = False
    fm_count = 0

    for line in lines:
        if line.strip() == "---":
            fm_count += 1
            if fm_count == 2:
                body_started = True
            continue
        if not body_started and fm_count < 2:
            continue

        match = re.match(r"^##\s+(.+)$", line)
        if match:
            sections.add(match.group(1).strip())

    return sections


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

def validate_file(filepath: Path) -> Tuple[bool, List[str]]:
    """Validate a single knowledge entry file.

    Returns (passed: bool, errors: list[str]).
    """
    errors: List[str] = []

    if not filepath.exists():
        return False, [f"File not found: {filepath}"]

    if not filepath.suffix == ".md":
        return False, [f"Not a markdown file: {filepath}"]

    text = filepath.read_text(encoding="utf-8")

    # --- Frontmatter validation ---
    frontmatter, parse_errors = parse_frontmatter(text)
    errors.extend(parse_errors)

    if frontmatter is None:
        return False, errors

    # Check required fields
    for field in REQUIRED_FRONTMATTER:
        if field not in frontmatter or not frontmatter[field]:
            errors.append(f"Missing required frontmatter field: {field}")

    # Validate type
    entry_type = frontmatter.get("type", "")
    if entry_type and entry_type not in VALID_TYPES:
        errors.append(
            f"Invalid type: '{entry_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_TYPES))}"
        )

    # Validate domain
    domain = frontmatter.get("domain", "")
    if domain and domain not in VALID_DOMAINS:
        errors.append(
            f"Invalid domain: '{domain}'. "
            f"Must be one of: {', '.join(sorted(VALID_DOMAINS))}"
        )

    # Validate confidence
    confidence = frontmatter.get("confidence", "")
    if confidence and confidence not in VALID_CONFIDENCE:
        errors.append(
            f"Invalid confidence: '{confidence}'. "
            f"Must be one of: {', '.join(sorted(VALID_CONFIDENCE))}"
        )

    # Validate tags is a list
    tags = frontmatter.get("tags")
    if tags is not None and not isinstance(tags, list):
        errors.append("'tags' must be a list (e.g., [tag1, tag2])")

    # --- Section validation ---
    sections = parse_sections(text)

    # Determine if this is a quick entry
    complexity = frontmatter.get("complexity", "")
    is_quick = complexity == "low" or entry_type in QUICK_TYPES

    if is_quick:
        required = QUICK_REQUIRED_SECTIONS
    else:
        required = STANDARD_REQUIRED_SECTIONS

    for section in required:
        if section not in sections:
            label = "quick" if is_quick else "standard"
            errors.append(f"Missing required section for {label} entry: ## {section}")

    passed = len(errors) == 0
    return passed, errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    root = get_root()

    if len(sys.argv) < 2:
        print("Usage: python validate.py <file> | --all")
        return 1

    if sys.argv[1] == "--all":
        entries_dir = root / "entries"
        if not entries_dir.is_dir():
            print(f"ERROR: entries directory not found at {entries_dir}")
            return 1

        files = sorted(entries_dir.rglob("*.md"))
        if not files:
            print("No .md files found in entries/")
            return 0

        total_pass = 0
        total_fail = 0

        for f in files:
            passed, errors = validate_file(f)
            rel = f.relative_to(root)
            if passed:
                print(f"  PASS  {rel}")
                total_pass += 1
            else:
                print(f"  FAIL  {rel}")
                for err in errors:
                    print(f"        - {err}")
                total_fail += 1

        print(f"\nResults: {total_pass} passed, {total_fail} failed, {total_pass + total_fail} total")
        return 1 if total_fail > 0 else 0

    else:
        filepath = Path(sys.argv[1])
        if not filepath.is_absolute():
            filepath = Path.cwd() / filepath

        passed, errors = validate_file(filepath)
        rel = filepath.name
        try:
            rel = filepath.relative_to(root)
        except ValueError:
            pass

        if passed:
            print(f"PASS  {rel}")
            return 0
        else:
            print(f"FAIL  {rel}")
            for err in errors:
                print(f"  - {err}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
