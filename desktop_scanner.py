"""
desktop_scanner.py - Desktop File Scanner & Categorizer (Legacy)

WHAT IS THIS FILE?
==================
This module scans the user's Desktop (or any folder) and organizes files
into categories like "documents", "images", "videos", etc.

Think of it like a librarian sorting books into sections:
- Documents go on the "Documents" shelf
- Images go on the "Images" shelf
- Videos go on the "Videos" shelf
- Everything else goes on "Other"

This is the LEGACY version used by main.py. The newer version is
src/file_scanner.py, which has more configurable filtering options.

KEY DIFFERENCES from src/file_scanner.py:
- This file has built-in category support (documents, images, etc.)
- This file can filter by name patterns and recency
- src/file_scanner.py uses config-based extension filtering instead

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS
# =============================================================================

# 'os' for operating system functions (file checks, path handling).
import os

# 'Path' from pathlib for smarter file path handling.
# Path objects work on Mac, Windows, and Linux without worrying about
# different path separator characters (/ vs \).
from pathlib import Path

# Type hints for code documentation:
# List[Path] = a list of Path objects
# Dict[str, List[Path]] = a dictionary mapping strings to lists of Paths
# Optional = can be the type or None
from typing import List, Dict, Optional


class DesktopScanner:
    """
    Scans the Desktop (or any folder) for files and organizes them by category.
    
    Despite the name "DesktopScanner," this class can scan ANY folder.
    The name comes from its primary use case: organizing files on the Desktop.
    
    This class provides:
    - Getting all files (with sorting)
    - Filtering by extension, category, name pattern, or recency
    - Categorizing files by type (documents, images, etc.)
    - Displaying formatted file lists and summaries
    
    Attributes:
        desktop_path (Path): The directory being scanned
        FILE_CATEGORIES (dict): Mapping of category names to file extensions
    """
    
    # =========================================================================
    # FILE CATEGORIES — A dictionary mapping category names to extensions
    # =========================================================================
    # This is a CLASS VARIABLE (shared by all instances, not per-object).
    # It defines what file extensions belong to each category.
    # When scanning files, we use these lists to sort files into categories.
    #
    # Each key is a category name, and each value is a list of extensions.
    # All extensions include the leading dot (e.g., '.pdf' not 'pdf').
    FILE_CATEGORIES = {
        # Office documents, text files, spreadsheets, presentations
        'documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt',
                      '.xls', '.xlsx', '.ppt', '.pptx', '.csv'],
        
        # Common image formats (photos, graphics, web images)
        'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',
                   '.webp', '.heic', '.tiff'],
        
        # Video files
        'videos': ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm'],
        
        # Audio/music files
        'audio': ['.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a'],
        
        # Compressed/archive files
        'archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        
        # Programming/code files
        'code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c',
                 '.json', '.xml']
    }
    
    def __init__(self, desktop_path: str = None):
        """
        Initialize the DesktopScanner with a directory to scan.
        
        Args:
            desktop_path: Path to scan. If None, defaults to the user's Desktop.
        
        Raises:
            FileNotFoundError: If the specified path doesn't exist.
        """
        if desktop_path:
            # User provided a custom path — use it.
            self.desktop_path = Path(desktop_path)
        else:
            # Default: scan the user's Desktop folder.
            # Path.home() returns the user's home directory:
            #   Mac: /Users/username
            #   Windows: C:\Users\username
            # Then / "Desktop" adds the Desktop subfolder.
            self.desktop_path = Path.home() / "Desktop"
        
        # Make sure the path exists before proceeding.
        if not self.desktop_path.exists():
            raise FileNotFoundError(f"Desktop path not found: {self.desktop_path}")
    
    def get_all_files(self, include_hidden: bool = False) -> List[Path]:
        """
        Get all files from the scanned directory (excluding subdirectories).
        
        Args:
            include_hidden: If True, include hidden files (names starting with '.').
                            Default is False — hidden files are usually system files
                            that you don't want to upload (like .DS_Store on macOS).
        
        Returns:
            List of Path objects, sorted alphabetically by name.
        """
        files = []
        
        # iterdir() returns every item in the directory.
        # We loop through and keep only files (not folders).
        for item in self.desktop_path.iterdir():
            if item.is_file():
                # Skip hidden files unless explicitly included.
                # Hidden files start with '.' on Mac/Linux.
                if not include_hidden and item.name.startswith('.'):
                    continue
                files.append(item)
        
        # Sort alphabetically by filename (case-insensitive).
        # Without .lower(), uppercase names would sort separately from lowercase.
        files.sort(key=lambda f: f.name.lower())
        return files
    
    def get_files_by_extension(self, extensions: List[str]) -> List[Path]:
        """
        Get only files matching specific extensions.
        
        Args:
            extensions: List of extensions to include (must include the dot).
                        Example: ['.pdf', '.doc', '.docx']
        
        Returns:
            List of matching file Path objects, sorted alphabetically.
        """
        # Normalize extensions to lowercase for case-insensitive matching.
        extensions = [ext.lower() for ext in extensions]
        files = []
        
        for item in self.desktop_path.iterdir():
            # Check if the item is a file AND its extension matches.
            # .suffix returns the file's extension (e.g., '.pdf').
            if item.is_file() and item.suffix.lower() in extensions:
                files.append(item)
        
        files.sort(key=lambda f: f.name.lower())
        return files
    
    def get_files_by_category(self, category: str) -> List[Path]:
        """
        Get files matching a predefined category (documents, images, etc.).
        
        This is a convenience method that looks up the extensions for a
        category and then calls get_files_by_extension().
        
        Args:
            category: One of the category names from FILE_CATEGORIES:
                      'documents', 'images', 'videos', 'audio', 'archives', 'code'
        
        Returns:
            List of matching file Path objects.
        
        Raises:
            ValueError: If the category name is not recognized.
        """
        # Check that the category exists in our dictionary.
        if category not in self.FILE_CATEGORIES:
            raise ValueError(
                f"Unknown category: {category}. "
                f"Available: {list(self.FILE_CATEGORIES.keys())}"
            )
        
        # Look up the extensions for this category and filter files.
        return self.get_files_by_extension(self.FILE_CATEGORIES[category])
    
    def get_files_by_name_pattern(self, pattern: str) -> List[Path]:
        """
        Search for files whose name contains a specific pattern.
        
        This is a simple substring search (case-insensitive).
        For example, pattern="report" would match "monthly_report.pdf",
        "Report_v2.docx", and "REPORTS.xlsx".
        
        Args:
            pattern: Text to search for within filenames.
        
        Returns:
            List of matching file Path objects, sorted alphabetically.
        """
        # Convert pattern to lowercase for case-insensitive matching.
        pattern = pattern.lower()
        files = []
        
        for item in self.desktop_path.iterdir():
            # Check if the item is a file AND the pattern appears in its name.
            # 'pattern in item.name.lower()' checks if the search text exists
            # anywhere within the filename (substring match).
            if item.is_file() and pattern in item.name.lower():
                files.append(item)
        
        files.sort(key=lambda f: f.name.lower())
        return files
    
    def get_recent_files(self, hours: int = 24) -> List[Path]:
        """
        Get files modified within the last N hours.
        
        This is useful for finding files you just worked on.
        "Modified" means the file's content was changed, not just opened.
        
        Args:
            hours: How many hours to look back (default 24 = last day).
        
        Returns:
            List of recent file Path objects, sorted by modification time
            (newest first, not alphabetically).
        """
        # 'time' module provides access to the current time.
        import time
        
        # Calculate the cutoff time.
        # time.time() returns the current time as a Unix timestamp (seconds
        # since January 1, 1970).
        # hours * 3600 converts hours to seconds (1 hour = 3600 seconds).
        # Subtracting gives us the timestamp for N hours ago.
        cutoff = time.time() - (hours * 3600)
        
        files = []
        
        for item in self.desktop_path.iterdir():
            # Check if the file was modified AFTER the cutoff time.
            # st_mtime = the file's last modification time (Unix timestamp).
            if item.is_file() and item.stat().st_mtime >= cutoff:
                files.append(item)
        
        # Sort by modification time (newest first).
        # reverse=True puts the highest (most recent) timestamps first.
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return files
    
    def categorize_files(self) -> Dict[str, List[Path]]:
        """
        Sort ALL files into categories (documents, images, videos, etc.).
        
        Files that don't match any category go into "other".
        This is like sorting a pile of mixed items into labeled boxes.
        
        Returns:
            Dictionary where keys are category names and values are lists
            of file Path objects belonging to that category.
            Includes an 'other' category for uncategorized files.
        """
        # Create empty lists for each category.
        # {cat: [] for cat in ...} is a dictionary comprehension.
        categorized = {cat: [] for cat in self.FILE_CATEGORIES}
        categorized['other'] = []  # Add an "other" category for leftovers
        
        for item in self.desktop_path.iterdir():
            # Skip directories and hidden files.
            if not item.is_file() or item.name.startswith('.'):
                continue
            
            # Try to find which category this file belongs to.
            found = False
            for category, extensions in self.FILE_CATEGORIES.items():
                if item.suffix.lower() in extensions:
                    categorized[category].append(item)
                    found = True
                    break  # Stop checking — file can only be in one category
            
            # If no category matched, put it in "other".
            if not found:
                categorized['other'].append(item)
        
        # Sort files within each category alphabetically.
        for category in categorized:
            categorized[category].sort(key=lambda f: f.name.lower())
        
        return categorized
    
    def display_files(self, files: List[Path]) -> None:
        """
        Print a numbered list of files with their sizes.
        
        Output format:
            1. document.pdf (245.3 KB)
            2. photo.png (1.2 MB)
        
        Args:
            files: List of file Path objects to display.
        """
        if not files:
            print("  (No files found)")
            return
        
        # enumerate(files, 1) gives us (index, file) pairs starting from 1.
        for i, f in enumerate(files, 1):
            # Calculate human-readable file size.
            size_kb = f.stat().st_size / 1024  # bytes → kilobytes
            if size_kb < 1024:
                size_str = f"{size_kb:.1f} KB"  # :.1f = 1 decimal place
            else:
                size_str = f"{size_kb/1024:.1f} MB"  # kilobytes → megabytes
            
            # Print formatted: number, filename, and size.
            print(f"  {i}. {f.name} ({size_str})")
    
    def display_summary(self) -> Dict[str, int]:
        """
        Display a summary of files by category with counts.
        
        Shows something like:
            📁 Desktop Files Summary (/Users/ak/Desktop)
            --------------------------------------------------
              Documents        5 files
              Images          12 files
              Other            3 files
            --------------------------------------------------
              Total           20 files
        
        Returns:
            Dictionary mapping category names to file counts.
            Example: {'documents': 5, 'images': 12, 'other': 3}
        """
        # Get categorized files first.
        categorized = self.categorize_files()
        
        # Print the header with the scanned path.
        print(f"\n📁 Desktop Files Summary ({self.desktop_path})")
        print("-" * 50)
        
        total = 0
        for category, files in categorized.items():
            if files:  # Only show categories that have files
                # :15 left-aligns the category name in a 15-character field.
                # :3 right-aligns the count in a 3-character field.
                # This creates nice, aligned columns.
                print(f"  {category.capitalize():15} {len(files):3} files")
                total += len(files)
        
        print("-" * 50)
        print(f"  {'Total':15} {total:3} files")
        
        # Return counts for each category (useful for programmatic access).
        return {cat: len(files) for cat, files in categorized.items()}
