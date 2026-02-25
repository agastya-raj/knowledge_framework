#!/usr/bin/env python3
"""
Recursively apply macOS Finder color tags to all files and folders
within ~/PhD_Work based on their project's recency.
"""

import subprocess
import os
import plistlib
import time

PHD_WORK = os.path.expanduser("~/PhD_Work")
NOW = time.time()

# Color scheme: (max_age_days, tag_name, color_index)
# Color indices: 0=None, 1=Gray, 2=Green, 3=Purple, 4=Blue, 5=Yellow, 6=Red, 7=Orange
COLOR_SCHEME = [
    (1, "Red", 6),
    (7, "Orange", 7),
    (30, "Yellow", 5),
    (90, "Green", 2),
    (180, "Blue", 4),
    (365, "Purple", 3),
    (999999, "Gray", 1),
]

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.DS_Store'}


def get_tag_plist(tag_name, color_index):
    """Create the binary plist data for a macOS Finder tag."""
    tag_string = f"{tag_name}\n{color_index}"
    return plistlib.dumps([tag_string], fmt=plistlib.FMT_BINARY)


def get_latest_mtime(folder):
    """Get the most recent modification time of any file in a folder."""
    latest = 0
    for root, dirs, files in os.walk(folder):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f == '.DS_Store':
                continue
            try:
                mtime = os.path.getmtime(os.path.join(root, f))
                if mtime > latest:
                    latest = mtime
            except OSError:
                pass
    return latest


def apply_tag_recursive(folder, tag_name, color_index):
    """Apply a color tag to a folder and ALL its contents recursively."""
    tag_data = get_tag_plist(tag_name, color_index)
    tag_hex = tag_data.hex()

    count = 0
    for root, dirs, files in os.walk(folder):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        # Tag the current directory
        try:
            subprocess.run(
                ['xattr', '-wx', 'com.apple.metadata:_kMDItemUserTags', tag_hex, root],
                capture_output=True, timeout=5
            )
            count += 1
        except Exception:
            pass

        # Tag all files in current directory
        for f in files:
            if f == '.DS_Store':
                continue
            filepath = os.path.join(root, f)
            try:
                subprocess.run(
                    ['xattr', '-wx', 'com.apple.metadata:_kMDItemUserTags', tag_hex, filepath],
                    capture_output=True, timeout=5
                )
                count += 1
            except Exception:
                pass

    return count


def get_color_for_age(age_days):
    """Determine color based on age in days."""
    for max_days, tag_name, color_index in COLOR_SCHEME:
        if age_days < max_days:
            return tag_name, color_index
    return "Gray", 1


def main():
    print("Applying recursive color tags to ~/PhD_Work...")
    print()

    total_tagged = 0

    # Tag project folders
    projects_dir = os.path.join(PHD_WORK, "projects")
    if os.path.isdir(projects_dir):
        print("=== Projects ===")
        for name in sorted(os.listdir(projects_dir)):
            folder = os.path.join(projects_dir, name)
            if not os.path.isdir(folder):
                continue

            latest = get_latest_mtime(folder)
            if latest == 0:
                age_days = 999999
            else:
                age_days = (NOW - latest) / 86400

            tag_name, color_index = get_color_for_age(age_days)
            count = apply_tag_recursive(folder, tag_name, color_index)
            total_tagged += count
            print(f"  {name}: {tag_name} ({int(age_days)}d old, {count} items tagged)")

    # Tag top-level folders
    print()
    print("=== Top-level folders ===")
    for name in sorted(os.listdir(PHD_WORK)):
        folder = os.path.join(PHD_WORK, name)
        if not os.path.isdir(folder) or name == "projects" or name.startswith('.'):
            continue

        latest = get_latest_mtime(folder)
        if latest == 0:
            age_days = 999999
        else:
            age_days = (NOW - latest) / 86400

        tag_name, color_index = get_color_for_age(age_days)

        # For top-level, only tag the folder itself (not recursively into projects)
        tag_data = get_tag_plist(tag_name, color_index)
        tag_hex = tag_data.hex()
        try:
            subprocess.run(
                ['xattr', '-wx', 'com.apple.metadata:_kMDItemUserTags', tag_hex, folder],
                capture_output=True, timeout=5
            )
            total_tagged += 1
        except Exception:
            pass
        print(f"  {name}: {tag_name} ({int(age_days)}d old)")

    # Tag the projects folder itself
    tag_data = get_tag_plist("Red", 6)
    tag_hex = tag_data.hex()
    subprocess.run(
        ['xattr', '-wx', 'com.apple.metadata:_kMDItemUserTags', tag_hex, projects_dir],
        capture_output=True, timeout=5
    )

    print()
    print(f"Done! Tagged {total_tagged} items total.")


if __name__ == "__main__":
    main()
