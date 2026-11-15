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

# Cross-platform Desktop path detection
try:
    from utils.platform import get_desktop_path as _get_desktop_cross
except ImportError:
    _get_desktop_cross = None

def get_desktop_path() -> Path:
    """Find the user's Desktop folder automatically (cross-platform)."""
    if _get_desktop_cross is not None:
        return _get_desktop_cross()
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

    # Check for the ' - From ' separator (case-insensitive) to preserve the structure
    match = re.search(r'\s+-\s+from\s+', name, re.IGNORECASE)
    if match:
        company = name[:match.start()]
        sender = name[match.end():]
        
        # Clean company name
        lower_company = company.lower()
        if 'i1 tech inc' in lower_company:
            clean_company = 'I1 Tech Inc'
        elif 'cloud 9 bee inc' in lower_company:
            clean_company = 'Cloud 9 Bee Inc'
        else:
            clean_company = ' '.join(re.sub(r'[^a-zA-Z\s]', '', company).split()).strip().title()
            
        # Clean sender name
        clean_sender = ' '.join(re.sub(r'[^a-zA-Z\s]', '', sender).split()).strip().title()
        
        if clean_sender:
            return f"{clean_company} --From {clean_sender}"
        else:
            return f"{clean_company} --From"

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
    # Cap alignment padding to prevent line wrapping for long names in standard terminals
    max_name_len = min(max(len(name) for name in counts) + 2, 50)

    for name, count in counts.most_common():
        if len(name) >= max_name_len:
            print(f"  {name} — {count}")
        else:
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

def extract_company_name(filename: str) -> str:
    """
    Extract just the company name from an already-renamed file.
    For files in 'Company - From Sender.pdf' format, returns 'Company'.
    For files not yet renamed, returns the full group name as fallback.
    """
    name = Path(filename).stem
    # Check for the ' - From ' separator used by ai_pdf_renamer
    if ' - From ' in name:
        return name.split(' - From ')[0].strip()
    # Fallback: use the regular group name extractor
    return extract_group_name(filename)


def group_by_company(files: list) -> Counter:
    """Group files by company name only and count each company."""
    companies = [extract_company_name(f.name) for f in files]
    return Counter(companies)


def display_company_summary(counts: Counter):
    """Display a company-level summary with total file counts."""
    if not counts:
        print("\n⚠  No companies found.")
        return

    print("\n🏢 Company Summary (Total Files)")
    print("─" * 48)
    max_name_len = min(max(len(name) for name in counts) + 2, 50)

    for name, count in counts.most_common():
        if len(name) >= max_name_len:
            print(f"  {name} — {count}")
        else:
            print(f"  {name:<{max_name_len}} — {count}")

    print("─" * 48)
    total = sum(counts.values())
    print(f"  Total: {total} file(s) across {len(counts)} company/companies")
    print()


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

    print(f"📂 Found {len(files)} file(s)\n")
    counts = group_and_count(files)
    display_results(counts, total_files=len(files))
    
    print("📋 Summary:")
    display_one_line_summary(counts)

    # Company-level summary (groups by company name only)
    company_counts = group_by_company(files)
    display_company_summary(company_counts)

if __name__ == "__main__":
    main()

