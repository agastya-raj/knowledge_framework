#!/usr/bin/env python3
"""
Fast recursive macOS Finder color tagging using xattr directly in Python.
Avoids subprocess calls for each file — much faster than calling xattr CLI.
"""
import os
import ctypes
import ctypes.util
import plistlib
import time
import sys

# Load the system library for xattr
libc = ctypes.CDLL(ctypes.util.find_library('c'))

PHD_WORK = os.path.expanduser("~/PhD_Work")
NOW = time.time()
ATTR_NAME = b'com.apple.metadata:_kMDItemUserTags'

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.tox', 'env'}

COLOR_SCHEME = [
    (1, "Red", 6),
    (7, "Orange", 7),
    (30, "Yellow", 5),
    (90, "Green", 2),
    (180, "Blue", 4),
    (365, "Purple", 3),
    (999999, "Gray", 1),
]

# Pre-compute binary plist data for each color
TAG_DATA = {}
for _, tag_name, color_index in COLOR_SCHEME:
    tag_string = f"{tag_name}\n{color_index}"
    TAG_DATA[(tag_name, color_index)] = plistlib.dumps([tag_string], fmt=plistlib.FMT_BINARY)


def set_xattr_fast(path, data):
    """Set extended attribute using ctypes (no subprocess)."""
    try:
        path_bytes = path.encode('utf-8') if isinstance(path, str) else path
        ret = libc.setxattr(path_bytes, ATTR_NAME, data, len(data), ctypes.c_uint32(0), ctypes.c_int(0))
        return ret == 0
    except Exception:
        return False


def get_latest_mtime(folder):
    """Get the most recent modification time in a folder tree."""
    latest = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f == '.DS_Store':
                continue
            try:
                mt = os.path.getmtime(os.path.join(root, f))
                if mt > latest:
                    latest = mt
            except OSError:
                pass
    return latest


def get_color_for_age(age_days):
    for max_days, tag_name, color_index in COLOR_SCHEME:
        if age_days < max_days:
            return tag_name, color_index
    return "Gray", 1


def tag_tree(folder, tag_name, color_index):
    """Tag everything in a folder tree."""
    data = TAG_DATA[(tag_name, color_index)]
    count = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if set_xattr_fast(root, data):
            count += 1
        for f in files:
            if f == '.DS_Store':
                continue
            if set_xattr_fast(os.path.join(root, f), data):
                count += 1
    return count


def main():
    total = 0
    projects_dir = os.path.join(PHD_WORK, "projects")

    print("=== Projects ===", flush=True)
    for name in sorted(os.listdir(projects_dir)):
        folder = os.path.join(projects_dir, name)
        if not os.path.isdir(folder):
            continue
        latest = get_latest_mtime(folder)
        age_days = (NOW - latest) / 86400 if latest else 999999
        tag_name, color_index = get_color_for_age(age_days)
        count = tag_tree(folder, tag_name, color_index)
        total += count
        print(f"  {name}: {tag_name} ({int(age_days)}d, {count} items)", flush=True)

    print("\n=== Top-level ===", flush=True)
    for name in sorted(os.listdir(PHD_WORK)):
        folder = os.path.join(PHD_WORK, name)
        if not os.path.isdir(folder) or name == "projects" or name.startswith('.'):
            continue
        latest = get_latest_mtime(folder)
        age_days = (NOW - latest) / 86400 if latest else 999999
        tag_name, color_index = get_color_for_age(age_days)
        # Tag folder + immediate children only (not deep recursion for non-project dirs)
        data = TAG_DATA[(tag_name, color_index)]
        set_xattr_fast(folder, data)
        for item in os.listdir(folder):
            set_xattr_fast(os.path.join(folder, item), data)
        total += 1
        print(f"  {name}: {tag_name} ({int(age_days)}d)", flush=True)

    # Tag projects/ folder itself
    set_xattr_fast(projects_dir, TAG_DATA[("Red", 6)])

    print(f"\nDone! {total} items tagged.", flush=True)


if __name__ == "__main__":
    main()
