#!/usr/bin/env python3
"""Curate the knowledge framework inbox: validate, categorize, and promote entries.

Reads .md files from _inbox/, validates each one, and either:
  - Promotes valid entries to entries/{category}/{slug}.md
  - Moves invalid entries to _review/ with error comments prepended

After processing, rebuilds index.md and tags.md.

Usage:
    python curate.py              # process inbox
    python curate.py --commit     # process inbox, then git commit and push
"""

import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import List, Tuple

# Import sibling modules
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import validate_file, parse_frontmatter
from rebuild_index import rebuild


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TYPE_TO_CATEGORY = {
    "pattern": "patterns",
    "decision": "decisions",
    "domain": "domain",
    "integration": "integrations",
    "debugging": "debugging",
    "tool": "tools",
    "research": "research",
}


def get_root() -> Path:
    """Return the knowledge_framework root directory relative to this script."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------

def slugify(title: str) -> str:
    """Generate a filesystem-safe slug from a title.

    Lowercase, spaces to underscores (snake_case), remove special characters.
    """
    slug = title.lower().strip()
    # Replace spaces and hyphens with underscores
    slug = re.sub(r"[\s-]+", "_", slug)
    # Remove anything that isn't alphanumeric or underscore
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    # Collapse multiple underscores
    slug = re.sub(r"_{2,}", "_", slug)
    # Strip leading/trailing underscores
    slug = slug.strip("_")
    return slug


# ---------------------------------------------------------------------------
# Check for duplicate slugs
# ---------------------------------------------------------------------------

def find_existing_slugs(root: Path) -> set:
    """Return a set of all existing entry slugs (stem names) in entries/."""
    entries_dir = root / "entries"
    slugs = set()
    if entries_dir.is_dir():
        for md_file in entries_dir.rglob("*.md"):
            slugs.add(md_file.stem)
    return slugs


# ---------------------------------------------------------------------------
# Prepend review comment to a file
# ---------------------------------------------------------------------------

def prepend_review_comment(filepath: Path, errors: List[str]) -> str:
    """Prepend a review comment block to the file content and return it."""
    original = filepath.read_text(encoding="utf-8")
    comment_lines = [
        "<!-- REVIEW NEEDED",
        f"   Validation failed on {date.today().isoformat()}.",
        "   Errors:",
    ]
    for err in errors:
        comment_lines.append(f"   - {err}")
    comment_lines.append("-->")
    comment_lines.append("")

    return "\n".join(comment_lines) + original


# ---------------------------------------------------------------------------
# Set the updated date in frontmatter
# ---------------------------------------------------------------------------

def set_updated_date(text: str, new_date: str) -> str:
    """Set or add the 'updated' field in YAML frontmatter."""
    lines = text.split("\n")

    if not lines or lines[0].strip() != "---":
        return text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return text

    # Look for existing updated field
    updated_found = False
    for i in range(1, end_idx):
        if re.match(r"^updated\s*:", lines[i]):
            lines[i] = f"updated: {new_date}"
            updated_found = True
            break

    # If no updated field, add it before the closing ---
    if not updated_found:
        lines.insert(end_idx, f"updated: {new_date}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main curation logic
# ---------------------------------------------------------------------------

def curate(root: Path) -> Tuple[int, int, int]:
    """Process all files in _drafts/.

    Returns (promoted_count, review_count, duplicate_count).
    """
    inbox_dir = root / "_inbox"
    review_dir = root / "_review"

    # Ensure directories exist
    inbox_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    inbox_files = sorted(inbox_dir.glob("*.md"))
    if not inbox_files:
        print("No files found in _inbox/")
        return 0, 0, 0

    existing_slugs = find_existing_slugs(root)

    promoted = 0
    sent_to_review = 0
    duplicates = 0

    for filepath in inbox_files:
        print(f"\nProcessing: {filepath.name}")

        # Step 1: Validate
        passed, errors = validate_file(filepath)

        if not passed:
            # Move to _review/ with comment
            print(f"  FAIL - moving to _review/")
            for err in errors:
                print(f"    - {err}")
            commented_content = prepend_review_comment(filepath, errors)
            dest = review_dir / filepath.name
            dest.write_text(commented_content, encoding="utf-8")
            filepath.unlink()
            sent_to_review += 1
            continue

        # Step 2: Parse frontmatter for categorization
        text = filepath.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)[0]

        if fm is None:
            # Should not happen since validation passed, but be safe
            print(f"  ERROR - could not parse frontmatter after validation")
            sent_to_review += 1
            continue

        entry_type = fm.get("type", "")
        title = fm.get("title", "")
        category = TYPE_TO_CATEGORY.get(entry_type)

        if not category:
            print(f"  ERROR - no category mapping for type '{entry_type}'")
            commented_content = prepend_review_comment(
                filepath, [f"No category mapping for type: {entry_type}"]
            )
            dest = review_dir / filepath.name
            dest.write_text(commented_content, encoding="utf-8")
            filepath.unlink()
            sent_to_review += 1
            continue

        # Step 3: Generate slug and check for duplicates
        slug = slugify(title)
        if not slug:
            slug = slugify(filepath.stem)

        if slug in existing_slugs:
            print(f"  DUPLICATE - slug '{slug}' already exists in entries/")
            commented_content = prepend_review_comment(
                filepath,
                [f"Duplicate slug: '{slug}' already exists in entries/. "
                 f"Merge manually or rename the title."]
            )
            dest = review_dir / filepath.name
            dest.write_text(commented_content, encoding="utf-8")
            filepath.unlink()
            duplicates += 1
            continue

        # Step 4: Promote to entries/{category}/{slug}.md
        category_dir = root / "entries" / category
        category_dir.mkdir(parents=True, exist_ok=True)

        # Set updated date to today
        today = date.today().isoformat()
        updated_text = set_updated_date(text, today)

        dest = category_dir / f"{slug}.md"
        dest.write_text(updated_text, encoding="utf-8")
        filepath.unlink()
        existing_slugs.add(slug)
        promoted += 1
        print(f"  PROMOTED -> {dest.relative_to(root)}")

    return promoted, sent_to_review, duplicates


# ---------------------------------------------------------------------------
# Git commit and push
# ---------------------------------------------------------------------------

def git_commit_and_push(root: Path, summary: str) -> None:
    """Stage all changes, commit, and push."""
    try:
        subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
        msg = f"knowledge: curate -- {summary}"
        subprocess.run(["git", "commit", "-m", msg], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "push"], cwd=root, check=True, capture_output=True)
        print(f"\nCommitted and pushed: {msg}")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else ""
        print(f"\nGit error: {stderr}")
        if "nothing to commit" in stderr:
            print("Nothing to commit.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    root = get_root()
    do_commit = "--commit" in sys.argv

    print("=" * 60)
    print("Knowledge Framework Curation")
    print("=" * 60)

    # Process inbox
    promoted, sent_to_review, duplicates = curate(root)

    # Rebuild index
    print("\nRebuilding index.md and tags.md ...")
    entry_count, tag_count = rebuild(root)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Promoted to entries:  {promoted}")
    print(f"  Sent to review:      {sent_to_review}")
    print(f"  Duplicates:          {duplicates}")
    print(f"  Total entries now:   {entry_count}")
    print(f"  Total unique tags:   {tag_count}")

    # Commit if requested
    if do_commit:
        parts = []
        if promoted:
            parts.append(f"{promoted} promoted")
        if sent_to_review:
            parts.append(f"{sent_to_review} to review")
        if duplicates:
            parts.append(f"{duplicates} duplicates")
        summary = ", ".join(parts) if parts else "index rebuild only"
        git_commit_and_push(root, summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
