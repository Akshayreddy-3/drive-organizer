"""
tests/test_folder_navigator.py - Unit Tests for Folder Navigator

PURPOSE:
--------
This file contains unit tests for the FolderNavigator class.
Uses mock objects to test without making real API calls.

TEST CASES:
-----------
1. Finding existing folders
2. Matching base names to folders
3. Creating month/date subfolders

Author: Akshay Reddy
Date: 2026-02-03
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock config before importing
import src.config as config
config.VERBOSE_MODE = False
config.MONTH_FOLDER_FORMAT = "%b"  # Jan, Feb, Mar
config.DATE_FOLDER_FORMAT = "%Y-%m-%d"  # 2024-01-15

from src.folder_navigator import FolderNavigator


class TestGetExistingFolders(unittest.TestCase):
    """
    Test cases for get_existing_folders() method.
    """
    
    def setUp(self):
        """Set up mock DriveClient."""
        # Create a mock DriveClient
        self.mock_client = Mock()
        
        # Configure the mock to return test folders
        self.mock_client.list_root_folders.return_value = [
            {'id': 'folder1', 'name': 'akshay'},
            {'id': 'folder2', 'name': 'invoices'},
            {'id': 'folder3', 'name': 'Reports'}
        ]
        
        # Create navigator with mock client
        self.navigator = FolderNavigator(self.mock_client)
    
    def test_returns_folders_from_api(self):
        """Should return folders from Drive API."""
        folders = self.navigator.get_existing_folders()
        
        self.assertEqual(len(folders), 3)
        self.assertEqual(folders[0]['name'], 'akshay')
    
    def test_caches_results(self):
        """Should cache results and not call API again."""
        # First call
        self.navigator.get_existing_folders()
        
        # Second call
        self.navigator.get_existing_folders()
        
        # API should only be called once
        self.assertEqual(self.mock_client.list_root_folders.call_count, 1)
    
    def test_refresh_forces_api_call(self):
        """refresh=True should force new API call."""
        # First call
        self.navigator.get_existing_folders()
        
        # Second call with refresh
        self.navigator.get_existing_folders(refresh=True)
        
        # API should be called twice
        self.assertEqual(self.mock_client.list_root_folders.call_count, 2)


class TestGetFolderNames(unittest.TestCase):
    """
    Test cases for get_folder_names() method.
    """
    
    def setUp(self):
        """Set up mock DriveClient."""
        self.mock_client = Mock()
        self.mock_client.list_root_folders.return_value = [
            {'id': 'folder1', 'name': 'Akshay'},
            {'id': 'folder2', 'name': 'INVOICES'}
        ]
        self.navigator = FolderNavigator(self.mock_client)
    
    def test_returns_lowercase_names(self):
        """Should return folder names in lowercase."""
        names = self.navigator.get_folder_names()
        
        self.assertIn('akshay', names)
        self.assertIn('invoices', names)
        
        # Should NOT have uppercase versions
        self.assertNotIn('Akshay', names)
        self.assertNotIn('INVOICES', names)


class TestFindMatchingFolder(unittest.TestCase):
    """
    Test cases for find_matching_folder() method.
    """
    
    def setUp(self):
        """Set up mock DriveClient."""
        self.mock_client = Mock()
        self.mock_client.list_root_folders.return_value = [
            {'id': 'folder1', 'name': 'akshay'},
            {'id': 'folder2', 'name': 'Invoices'}
        ]
        self.navigator = FolderNavigator(self.mock_client)
    
    def test_finds_exact_match(self):
        """Should find folder with exact name match."""
        result = self.navigator.find_matching_folder('akshay')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'akshay')
    
    def test_case_insensitive_match(self):
        """Should match regardless of case."""
        # Search lowercase, folder is 'Invoices'
        result = self.navigator.find_matching_folder('invoices')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Invoices')
    
    def test_returns_none_if_not_found(self):
        """Should return None if no match."""
        result = self.navigator.find_matching_folder('nonexistent')
        
        self.assertIsNone(result)


class TestFindOrCreateMonthFolder(unittest.TestCase):
    """
    Test cases for find_or_create_month_folder() method.
    """
    
    def setUp(self):
        """Set up mock DriveClient."""
        self.mock_client = Mock()
        self.navigator = FolderNavigator(self.mock_client)
    
    def test_returns_existing_folder(self):
        """Should return existing folder if found."""
        # Mock find_folder to return a folder
        self.mock_client.find_folder.return_value = {'id': 'month123', 'name': 'Feb'}
        
        result = self.navigator.find_or_create_month_folder('parent123')
        
        self.assertEqual(result['id'], 'month123')
        # create_folder should NOT be called
        self.mock_client.create_folder.assert_not_called()
    
    def test_creates_folder_if_not_found(self):
        """Should create folder if not found."""
        # Mock find_folder to return None (not found)
        self.mock_client.find_folder.return_value = None
        
        # Mock create_folder
        self.mock_client.create_folder.return_value = {'id': 'new123', 'name': 'Feb'}
        
        result = self.navigator.find_or_create_month_folder('parent123')
        
        self.assertEqual(result['id'], 'new123')
        self.mock_client.create_folder.assert_called_once()


class TestFindOrCreateDateFolder(unittest.TestCase):
    """
    Test cases for find_or_create_date_folder() method.
    """
    
    def setUp(self):
        """Set up mock DriveClient."""
        self.mock_client = Mock()
        self.navigator = FolderNavigator(self.mock_client)
    
    def test_uses_correct_date_format(self):
        """Should use DATE_FOLDER_FORMAT from config."""
        # Mock find_folder to return None (will create new)
        self.mock_client.find_folder.return_value = None
        self.mock_client.create_folder.return_value = {'id': 'date123', 'name': '2024-02-15'}
        
        # Use specific date
        test_date = datetime(2024, 2, 15)
        
        self.navigator.find_or_create_date_folder('parent123', test_date)
        
        # Check that create was called with correct name
        args, kwargs = self.mock_client.create_folder.call_args
        self.assertEqual(args[0], '2024-02-15')


class TestGetUploadFolder(unittest.TestCase):
    """
    Test cases for get_upload_folder() method.
    """
    
    def setUp(self):
        """Set up mock DriveClient."""
        self.mock_client = Mock()
        self.mock_client.list_root_folders.return_value = [
            {'id': 'folder1', 'name': 'akshay'}
        ]
        # Mock find_folder to always return a folder (simulating existing folders)
        self.mock_client.find_folder.return_value = {'id': 'sub123', 'name': 'test'}
        
        self.navigator = FolderNavigator(self.mock_client)
    
    def test_returns_date_folder(self):
        """Should return the date folder for upload."""
        result = self.navigator.get_upload_folder('akshay')
        
        self.assertIsNotNone(result)
        self.assertIn('id', result)
    
    def test_returns_none_if_no_matching_folder(self):
        """Should return None if no matching folder exists."""
        result = self.navigator.get_upload_folder('nonexistent')
        
        self.assertIsNone(result)


# =============================================================================
# Run tests when executed directly
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
