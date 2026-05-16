"""
tests/test_file_scanner.py - Unit Tests for File Scanner

PURPOSE:
--------
This file contains unit tests for the FileScanner class.
Uses temporary directories to test file scanning without affecting real files.

TEST CASES:
-----------
1. Finding files in a directory
2. Filtering by extension
3. Sorting files alphabetically
4. Getting file info

Author: Akshay Reddy
Date: 2026-02-03
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# We need to mock the config before importing FileScanner
# This prevents the config from affecting tests
import src.config as config
config.VERBOSE_MODE = False
config.INCLUDE_EXTENSIONS = []
config.EXCLUDE_EXTENSIONS = []
config.INCLUDE_HIDDEN_FILES = False

from src.file_scanner import FileScanner


class TestFileScanner(unittest.TestCase):
    """
    Test cases for the FileScanner class.
    
    Uses temporary directories for isolation.
    """
    
    def setUp(self):
        """
        Create a temporary directory with test files.
        
        This runs before each test method.
        """
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test files
        self.test_files = [
            "document.pdf",
            "image.png",
            "spreadsheet.xlsx",
            "report.pdf",
            ".hidden_file.txt"  # Hidden file (starts with .)
        ]
        
        for filename in self.test_files:
            filepath = os.path.join(self.temp_dir, filename)
            # Create empty file
            with open(filepath, 'w') as f:
                f.write("test content")
        
        # Create a subdirectory (should be ignored)
        os.makedirs(os.path.join(self.temp_dir, "subfolder"))
    
    def tearDown(self):
        """
        Clean up temporary directory.
        
        This runs after each test method.
        """
        import shutil
        shutil.rmtree(self.temp_dir)
    
    # -------------------------------------------------------------------------
    # Test: Basic file scanning
    # -------------------------------------------------------------------------
    
    def test_finds_files(self):
        """Scanner should find all non-hidden files."""
        scanner = FileScanner(self.temp_dir)
        files = scanner.get_all_files()
        
        # Should find 4 files (not hidden, not directory)
        self.assertEqual(len(files), 4)
    
    def test_excludes_directories(self):
        """Scanner should not include directories."""
        scanner = FileScanner(self.temp_dir)
        files = scanner.get_all_files()
        
        # None of the results should be directories
        for f in files:
            self.assertTrue(f.is_file())
    
    def test_excludes_hidden_by_default(self):
        """Hidden files (starting with .) should be excluded by default."""
        scanner = FileScanner(self.temp_dir)
        files = scanner.get_all_files()
        
        # Check no hidden files
        for f in files:
            self.assertFalse(f.name.startswith('.'))
    
    # -------------------------------------------------------------------------
    # Test: Sorting
    # -------------------------------------------------------------------------
    
    def test_files_sorted_alphabetically(self):
        """Files should be sorted alphabetically by name."""
        scanner = FileScanner(self.temp_dir)
        files = scanner.get_all_files()
        
        # Get names
        names = [f.name for f in files]
        
        # Should be sorted (case-insensitive)
        sorted_names = sorted(names, key=str.lower)
        self.assertEqual(names, sorted_names)
    
    def test_sorting_can_be_disabled(self):
        """Passing sort=False should return unsorted files."""
        scanner = FileScanner(self.temp_dir)
        
        # Just verify it doesn't crash
        files = scanner.get_all_files(sort=False)
        self.assertGreater(len(files), 0)
    
    # -------------------------------------------------------------------------
    # Test: Extension filtering
    # -------------------------------------------------------------------------
    
    def test_filter_by_extension(self):
        """Should filter to specific extensions."""
        scanner = FileScanner(self.temp_dir)
        
        # Get only PDFs
        pdfs = scanner.get_files_by_extension(['.pdf'])
        
        self.assertEqual(len(pdfs), 2)  # document.pdf and report.pdf
        for f in pdfs:
            self.assertEqual(f.suffix.lower(), '.pdf')
    
    def test_filter_multiple_extensions(self):
        """Should filter by multiple extensions."""
        scanner = FileScanner(self.temp_dir)
        
        files = scanner.get_files_by_extension(['.pdf', '.png'])
        
        self.assertEqual(len(files), 3)  # 2 PDFs + 1 PNG
    
    # -------------------------------------------------------------------------
    # Test: File info
    # -------------------------------------------------------------------------
    
    def test_get_file_info(self):
        """Should return file information dictionary."""
        scanner = FileScanner(self.temp_dir)
        files = scanner.get_all_files()
        
        info = scanner.get_file_info(files[0])
        
        # Check required keys
        self.assertIn('name', info)
        self.assertIn('path', info)
        self.assertIn('size_bytes', info)
        self.assertIn('size_human', info)
        self.assertIn('modified', info)
    
    # -------------------------------------------------------------------------
    # Test: Error handling
    # -------------------------------------------------------------------------
    
    def test_nonexistent_path_raises_error(self):
        """Should raise FileNotFoundError for nonexistent path."""
        with self.assertRaises(FileNotFoundError):
            FileScanner("/nonexistent/path/12345")
    
    def test_file_path_raises_error(self):
        """Should raise error if path is a file, not directory."""
        file_path = os.path.join(self.temp_dir, "document.pdf")
        
        with self.assertRaises(NotADirectoryError):
            FileScanner(file_path)


class TestFileScannerSummary(unittest.TestCase):
    """
    Test cases for the get_summary() method.
    """
    
    def setUp(self):
        """Create temporary directory with test files."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create files of different sizes
        for i, size in enumerate([100, 200, 300]):
            filepath = os.path.join(self.temp_dir, f"file{i}.txt")
            with open(filepath, 'wb') as f:
                f.write(b'x' * size)
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_summary_counts_files(self):
        """Summary should count total files."""
        scanner = FileScanner(self.temp_dir)
        summary = scanner.get_summary()
        
        self.assertEqual(summary['total_files'], 3)
    
    def test_summary_calculates_size(self):
        """Summary should calculate total size."""
        scanner = FileScanner(self.temp_dir)
        summary = scanner.get_summary()
        
        self.assertEqual(summary['total_size'], 600)  # 100 + 200 + 300
    
    def test_summary_counts_extensions(self):
        """Summary should count extensions."""
        scanner = FileScanner(self.temp_dir)
        summary = scanner.get_summary()
        
        self.assertEqual(summary['extensions']['.txt'], 3)


# =============================================================================
# Run tests when executed directly
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
