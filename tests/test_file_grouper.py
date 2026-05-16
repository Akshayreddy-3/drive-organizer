"""
tests/test_file_grouper.py - Unit Tests for File Grouper

PURPOSE:
--------
This file contains unit tests for the FileGrouper class.
It verifies that file grouping logic works correctly.

TEST CASES:
-----------
1. Base name extraction from various filename patterns
2. Grouping multiple files correctly
3. Handling edge cases (numbers only, no extension, etc.)

HOW TO RUN:
-----------
    # Run just this test file
    python -m pytest tests/test_file_grouper.py -v
    
    # Or run with unittest
    python -m unittest tests.test_file_grouper -v
    
    # Or run all tests
    python run_tests.py

Author: Akshay Reddy
Date: 2026-02-03
"""

import unittest
import sys
import os

# Add project root to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.file_grouper import FileGrouper


class TestExtractBaseName(unittest.TestCase):
    """
    Test cases for the extract_base_name() method.
    
    This method should remove trailing numbers, dates, and normalize
    special patterns like screenshots.
    """
    
    def setUp(self):
        """
        Set up test fixtures.
        
        This method runs before each test method.
        Creates a FileGrouper instance for testing.
        """
        self.grouper = FileGrouper()
    
    # -------------------------------------------------------------------------
    # Test: Trailing numbers removal
    # -------------------------------------------------------------------------
    
    def test_removes_trailing_numbers(self):
        """Files with trailing numbers should have them removed."""
        # akshay12345.pdf → akshay
        result = self.grouper.extract_base_name("akshay12345.pdf")
        self.assertEqual(result, "akshay")
    
    def test_removes_underscore_numbers(self):
        """Files with _numbers should have them removed."""
        # invoice_001.pdf → invoice
        result = self.grouper.extract_base_name("invoice_001.pdf")
        self.assertEqual(result, "invoice")
    
    def test_removes_dash_numbers(self):
        """Files with -numbers should have them removed."""
        # report-2024.pdf → report
        result = self.grouper.extract_base_name("report-2024.pdf")
        self.assertEqual(result, "report")
    
    def test_multiple_numbers_only_removes_trailing(self):
        """Only trailing numbers should be removed, not embedded ones."""
        # file123abc456.pdf → file123abc
        # Note: This removes 456 but keeps 123
        result = self.grouper.extract_base_name("product123_item456.pdf")
        # After removing trailing 456, we get product123_item
        self.assertEqual(result, "product123_item")
    
    # -------------------------------------------------------------------------
    # Test: Case insensitivity
    # -------------------------------------------------------------------------
    
    def test_lowercase_conversion(self):
        """Result should be lowercase."""
        result = self.grouper.extract_base_name("AKSHAY.pdf")
        self.assertEqual(result, "akshay")
    
    def test_mixed_case_conversion(self):
        """Mixed case should become lowercase."""
        result = self.grouper.extract_base_name("AkShAy123.pdf")
        self.assertEqual(result, "akshay")
    
    # -------------------------------------------------------------------------
    # Test: Screenshot handling
    # -------------------------------------------------------------------------
    
    def test_screenshot_pattern(self):
        """Screenshot files should go to 'screenshots' folder."""
        result = self.grouper.extract_base_name("Screenshot 2024-01-15 at 10.30.00 PM.png")
        self.assertEqual(result, "screenshots")
    
    def test_screenshot_lowercase(self):
        """Lowercase 'screenshot' should also work."""
        result = self.grouper.extract_base_name("screenshot 2024-01-15.png")
        self.assertEqual(result, "screenshots")
    
    # -------------------------------------------------------------------------
    # Test: Camera photo handling
    # -------------------------------------------------------------------------
    
    def test_img_underscore_pattern(self):
        """IMG_ files should go to 'photos' folder."""
        result = self.grouper.extract_base_name("IMG_20240115_123456.jpg")
        self.assertEqual(result, "photos")
    
    def test_img_dash_pattern(self):
        """IMG- files should go to 'photos' folder."""
        result = self.grouper.extract_base_name("IMG-20240115.jpg")
        self.assertEqual(result, "photos")
    
    # -------------------------------------------------------------------------
    # Test: Date pattern removal
    # -------------------------------------------------------------------------
    
    def test_iso_date_removal(self):
        """ISO date format (YYYY-MM-DD) should be removed."""
        result = self.grouper.extract_base_name("report_2024-01-15.pdf")
        self.assertEqual(result, "report")
    
    def test_underscore_date_removal(self):
        """Date with underscores (YYYY_MM_DD) should be removed."""
        result = self.grouper.extract_base_name("report_2024_01_15.pdf")
        self.assertEqual(result, "report")
    
    # -------------------------------------------------------------------------
    # Test: Edge cases
    # -------------------------------------------------------------------------
    
    def test_only_numbers_returns_files(self):
        """Filename with only numbers should return 'files'."""
        result = self.grouper.extract_base_name("12345.pdf")
        self.assertEqual(result, "files")
    
    def test_no_extension(self):
        """Filename without extension should work."""
        result = self.grouper.extract_base_name("document")
        self.assertEqual(result, "document")
    
    def test_empty_after_removal(self):
        """If name becomes empty after removal, return 'files'."""
        result = self.grouper.extract_base_name("123.pdf")
        self.assertEqual(result, "files")


class TestGroupFiles(unittest.TestCase):
    """
    Test cases for the group_files() method.
    
    This method should group file paths by their base names.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.grouper = FileGrouper()
    
    def test_groups_by_base_name(self):
        """Files with same base name should be grouped together."""
        files = [
            "/path/akshay123.pdf",
            "/path/akshay456.pdf",
            "/path/invoice_001.pdf"
        ]
        
        groups = self.grouper.group_files(files)
        
        # Should have 2 groups
        self.assertEqual(len(groups), 2)
        
        # akshay group should have 2 files
        self.assertEqual(len(groups["akshay"]), 2)
        
        # invoice group should have 1 file
        self.assertEqual(len(groups["invoice"]), 1)
    
    def test_files_sorted_within_group(self):
        """Files within a group should be sorted alphabetically."""
        files = [
            "/path/akshay999.pdf",
            "/path/akshay111.pdf",
            "/path/akshay555.pdf"
        ]
        
        groups = self.grouper.group_files(files)
        
        # Check order (should be sorted by filename)
        filenames = [os.path.basename(f) for f in groups["akshay"]]
        self.assertEqual(filenames, ["akshay111.pdf", "akshay555.pdf", "akshay999.pdf"])
    
    def test_empty_input(self):
        """Empty input should return empty dict."""
        groups = self.grouper.group_files([])
        self.assertEqual(groups, {})
    
    def test_single_file(self):
        """Single file should create single group."""
        files = ["/path/document.pdf"]
        
        groups = self.grouper.group_files(files)
        
        self.assertEqual(len(groups), 1)
        self.assertIn("document", groups)


class TestGetSummary(unittest.TestCase):
    """
    Test cases for the get_summary() method.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.grouper = FileGrouper()
    
    def test_summary_format(self):
        """Summary should include group and file counts."""
        groups = {
            "akshay": ["file1.pdf", "file2.pdf"],
            "invoice": ["inv.pdf"]
        }
        
        summary = self.grouper.get_summary(groups)
        
        self.assertIn("2 groups", summary)
        self.assertIn("3 files", summary)


# =============================================================================
# Run tests when executed directly
# =============================================================================

if __name__ == "__main__":
    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestExtractBaseName))
    suite.addTests(loader.loadTestsFromTestCase(TestGroupFiles))
    suite.addTests(loader.loadTestsFromTestCase(TestGetSummary))
    
    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
