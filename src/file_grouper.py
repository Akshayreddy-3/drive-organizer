"""
src/file_grouper.py - Smart File Grouping by Base Name

WHAT IS THIS FILE?
==================
This module groups files by their "base name" — the core name with
trailing numbers, dates, and timestamps stripped away.

For example, imagine you have these files on your Desktop:
    - akshay12345.pdf
    - akshay67890.pdf
    - akshay_2024.pdf

They all share the base name "akshay", so they should go to the same
folder in Google Drive: the "akshay/" folder.

This module figures out that relationship.

WHY IS GROUPING NEEDED?
========================
Without grouping, the app would need to upload each file individually
and you'd have to tell it WHERE each file goes. With grouping, the app
automatically knows:
    "akshay12345.pdf → belongs to akshay/ folder"
    "invoice_001.pdf → belongs to invoice/ folder"

It's like sorting mail by recipient — you look at the name and put
it in the right mailbox.

GROUPING LOGIC:
---------------
1. Screenshot files → all go to "screenshots/" folder
2. IMG files (camera photos) → all go to "photos/" folder
3. Files with trailing numbers (invoice_001) → remove numbers → "invoice"
4. Files with dates (report_2024-01-15) → remove date → "report"

STEP 2 in our pipeline:
  1. Scan files → [2. Group files] → 3. Match to folders → 4. Upload

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS — Loading the tools we need
# =============================================================================

# 're' (regular expressions) is a powerful tool for pattern matching in strings.
# Think of regex like a "smart search" — instead of searching for an exact word,
# you can search for PATTERNS. Example: "any digit followed by any digit" = \d\d
# We use it to find and remove numbers/dates from filenames.
import re

# 'os' gives us access to operating system functions like file path handling.
import os

# 'Path' from pathlib handles file paths in a cross-platform way.
# Path("report.pdf").stem gives us "report" (name without extension).
from pathlib import Path

# Type hints for better code readability:
# Dict[str, List[str]] means "a dictionary where keys are strings and 
# values are lists of strings"
from typing import Dict, List

# 'defaultdict' is a special dictionary from the collections module.
# Normal dict raises KeyError if you access a key that doesn't exist.
# defaultdict CREATES a default value (like an empty list) automatically.
# It saves us from writing: "if key not in dict: dict[key] = []" every time.
from collections import defaultdict


class FileGrouper:
    """
    Groups files by extracting and comparing their base names.
    
    Think of this class like a mail sorter:
    - It looks at each file's name
    - Strips away numbers and dates to find the "core" name
    - Groups files that share the same core name together
    
    The base name is the filename with:
    - Trailing numbers removed (invoice_001 → invoice)
    - Date patterns removed (report_2024-01-15 → report)
    - Screenshot prefixes normalized (Screenshot 2024... → screenshots)
    - IMG prefixes normalized (IMG_12345 → photos)
    
    Example:
        >>> grouper = FileGrouper()
        >>> # These all have base name "akshay":
        >>> grouper.extract_base_name("akshay12345.pdf")   # → "akshay"
        >>> grouper.extract_base_name("akshay_8765.pdf")   # → "akshay"
        >>> grouper.extract_base_name("Akshay2024.pdf")    # → "akshay"
    """
    
    def __init__(self):
        """
        Initialize the FileGrouper.
        
        No configuration needed — all the grouping logic is built into
        the methods below. 'pass' means "do nothing" — this constructor
        exists just to be explicit that there's nothing to set up.
        
        WHY have an empty __init__?
        It's good practice to include it even when empty, so other
        developers know you intentionally chose not to initialize anything.
        """
        pass  # Nothing to initialize — all logic is in the methods
    
    def extract_base_name(self, filename: str) -> str:
        """
        Extract the base name from a filename.
        
        This is the CORE METHOD of the class — the brains of the grouping.
        It takes a filename like "akshay12345.pdf" and returns "akshay".
        
        WHY extract a base name?
        Because users often have many files that belong to the same category
        but have different numbers or dates in their names. By stripping
        those away, we can figure out which folder they belong to.
        
        Args:
            filename: The filename (with or without path/extension)
                      Examples: "akshay12345.pdf", "/path/to/invoice_001.pdf"
        
        Returns:
            The normalized base name (always lowercase)
            Examples: "akshay", "invoice", "screenshots", "photos"
        
        PROCESSING STEPS:
        -----------------
        1. Remove file extension (.pdf, .docx, etc.)
        2. Check for special patterns (screenshots, photos)
        3. Remove date patterns (2024-01-15)
        4. Remove trailing numbers (123, _001)
        5. Clean up leftover separators (trailing _, -, spaces)
        6. Convert to lowercase for consistency
        
        EXAMPLES:
        ---------
        >>> grouper = FileGrouper()
        
        # Trailing numbers are removed:
        >>> grouper.extract_base_name("akshay12345.pdf")    # → 'akshay'
        >>> grouper.extract_base_name("invoice_001.pdf")    # → 'invoice'
        
        # Screenshots go to "screenshots" folder:
        >>> grouper.extract_base_name("Screenshot 2024-01-15 at 10.30.00.png")
        'screenshots'
        
        # Camera photos go to "photos" folder:
        >>> grouper.extract_base_name("IMG_20240115_123456.jpg")
        'photos'
        
        # Dates are removed:
        >>> grouper.extract_base_name("report_2024-01-15.pdf")  # → 'report'
        """
        # =====================================================================
        # STEP 1: Get filename without extension
        # =====================================================================
        # Path(filename).stem extracts the name without its extension.
        # "stem" means the main part — like the stem of a flower without petals.
        # Example: "document.pdf" → "document"
        # Example: "/Users/ak/Desktop/report_v2.docx" → "report_v2"
        # WHY remove the extension? Because we care about the NAME for grouping,
        # not the file type. "report.pdf" and "report.docx" should be in the
        # same group.
        name = Path(filename).stem
        
        # =====================================================================
        # STEP 1b: Remove ' - From [sender]' suffix from AI-renamed files
        # =====================================================================
        # The ai_pdf_renamer.py renames files to: "Company - From Sender.pdf"
        # We need to strip everything from " - From " onward so that
        # "Amara Systems Tech - From IRS" becomes "Amara Systems Tech".
        # Also handles counter suffixes like "Company - From Sender (2).pdf"
        name = re.sub(r'\s*-\s*From\s+.*', '', name, flags=re.IGNORECASE).strip()
        
        # =====================================================================
        # STEP 2: Handle special patterns FIRST
        # =====================================================================
        # Some files have special naming patterns that we always want to handle
        # the same way, regardless of the numbers/dates in them.
        # We check these FIRST because they override the normal logic.
        
        # Pattern 2a: Screenshots
        # On Mac, screenshots are automatically named like:
        #   "Screenshot 2024-01-15 at 10.30.00 AM"
        # All screenshots should go to one "screenshots" folder, regardless
        # of when they were taken. So we just return "screenshots" immediately.
        # .lower() makes the check case-insensitive.
        # .startswith() checks if the name begins with the given text.
        if name.lower().startswith('screenshot'):
            return 'screenshots'
        
        # Pattern 2b: Camera photos
        # Most smartphone cameras name photos like:
        #   "IMG_20240115_123456" (IMG + date + time)
        #   "IMG-20240115-WA0001" (WhatsApp photos)
        # All camera photos go to one "photos" folder.
        # .upper() converts to uppercase so both "img_" and "IMG_" match.
        if name.upper().startswith('IMG_') or name.upper().startswith('IMG-'):
            return 'photos'
        
        # Pattern 2c: Custom Folder Name Exceptions
        # Some folders have names that include numbers or suffixes that
        # usually get stripped (like "I1 Tech Inc"). We preserve them here.
        # We search for the pattern anywhere in the name (substring match).
        lower_name = name.lower()
        if 'i1 tech inc' in lower_name:
            return 'i1 tech inc'
        if 'cloud 9 bee inc' in lower_name:
            return 'cloud 9 bee inc'
            
        # =====================================================================
        # STEP 3: Remove date patterns
        # =====================================================================
        # Many files have dates embedded in their names. We want to remove
        # those dates so "report_2024-01-15" becomes just "report".
        #
        # The regex pattern explained:
        #   \s*       = zero or more whitespace characters (spaces/tabs)
        #   \d{4}     = exactly 4 digits (the year, like "2024")
        #   [-_]?     = optionally a dash or underscore separator
        #   \d{2}     = exactly 2 digits (the month, like "01")
        #   [-_]?     = optionally a dash or underscore separator
        #   \d{2}     = exactly 2 digits (the day, like "15")
        #   .*$       = everything from here to the end of the string
        #
        # This matches dates in formats like:
        #   2024-01-15  (ISO format with dashes)
        #   2024_01_15  (with underscores)
        #   20240115    (compact format, no separators)
        #
        # The .*$ at the end removes everything AFTER the date too.
        # Example: "report_2024-01-15_final" → "report"
        # WHY remove everything after? Because text after a date is usually
        # a timestamp or version that's not useful for grouping.
        #
        # re.sub(pattern, replacement, string) finds the pattern and replaces it.
        # '' (empty string) as replacement means "delete it."
        name = re.sub(r'\s*\d{4}[-_]?\d{2}[-_]?\d{2}.*$', '', name)
        
        # =====================================================================
        # STEP 4: Remove trailing numbers
        # =====================================================================
        # Now we remove any numbers at the END of the name.
        # This handles cases like:
        #   "akshay12345"  → "akshay"     (numbers directly after name)
        #   "invoice_001"  → "invoice"    (underscore + numbers)
        #   "report-23"    → "report"     (dash + numbers)
        #   "file 42"      → "file"       (space + numbers)
        #
        # The regex pattern explained:
        #   [-_\s]?   = optionally start with a dash, underscore, or space
        #   \d+       = one or more digits (the number to remove)
        #   $         = at the END of the string (so we don't accidentally
        #               remove numbers from the middle of a name)
        #
        # WHY only trailing numbers? If someone has a file called "3dmodel.pdf",
        # we don't want to remove the "3" — it's part of the actual name.
        # But "model_3.pdf" → removing "_3" gives us "model" which is correct.
        base_name = re.sub(r'[-_\s]?\d+$', '', name)
        
        # =====================================================================
        # STEP 5: Handle edge cases
        # =====================================================================
        
        # Edge case 1: The entire filename was just numbers (like "12345.pdf").
        # After removing all numbers, base_name would be empty ("").
        # We can't use an empty string as a folder name, so we default to "files".
        if not base_name:
            base_name = "files"
        
        # Edge case 2: After removing numbers, there might be a trailing
        # separator left over. Example: "invoice_" (the _ was before the number).
        # rstrip() removes specified characters from the RIGHT side of the string.
        # We remove dashes, underscores, and spaces.
        base_name = base_name.rstrip('-_ ')
        
        # =====================================================================
        # STEP 6: Normalize to lowercase
        # =====================================================================
        # Convert to lowercase so "Akshay.pdf" and "akshay.pdf" and
        # "AKSHAY.pdf" all map to the same folder name: "akshay".
        # WHY lowercase? Because folder matching is case-insensitive.
        # Without this, "Report" and "report" would create two separate groups!
        result = base_name.lower()

        return result
    
    def group_files(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """
        Group multiple files by their base names.
        
        This takes a list of file paths and organizes them into groups.
        Think of it like sorting a pile of letters into mailboxes:
        - Each mailbox is labeled with a base name (folder name)
        - Each letter goes into the mailbox that matches its name
        
        Args:
            file_paths: List of full file paths or filenames
                        Example: ["/path/to/akshay123.pdf", "/path/to/invoice_001.pdf"]
        
        Returns:
            Dictionary where:
            - Keys = base names (the folder each group belongs to)
            - Values = lists of file paths that belong to that group
            
        Example:
            >>> files = [
            ...     "/path/to/akshay123.pdf",
            ...     "/path/to/akshay456.pdf",
            ...     "/path/to/invoice_001.pdf"
            ... ]
            >>> groups = grouper.group_files(files)
            >>> # Result:
            >>> # {
            >>> #     "akshay": ["/path/to/akshay123.pdf", "/path/to/akshay456.pdf"],
            >>> #     "invoice": ["/path/to/invoice_001.pdf"]
            >>> # }
        """
        # defaultdict(list) creates a dictionary that automatically creates
        # an empty list [] for any new key you access.
        #
        # With a regular dict, this would crash:
        #   groups = {}
        #   groups["akshay"].append("file.pdf")  # KeyError: "akshay" doesn't exist!
        #
        # With defaultdict(list), it works:
        #   groups = defaultdict(list)
        #   groups["akshay"].append("file.pdf")  # Automatically creates the list first
        #
        # WHY defaultdict over regular dict? It's cleaner and avoids the need
        # for "if key not in dict" checks everywhere.
        groups = defaultdict(list)
        
        # Process each file and assign it to a group.
        for path in file_paths:
            # Extract just the filename from the full path.
            # os.path.basename("/Users/ak/Desktop/report.pdf") → "report.pdf"
            filename = os.path.basename(path)
            
            # Use our extract_base_name method to determine the group.
            # "akshay12345.pdf" → "akshay"
            base_name = self.extract_base_name(filename)
            
            # Add this file's full path to its group's list.
            # If the group doesn't exist yet, defaultdict creates it.
            groups[base_name].append(path)
        
        # Sort files within each group alphabetically.
        # This ensures that files are always in a predictable order.
        # key=lambda x: os.path.basename(x).lower() sorts by the filename
        # (not the full path), case-insensitively.
        for base_name in groups:
            groups[base_name].sort(key=lambda x: os.path.basename(x).lower())
        
        # Convert defaultdict back to a regular dict before returning.
        # WHY? Because defaultdict has a side effect: accessing any key
        # creates it automatically. Regular dict is safer to pass around
        # because it won't accidentally create empty entries.
        return dict(groups)
    
    def display_groups(self, groups: Dict[str, List[str]]) -> None:
        """
        Print a nicely formatted display of the file groups.
        
        This shows the user how their files were grouped, making it easy
        to verify that the grouping logic worked correctly.
        
        Args:
            groups: Dictionary of groups from group_files()
        
        Output format:
            📁 File Groups (3 groups):
            --------------------------------------------------
            
              📂 akshay/ (2 files)
                  └── akshay123.pdf
                  └── akshay456.pdf
            
              📂 invoice/ (1 files)
                  └── invoice_001.pdf
        """
        # Show a header with the total number of groups found.
        print(f"\n📁 File Groups ({len(groups)} groups):")
        print("-" * 50)  # Print 50 dashes as a visual separator
        
        # sorted() returns groups in alphabetical order by key (base name).
        # .keys() gets just the dictionary keys (group names) without values.
        for base_name in sorted(groups.keys()):
            files = groups[base_name]
            # Show the group name and how many files are in it.
            print(f"\n  📂 {base_name}/ ({len(files)} files)")
            
            # Show each file in the group, indented under the group name.
            # └── is a Unicode box-drawing character for tree-style display.
            for file_path in files:
                filename = os.path.basename(file_path)
                print(f"      └── {filename}")
    
    def get_summary(self, groups: Dict[str, List[str]]) -> str:
        """
        Get a one-line summary of the groups.
        
        Useful for quick status messages like "5 groups, 23 files"
        without printing the full detailed display.
        
        Args:
            groups: Dictionary of groups from group_files()
        
        Returns:
            Summary string like "5 groups, 23 files"
        """
        # sum() adds up all the values. len(files) gives the count of
        # files in each group. groups.values() gives all the file lists.
        # This is a concise way to count ALL files across ALL groups.
        total_files = sum(len(files) for files in groups.values())
        return f"{len(groups)} groups, {total_files} files"


# =============================================================================
# STANDALONE TEST / DEMO
# =============================================================================
# This code ONLY runs when you execute this file directly:
#   python src/file_grouper.py
# It does NOT run when you import the module in another file.
#
# __name__ is a special Python variable:
# - When a file runs directly → __name__ is "__main__"
# - When a file is imported → __name__ is the module name (e.g., "file_grouper")
#
# WHY is this useful? It lets us include test code in the same file
# without it running when other files import our class.

if __name__ == "__main__":
    print("=" * 60)
    print("  FileGrouper Demo")
    print("=" * 60)
    
    # Create a FileGrouper instance to test with.
    grouper = FileGrouper()
    
    # Define test cases: each is a tuple of (input_filename, expected_output).
    # These let us verify the extract_base_name method works correctly.
    test_cases = [
        # (input filename,                          expected base name)
        ("akshay12345.pdf",                          "akshay"),
        ("akshay_8765.pdf",                          "akshay"),
        ("AKSHAY2024.pdf",                           "akshay"),
        ("invoice_001.pdf",                          "invoice"),
        ("Invoice_002.pdf",                          "invoice"),
        ("report_2024-01-15.pdf",                    "report"),
        ("Screenshot 2024-01-15 at 10.30.00.png",    "screenshots"),
        ("IMG_20240115_123456.jpg",                   "photos"),
        ("12345.pdf",                                 "files"),
    ]
    
    print("\n📋 Base Name Extraction Tests:\n")
    all_passed = True  # Will become False if any test fails
    
    # Run each test case.
    for filename, expected in test_cases:
        result = grouper.extract_base_name(filename)  # Get actual result
        passed = result == expected                     # Compare to expected
        status = "✓" if passed else "✗"                # Choose status icon
        
        print(f"  {status} {filename}")
        print(f"      Expected: {expected}")
        print(f"      Got:      {result}")
        
        if not passed:
            all_passed = False
    
    # Final summary.
    print("\n" + "=" * 60)
    if all_passed:
        print("  ✓ All tests passed!")
    else:
        print("  ✗ Some tests failed!")
    print("=" * 60)
