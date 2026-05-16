"""
src/file_scanner.py - Local File System Scanner

WHAT IS THIS FILE?
==================
This module scans a folder on your computer (like the Desktop) and finds
all the files in it. Think of it like a librarian who walks through a room,
picks up every book (file), and writes down a list.

It can also FILTER files — for example, only show PDFs, or only show
files modified in the last 24 hours.

WHY DO WE NEED THIS?
=====================
Before we upload anything to Google Drive, we need to know WHAT files exist
on the user's computer. This module answers: "What files do you have, and
what are their details (size, extension, etc.)?"

It's the FIRST STEP in our pipeline:
  [1. Scan files] → 2. Group files → 3. Match to folders → 4. Upload

DESIGN NOTES:
-------------
- Uses pathlib.Path instead of raw strings for file paths.
  Path objects are smarter — they work on Mac, Windows, and Linux
  without worrying about / vs \\  backslash differences.
- Automatically excludes hidden files and system files.
- Returns sorted results for predictable, organized output.

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS — Loading the tools we need
# =============================================================================

# 'os' lets us interact with the operating system (file checks, path operations).
import os

# 'Path' from pathlib is a smarter way to handle file paths.
# Instead of string manipulation like: path = "/Users/ak" + "/" + "Desktop"
# We can do: path = Path("/Users/ak") / "Desktop"
# Path objects also have useful methods like .exists(), .is_file(), .suffix, etc.
from pathlib import Path

# Type hints from the 'typing' module:
# List[Path] = a list of Path objects
# Optional = value can be the specified type or None
from typing import List, Optional

# 'datetime' handles dates and times in Python.
# We use it to get file modification dates.
from datetime import datetime

# Import our configuration settings.
# DEFAULT_SCAN_PATH = where to scan (None = Desktop)
# INCLUDE_EXTENSIONS = only scan these file types (empty = all)
# EXCLUDE_EXTENSIONS = skip these file types (.tmp, .log, .DS_Store)
# INCLUDE_HIDDEN_FILES = whether to include files starting with '.'
# VERBOSE_MODE = whether to show detailed status messages
from src.config import (
    DEFAULT_SCAN_PATH,
    INCLUDE_EXTENSIONS,
    EXCLUDE_EXTENSIONS,
    INCLUDE_HIDDEN_FILES,
    VERBOSE_MODE
)


class FileScanner:
    """
    Scans a directory (folder) for files and provides filtering and sorting.
    
    Think of this class as a "file detective" — it goes into a folder,
    finds all the files, and lets you filter them in different ways.
    
    This class is responsible for:
    1. Finding all files in a directory
    2. Filtering by extension (include some, exclude others)
    3. Sorting files alphabetically
    4. Getting file metadata (size, modification date)
    
    Attributes:
        scan_path (Path): The directory (folder) being scanned
    
    Example:
        >>> scanner = FileScanner("/Users/akshay/Desktop")
        >>> files = scanner.get_all_files()
        >>> print(f"Found {len(files)} files")
    """
    
    def __init__(self, scan_path: str = None):
        """
        Initialize the FileScanner with a directory to scan.
        
        This decides WHICH folder to scan for files. If no path is given,
        it defaults to your Desktop folder (the most common place for
        miscellaneous files that need organizing).
        
        Args:
            scan_path: Path to directory to scan.
                       - If a string is provided, scan that specific folder
                       - If None, use DEFAULT_SCAN_PATH from config
                       - If config is also None, use the Desktop folder
                       
        Raises:
            FileNotFoundError: If the directory doesn't exist
            NotADirectoryError: If the path points to a file, not a folder
        
        Example:
            >>> scanner = FileScanner()  # Scans Desktop
            >>> scanner = FileScanner("/path/to/folder")  # Scans specific folder
        """
        # Determine which path to scan using a "fallback chain":
        # Priority 1: User-provided path (most specific)
        # Priority 2: Config default (from src/config.py)
        # Priority 3: Desktop folder (universal default)
        #
        # WHY this chain? It provides flexibility:
        # - Power users can specify any folder
        # - Admins can set a default in config
        # - Regular users get Desktop without thinking about it
        
        if scan_path:
            # User explicitly told us where to scan.
            # Path() converts the string to a Path object for smarter handling.
            self.scan_path = Path(scan_path)
        elif DEFAULT_SCAN_PATH:
            # No user path, but config has a default — use that.
            self.scan_path = Path(DEFAULT_SCAN_PATH)
        else:
            # No path from user or config — default to Desktop.
            # Path.home() returns the user's home directory:
            #   Mac: /Users/username
            #   Windows: C:\Users\username
            #   Linux: /home/username
            # Then / "Desktop" appends the Desktop folder to it.
            self.scan_path = Path.home() / "Desktop"
        
        # SAFETY CHECK 1: Make sure the path actually exists on the computer.
        # If someone types a wrong path, we catch it early with a clear message
        # instead of crashing later with a confusing error.
        if not self.scan_path.exists():
            raise FileNotFoundError(
                f"Directory not found: {self.scan_path}\n"
                "Please provide a valid directory path."
            )
        
        # SAFETY CHECK 2: Make sure it's a directory (folder), not a file.
        # If someone accidentally passes a file path like "/Users/ak/resume.pdf",
        # we want to tell them that's not valid — we need a folder to scan.
        if not self.scan_path.is_dir():
            raise NotADirectoryError(
                f"Not a directory: {self.scan_path}\n"
                "Please provide a path to a directory, not a file."
            )
        
        if VERBOSE_MODE:
            print(f"→ FileScanner initialized for: {self.scan_path}")
    
    def get_all_files(self, sort: bool = True) -> List[Path]:
        """
        Get ALL files from the scan directory (with filtering applied).
        
        This is the main method that does the heavy lifting.
        It walks through every item in the folder and applies multiple filters
        to decide which files to include.
        
        FILTER PIPELINE (each file must pass ALL checks):
        ─────────────────────────────────────────────────
        1. Is it a file? (skip directories/folders)
        2. Is it hidden? (skip if starts with '.' and config says to exclude)
        3. Is its extension excluded? (skip .tmp, .log, .DS_Store)
        4. Is its extension included? (if filter is set, only keep matching)
        
        Think of it like a bouncer at a club checking multiple conditions:
        "Are you old enough? Are you on the guest list? Are you not banned?"
        Only files that pass ALL checks make it into the final list.
        
        Args:
            sort: If True (default), sort files alphabetically by name.
                  WHY sort? So the output is predictable and organized.
                  Without sorting, files appear in whatever order the
                  operating system returns them (which varies!).
        
        Returns:
            List of Path objects, one for each file that passed all filters.
            A Path object contains both the filename and its full path.
        
        Example:
            >>> files = scanner.get_all_files()
            >>> for f in files:
            ...     print(f.name)  # Just the filename: "report.pdf"
            ...     print(f)       # Full path: "/Users/ak/Desktop/report.pdf"
        """
        files = []  # Our result list — starts empty, we'll add files to it
        
        # iterdir() returns every item in the directory — FILES AND FOLDERS.
        # We loop through each item and decide if it should be included.
        for item in self.scan_path.iterdir():
            
            # FILTER 1: Skip directories (folders).
            # We only want actual files, not subfolders.
            # .is_file() returns True for regular files, False for directories.
            if not item.is_file():
                continue  # 'continue' skips to the next item in the loop
            
            # FILTER 2: Skip hidden files if configured to do so.
            # On Mac/Linux, hidden files start with a dot (.), like:
            #   .DS_Store (macOS system file)
            #   .gitignore (Git config file)
            #   .env (environment variables file)
            # These are typically system/config files you don't want to upload.
            if not INCLUDE_HIDDEN_FILES and item.name.startswith('.'):
                continue
            
            # FILTER 3: Check if the file's extension is EXCLUDED.
            # EXCLUDE_EXTENSIONS is a list like ['.tmp', '.log', '.DS_Store'].
            # If the file's extension matches any of these, skip it.
            # WHY lowercase comparison? So '.PDF' and '.pdf' are treated the same.
            if EXCLUDE_EXTENSIONS:
                # item.suffix returns the file extension (e.g., '.pdf')
                if item.suffix.lower() in [e.lower() for e in EXCLUDE_EXTENSIONS]:
                    continue
            
            # FILTER 4: Check if we should ONLY include certain extensions.
            # INCLUDE_EXTENSIONS is usually empty (meaning include everything).
            # But if it's set to ['.pdf', '.docx'], ONLY those file types pass.
            if INCLUDE_EXTENSIONS:
                if item.suffix.lower() not in [e.lower() for e in INCLUDE_EXTENSIONS]:
                    continue
            
            # 🎉 The file passed ALL filters — add it to our result list!
            files.append(item)
        
        # Sort the files alphabetically by filename (case-insensitive).
        # key=lambda f: f.name.lower() tells Python:
        #   "When comparing files, use their lowercase name as the sort key"
        # This way 'Apple.pdf' comes before 'banana.pdf', not after 'z.pdf'.
        # WHY case-insensitive? Because uppercase letters normally sort before
        # lowercase in Python ('A' < 'a'), which gives unexpected results.
        if sort:
            files.sort(key=lambda f: f.name.lower())
        
        return files
    
    def get_files_by_extension(self, extensions: List[str]) -> List[Path]:
        """
        Get only files that match specific extensions.
        
        This is a convenience method — instead of getting ALL files and
        then filtering yourself, you just ask for specific types.
        
        Args:
            extensions: List of extensions to include.
                        MUST include the dot!
                        Example: ['.pdf', '.docx']
                        NOT: ['pdf', 'docx']
        
        Returns:
            List of Path objects for files matching any of the extensions.
        
        Example:
            >>> pdfs = scanner.get_files_by_extension(['.pdf'])
            >>> images = scanner.get_files_by_extension(['.jpg', '.png', '.gif'])
        """
        # Convert all extensions to lowercase for consistent comparison.
        # This way ['.PDF'] will also match files ending in '.pdf'.
        extensions = [ext.lower() for ext in extensions]
        
        # Get ALL files first (using our existing method with all its filters),
        # then keep only the ones with matching extensions.
        # WHY reuse get_all_files()? Because it already handles hidden files,
        # excluded extensions, etc. We don't want to duplicate that logic.
        all_files = self.get_all_files()
        
        # List comprehension — a compact way to filter a list.
        # It reads: "keep each file f from all_files WHERE f's extension 
        # (in lowercase) is in our list of desired extensions"
        matching = [
            f for f in all_files 
            if f.suffix.lower() in extensions
        ]
        
        return matching
    
    def get_file_info(self, file_path: Path) -> dict:
        """
        Get detailed information about a single file.
        
        This is like right-clicking a file and selecting "Get Info" on a Mac.
        It returns the file's name, size, and when it was last modified.
        
        Args:
            file_path: Path object for the file to inspect
        
        Returns:
            Dictionary with file information:
            - name: just the filename (e.g., "report.pdf")
            - path: full path (e.g., "/Users/ak/Desktop/report.pdf")
            - size_bytes: file size in bytes (raw number)
            - size_human: human-readable size ("245.3 KB" or "1.2 MB")
            - modified: when the file was last changed (datetime object)
        
        Example:
            >>> info = scanner.get_file_info(files[0])
            >>> print(f"Name: {info['name']}")
            >>> print(f"Size: {info['size_human']}")
        """
        # .stat() returns an object with file system stats:
        # - st_size: file size in bytes
        # - st_mtime: last modification time (as a Unix timestamp)
        # - st_atime: last access time
        # - st_ctime: creation time (on some systems)
        stats = file_path.stat()
        
        # Convert file size to human-readable format.
        # Computers measure size in bytes, but humans prefer KB or MB.
        #
        # 1 KB (kilobyte) = 1024 bytes
        # 1 MB (megabyte) = 1024 KB = 1,048,576 bytes
        #
        # WHY 1024 and not 1000? Because computers use binary (base-2),
        # and 2^10 = 1024. This is the traditional standard for file sizes.
        #
        # We use a simple if/elif chain to pick the right unit:
        size_bytes = stats.st_size
        if size_bytes < 1024:
            # Less than 1 KB → show in bytes (very small file)
            size_human = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            # Less than 1 MB → show in KB
            # :.1f means "show 1 decimal place" (e.g., "245.3 KB")
            size_human = f"{size_bytes / 1024:.1f} KB"
        else:
            # 1 MB or larger → show in MB
            size_human = f"{size_bytes / (1024 * 1024):.1f} MB"
        
        # Convert the modification timestamp to a human-readable datetime.
        # st_mtime is a "Unix timestamp" — the number of seconds since
        # January 1, 1970 (a universal starting point for computer time).
        # Example: 1706900000 → 2024-02-03 00:00:00
        # datetime.fromtimestamp() converts this number to a useful datetime object.
        modified = datetime.fromtimestamp(stats.st_mtime)
        
        # Return all the info as a dictionary (key-value pairs).
        # Dictionaries are like labeled boxes — each piece of info has a label.
        return {
            'name': file_path.name,        # Just the filename
            'path': str(file_path),         # Full path as a string
            'size_bytes': size_bytes,       # Size in bytes (for calculations)
            'size_human': size_human,       # Size readable by humans
            'modified': modified            # When it was last changed
        }
    
    def display_files(self, files: List[Path], max_display: int = 20) -> None:
        """
        Print a nicely formatted list of files to the terminal.
        
        This is a "pretty printer" — it takes raw file data and shows it
        in a clean, numbered list that's easy to read.
        
        Args:
            files: List of Path objects to display
            max_display: Maximum number of files to show (default 20).
                         WHY limit it? If you have 500 files, printing all
                         of them would flood the terminal and be unreadable.
        
        Example output:
            1. document.pdf (245.3 KB)
            2. image.png (1.2 MB)
            3. spreadsheet.xlsx (56.7 KB)
            ... and 47 more files
        """
        if not files:
            print("  (No files found)")
            return  # Nothing to display, exit the method early
        
        # enumerate() adds a counter to each item while looping.
        # The '1' means start counting from 1 (not 0).
        # files[:max_display] takes only the first max_display items.
        # (This is Python's "slice" syntax for lists)
        for i, f in enumerate(files[:max_display], 1):
            # Get detailed info about this file
            info = self.get_file_info(f)
            # Print in format: "  1. filename.pdf (245.3 KB)"
            print(f"  {i}. {info['name']} ({info['size_human']})")
        
        # If there are more files than we showed, tell the user how many remain.
        if len(files) > max_display:
            remaining = len(files) - max_display
            print(f"  ... and {remaining} more files")
    
    def get_summary(self) -> dict:
        """
        Get a summary of ALL files in the scan directory.
        
        This gives you a bird's-eye view of what's in the folder:
        total number of files, total size, and a breakdown by file type.
        
        Returns:
            Dictionary with:
            - total_files: how many files were found
            - total_size: total size in bytes (for calculations)
            - total_size_human: total size in KB/MB/GB (for display)
            - extensions: dict mapping each extension to its count
                          Example: {'.pdf': 5, '.jpg': 12, '.docx': 3}
        
        Example:
            >>> summary = scanner.get_summary()
            >>> print(f"Total files: {summary['total_files']}")
            >>> print(f"Total size: {summary['total_size_human']}")
        """
        # Get all files using our existing method (with all filters applied)
        files = self.get_all_files()
        
        total_size = 0     # Running total of all file sizes combined
        extensions = {}    # Dict to count how many files of each type
        
        for f in files:
            # Add this file's size to the running total.
            # f.stat().st_size gives the file size in bytes.
            total_size += f.stat().st_size
            
            # Count file extensions.
            # f.suffix returns the extension (e.g., '.pdf').
            # If a file has no extension (like 'Makefile'), suffix is ''.
            # In that case, we use '(no extension)' as the label.
            ext = f.suffix.lower() or '(no extension)'
            
            # .get(ext, 0) returns the current count for this extension,
            # or 0 if it's the first time we've seen it. Then we add 1.
            # This is a common pattern for counting things in Python.
            extensions[ext] = extensions.get(ext, 0) + 1
        
        # Convert total size to human-readable format.
        # Same logic as get_file_info(), but we also handle GB for large totals.
        if total_size < 1024:
            size_human = f"{total_size} B"
        elif total_size < 1024 * 1024:
            size_human = f"{total_size / 1024:.1f} KB"
        elif total_size < 1024 * 1024 * 1024:
            size_human = f"{total_size / (1024 * 1024):.1f} MB"
        else:
            # :.2f means 2 decimal places for GB (more precision needed)
            size_human = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
        
        # Return the summary as a dictionary.
        return {
            'total_files': len(files),
            'total_size': total_size,
            'total_size_human': size_human,
            'extensions': extensions
        }
