#!/usr/bin/env python3
"""
desktop_file_counter.py - Desktop File Grouper & Counter

WHAT IS THIS FILE?
==================
This script scans your Desktop folder, looks at every filename, and groups 
files that share the same base name together. It's used as a quick summary
tool at the end of the upload process.

Author: Akshay Reddy
Date: 2026-02-19
"""

import re
from pathlib import Path
from collections import Counter
import sys

def get_desktop_path() -> Path:
    """Find the user's Desktop folder automatically."""
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        raise FileNotFoundError(f"Desktop folder not found at: {desktop}")
    return desktop

def get_all_files(folder: Path) -> list:
    """Get a list of all non-hidden files in a folder."""
    files = []
    for item in folder.iterdir():
        if item.is_file() and not item.name.startswith('.'):
            files.append(item)
    files.sort(key=lambda f: f.name.lower())
    return files

def extract_group_name(filename: str) -> str:
    """
    Extract the Title Case group name from a filename.
    Matches the logic used in FolderManager and FileGrouper.
    """
    name = Path(filename).stem
    lower_name = name.lower()

    # STEP 1: Handle special brand exceptions (preserve numbers/inc)
    if 'i1 tech inc' in lower_name:
        return 'I1 Tech Inc'
    if 'cloud 9 bee inc' in lower_name:
        return 'Cloud 9 Bee Inc'

    # STEP 2: Remove anything that's NOT a letter or space.
    alpha_only = re.sub(r'[^a-zA-Z\s]', '', name)

    # STEP 3: Clean up whitespace: collapse multiple spaces and trim edges.
    cleaned = ' '.join(alpha_only.split()).strip()

    # STEP 4: Convert to Title Case for consistent grouping and display.
    result = cleaned.title()

    return result or "Misc"

def group_and_count(files: list) -> Counter:
    """Group files by their group name and count each group."""
    names = [extract_group_name(f.name) for f in files]
    return Counter(names)

def display_results(counts: Counter, total_files: int):
    """Display the grouped file counts in a nicely formatted table."""
    if not counts:
        print("\n⚠  No groupable files found on the Desktop.")
        return

    print("\n📊 Desktop File Groups (by Name)")
    print("─" * 48)
    max_name_len = max(len(name) for name in counts) + 2

    for name, count in counts.most_common():
        print(f"  {name:<{max_name_len}} — {count}")

    print("─" * 48)
    total_grouped = sum(counts.values())
    print(f"  Total: {total_grouped} file(s) in {len(counts)} group(s)")
    print()

def display_one_line_summary(counts: Counter):
    """Print a compact one-line summary: name - count, name - count"""
    if not counts:
        print("No groupable files found.")
        return
    parts = [f"{name} - {count}" for name, count in counts.most_common()]
    print(", ".join(parts))

def main():
    """Main entry point."""
    try:
        desktop = get_desktop_path()
        print(f"\n🖥  Scanning Desktop: {desktop}")
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        return

    files = get_all_files(desktop)
    if not files:
        print("\n⚠  No files found on the Desktop.")
        return

    print(f"📂 Found {len(files)} \n")
    counts = group_and_count(files)
    display_results(counts, total_files=len(files))
    
    print("📋 Summary:")
    display_one_line_summary(counts)

if __name__ == "__main__":
    main()
