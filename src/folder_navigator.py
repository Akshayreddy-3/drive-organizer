"""
src/folder_navigator.py - Navigate and Create Folders in Google Drive

WHAT IS THIS FILE?
==================
This module handles folder navigation in Google Drive. If Google Drive
were a building, this module is the "directory" that tells you:
- Which rooms (folders) exist
- How to find the right room
- How to create new rooms inside existing ones

It manages the folder hierarchy: Project → Month → Date
Example: akshay/ → Feb/ → 2026-02-03/

The module will NOT auto-create project folders.
If a matching project folder doesn't exist, files are SKIPPED
with a warning. Month and date subfolders ARE still auto-created
inside existing project folders.

STEP 3 in our pipeline:
  1. Scan files → 2. Group files → [3. Match to folders] → 4. Upload

Author: Akshay Reddy
Date: 2026-02-03
"""

import re
from datetime import datetime
from typing import Dict, List, Optional

# Import our DriveClient class that handles actual Google Drive API calls.
# FolderNavigator USES DriveClient — it doesn't talk to Google directly.
# This is called "composition": one class uses another class to do work.
# Think of it like a manager (FolderNavigator) delegating tasks to a worker (DriveClient).
from src.drive_client import DriveClient

# VERBOSE_MODE = whether to print detailed status messages
# BASE_FOLDER_ID = the target root folder ID
from src.config import MONTH_FOLDER_FORMAT, DATE_FOLDER_FORMAT, VERBOSE_MODE, BASE_FOLDER_ID


class FolderNavigator:
    """
    Navigates and manages folder structure in Google Drive.
    
    Think of this class as a "GPS" for Google Drive:
    - It knows where all the folders are
    - It can find the right folder for your files
    - It creates sub-folders when needed (month/date folders)
    
    This class does three main things:
    1. Lists existing folders in Drive root (your top-level folders)
    2. Matches file groups to those existing folders
    3. Creates month/date subfolders for organized file storage
    
    Attributes:
        client: DriveClient instance for making API calls
        _existing_folders: Cached list of folders (to avoid repeated API calls)
    
    Example:
        >>> navigator = FolderNavigator(drive_client)
        >>> # Check what folders exist in Drive:
        >>> folders = navigator.get_existing_folders()
        >>> for f in folders:
        ...     print(f"- {f['name']}")
    """
    
    def __init__(self, drive_client: DriveClient):
        """
        Initialize the FolderNavigator.
        
        Args:
            drive_client: An authenticated DriveClient instance.
                          This must already be connected to Google Drive.
        
        Example:
            >>> client = DriveClient()  # Connect to Drive
            >>> navigator = FolderNavigator(client)  # Create navigator
        """
        # Store a reference to the Drive client so we can use it in other methods.
        # We don't create our OWN DriveClient — we receive one that's already
        # authenticated. This is called "dependency injection."
        # WHY? Because it lets us reuse the same authenticated connection
        # across multiple classes without re-authenticating each time.
        self.client = drive_client
        
        # Cache for existing folders — starts as None (not loaded yet).
        # After the first API call, we store the results here so we don't
        # need to ask Google Drive again and again.
        # This is called "caching" — saving expensive results for reuse.
        # The underscore prefix (_) signals "this is private" — other code
        # should use get_existing_folders() instead of accessing this directly.
        #
        # WHY cache? Each API call to Google takes time (network request).
        # If we call list_root_folders() every time, uploading 50 files would
        # make 50 API calls just to check folders. With caching, we make 1.
        # Counter for how many NEW project folders we create in this session.
        # This helps the final summary report.
        self.folders_created_count = 0
        self.created_project_names = []  # List to track WHCH folders were created
        self._existing_folders = None
    
    def get_existing_folders(self, refresh: bool = False) -> List[Dict]:
        """
        Get list of existing folders at the ROOT level of Google Drive.
        
        This fetches the top-level folders that the user has already created.
        Files will ONLY be uploaded to these folders — we don't auto-create
        new project folders.
        
        Uses CACHING: the first call fetches from Google's servers, and
        subsequent calls return the saved result (much faster).
        Pass refresh=True to force a fresh fetch from the API.
        
        Args:
            refresh: If True, ignore the cache and fetch from API again.
                     Useful if folders were created/deleted during the session.
        
        Returns:
            List of folder dicts, each containing:
            - 'id': the folder's unique ID in Google Drive
            - 'name': the folder's display name
        
        Example:
            >>> folders = navigator.get_existing_folders()
            >>> for f in folders:
            ...     print(f"Folder: {f['name']} (ID: {f['id']})")
        """
        # Check if we already have cached results AND we're not forced to refresh.
        # 'is not None' is more precise than 'if self._existing_folders' because
        # an empty list [] is valid (means "no folders") but would be falsy.
        if self._existing_folders is not None and not refresh:
            return self._existing_folders
        
        if VERBOSE_MODE:
            print("→ Fetching existing folders from Drive...")
        
        # Call the DriveClient to get all root-level folders from the API.
        # This makes an actual network request to Google's servers.
        folders = self.client.list_root_folders()
        
        # Store the results in our cache for future calls.
        self._existing_folders = folders
        
        if VERBOSE_MODE:
            print(f"  Found {len(folders)} existing folders")
        
        return folders
    
    def get_folder_names(self) -> List[str]:
        """
        Get just the NAMES of existing folders (in lowercase).
        
        This is a convenience method for quickly checking if a folder
        name exists. Returns lowercase names for easy comparison.
        
        Returns:
            List of folder names in lowercase.
            Example: ['akshay', 'invoices', 'reports']
        
        Example:
            >>> names = navigator.get_folder_names()
            >>> if 'akshay' in names:
            ...     print("akshay folder exists!")
        """
        # First get the full folder data (with ids and names).
        folders = self.get_existing_folders()
        
        # Use a list comprehension to extract just the names, in lowercase.
        # .lower() ensures matching is case-insensitive:
        # A folder named "Akshay" in Drive will match the base name "akshay".
        return [f['name'].lower() for f in folders]
    
    def _clean_for_match(self, name: str) -> str:
        """
        Cleans a string for robust matching by removing all non-alphanumeric 
        characters and converting to lowercase.
        
        This handles:
        - ' - From [sender]' suffix from ai_pdf_renamer
        - Non-breaking spaces (\u00A0 vs ' ')
        - Extra spaces/tabs
        - Different casing ('INC' vs 'inc')
        """
        # Remove ' - From [sender]' suffix added by ai_pdf_renamer
        name = re.sub(r'\s*-\s*From\s+.*', '', name, flags=re.IGNORECASE).strip()
        # Remove everything except letters and numbers
        return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

    def find_matching_folder(self, base_name: str) -> Optional[Dict]:
        """
        Find an existing folder that matches a given base name.
        
        This is the "matching" step — we take a base name from the
        FileGrouper (like "akshay") and look for a Drive folder with
        that name.
        
        Matching is ROBUST: it ignores spaces, special characters, and casing.
        
        Args:
            base_name: The base name to match (from FileGrouper)
        
        Returns:
            Folder dict (with 'id' and 'name') if a match is found.
            None if no matching folder exists.
        """
        # Clean the target name
        target_clean = self._clean_for_match(base_name)
        
        # Loop through all existing folders and check for a robust match
        for folder in self.get_existing_folders():
            if self._clean_for_match(folder['name']) == target_clean:
                return folder
        
        return None

    def find_or_create_project_folder(self, base_name: str) -> Dict:
        """
        Find an existing project folder or create a new one if it doesn't exist.
        
        This implements the new "auto-create" policy. If a folder like "akshay"
        doesn't exist in the root, we create it now.
        
        Args:
            base_name: The name of the folder to find/create.
            
        Returns:
            Folder dict with 'id' and 'name'.
        """
        # STEP 1: Try to find an existing folder first.
        # find_matching_folder handles case-insensitive matching.
        folder = self.find_matching_folder(base_name)
        
        if folder:
            if VERBOSE_MODE:
                print(f"  ✓ Found existing project folder: {folder['name']}")
            return folder
            
        # STEP 2: Not found — create a new one.
        # We use title case for new folder names to keep Drive looking nice.
        new_name = base_name.title()
        
        # Specific exceptions: if it's one of our special clients, use the exact name.
        if base_name.lower() == 'i1 tech inc':
            new_name = 'I1 Tech Inc'
        elif base_name.lower() == 'cloud 9 bee inc':
            new_name = 'Cloud 9 Bee Inc'
            
        if VERBOSE_MODE:
            print(f"  + Creating NEW project folder: {new_name}")
            
        # Create the new folder INSIDE our BASE_FOLDER_ID.
        new_folder = self.client.create_folder(new_name, BASE_FOLDER_ID)
        
        # IMPORTANT: Increment our created counter!
        self.folders_created_count += 1
        self.created_project_names.append(new_name)  # Remember this name for the summary
        
        # Add the new folder to our cache so we find it next time.
        if self._existing_folders is not None:
            self._existing_folders.append(new_folder)
            
        return new_folder
    
    def find_or_create_month_folder(self, parent_id: str, date: Optional[datetime] = None) -> Dict:
        """
        Find or create a month subfolder inside a project folder.
        
        If a month folder like "Feb" already exists → return it.
        If it doesn't exist → create it and return the new folder.
        
        This is the "find-or-create" pattern — it handles both cases
        so the caller doesn't need to worry about whether the folder exists.
        
        Args:
            parent_id: ID of the parent folder (the project folder).
                       Example: the ID of the "akshay" folder.
            date: Which month to use. Defaults to today's date.
                  WHY allow a custom date? For testing, or if you want
                  to upload files to a past month's folder.
        
        Returns:
            Month folder dict with 'id' and 'name'.
            Example: {'id': '1A2B3C', 'name': 'Feb'}
        
        Example:
            >>> month = navigator.find_or_create_month_folder(project_id)
            >>> print(f"Month folder: {month['name']}")  # "Feb"
        """
        # Use today's date if no specific date was provided.
        # datetime.now() gets the current date and time.
        if date is None:
            date = datetime.now()
        
        # Generate the month folder name using the format from config.
        # strftime() = "string format time" — converts a date to a string.
        # MONTH_FOLDER_FORMAT is "%b" by default, which gives abbreviated
        # month names: "Jan", "Feb", "Mar", etc.
        month_name = date.strftime(MONTH_FOLDER_FORMAT)
        
        if VERBOSE_MODE:
            print(f"  → Looking for month folder: {month_name}")
        
        # Try to find an existing month folder with this name.
        # find_folder() searches within the parent folder (our project folder).
        existing = self.client.find_folder(month_name, parent_id)
        
        if existing:
            # Folder already exists — reuse it!
            # WHY not create a duplicate? It would be confusing to have
            # two "Feb" folders inside the same project.
            if VERBOSE_MODE:
                print(f"    Found existing: {month_name}")
            return existing
        else:
            # Folder doesn't exist yet — create a new one.
            if VERBOSE_MODE:
                print(f"    Creating new: {month_name}")
            return self.client.create_folder(month_name, parent_id)
    
    def find_or_create_date_folder(self, parent_id: str, date: Optional[datetime] = None) -> Dict:
        """
        Find or create a date subfolder inside a month folder.
        
        Same pattern as find_or_create_month_folder, but for dates.
        
        If "2026-02-03" already exists → return it.
        If it doesn't exist → create it and return the new folder.
        
        WHY have date folders INSIDE month folders?
        It provides granular organization. Instead of dumping all February
        files in one "Feb" folder, each day gets its own subfolder.
        This makes it easy to find files from a specific date.
        
        Args:
            parent_id: ID of the parent folder (the month folder).
                       Example: the ID of the "Feb" folder.
            date: Which date to use. Defaults to today's date.
        
        Returns:
            Date folder dict with 'id' and 'name'.
            Example: {'id': '4D5E6F', 'name': '2026-02-03'}
        
        Example:
            >>> date_folder = navigator.find_or_create_date_folder(month_id)
            >>> print(f"Date folder: {date_folder['name']}")  # "2026-02-03"
        """
        # Use today's date if no specific date was provided.
        if date is None:
            date = datetime.now()
        
        # Generate the date folder name using the format from config.
        # DATE_FOLDER_FORMAT is "%Y-%m-%d" by default → "2026-02-03"
        date_name = date.strftime(DATE_FOLDER_FORMAT)
        
        if VERBOSE_MODE:
            print(f"  → Looking for date folder: {date_name}")
        
        # Try to find an existing date folder.
        existing = self.client.find_folder(date_name, parent_id)
        
        if existing:
            if VERBOSE_MODE:
                print(f"    Found existing: {date_name}")
            return existing
        else:
            if VERBOSE_MODE:
                print(f"    Creating new: {date_name}")
            return self.client.create_folder(date_name, parent_id)
    
    def get_upload_folder(self, base_name: str) -> Optional[Dict]:
        """
        Get the final destination folder for uploading files.
        
        This is the MAIN METHOD that other modules call. It does everything:
        1. Finds the matching project folder in Drive root
        2. Finds or creates the month subfolder
        3. Finds or creates the date subfolder
        4. Returns the date folder (that's where files get uploaded)
        
        The complete folder path is: ProjectFolder / Month / Date
        Example: akshay / Feb / 2026-02-03
        
        Args:
            base_name: The base name of the file group (from FileGrouper).
                       Example: "akshay"
        
        Returns:
            Date folder dict (with 'id' and 'name') if a matching folder exists.
            None if no matching project folder found in Drive root.
            WHY return None? Because we don't auto-create project folders.
            If "akshay" doesn't exist in Drive, we skip those files.
        
        Example:
            >>> target = navigator.get_upload_folder("akshay")
            >>> if target:
            ...     # Upload to: akshay/Feb/2026-02-03/
            ...     uploader.upload_file(file_path, target['id'])
            ... else:
            ...     print("No matching folder - skipped")
        """
        # STEP 1: Find the matching project folder in Drive root.
        # This looks for a folder named "akshay" (or whatever base_name is)
        # at the top level of Google Drive.
        # NOTE: We do NOT auto-create project folders anymore.
        # If no matching folder exists, we skip with a warning.
        project_folder = self.find_matching_folder(base_name)
        
        if not project_folder:
            # ⚠ NO matching folder found — warn the user and skip.
            print(f"\n  ⚠️  WARNING: No matching folder found for '{base_name}' in Google Drive!")
            print(f"     → These files will be SKIPPED. Create a '{base_name.title()}' folder in Drive first.")
            return None
        
        if VERBOSE_MODE:
            print(f"\n📁 Navigating to: {project_folder['name']}/")
        
        # STEP 2: Get or create the month subfolder inside the project folder.
        # Example: akshay/ → akshay/Feb/
        month_folder = self.find_or_create_month_folder(project_folder['id'])
        
        # STEP 3: Get or create the date subfolder inside the month folder.
        # Example: akshay/Feb/ → akshay/Feb/2026-02-03/
        date_folder = self.find_or_create_date_folder(month_folder['id'])
        
        if VERBOSE_MODE:
            # Show the complete folder path for the user.
            month_name = datetime.now().strftime(MONTH_FOLDER_FORMAT)
            date_name = datetime.now().strftime(DATE_FOLDER_FORMAT)
            print(f"  ✓ Target: {project_folder['name']}/{month_name}/{date_name}")
        
        # Return the date folder — this is where files will be uploaded.
        return date_folder
    
    def display_existing_folders(self) -> None:
        """
        Print a list of existing folders in Drive for the user's reference.
        
        This shows the user which folders are available to upload to.
        If no folders exist, it shows instructions for creating some.
        
        '-> None' means this method doesn't return anything —
        it just prints to the terminal (a "side effect").
        """
        # Fetch the list of existing folders.
        folders = self.get_existing_folders()
        
        # Print a formatted header.
        print(f"\n📂 Existing folders in your Drive ({len(folders)}):")
        print("-" * 40)
        
        # Handle the case where no folders exist.
        if not folders:
            print("  (No folders found)")
            print("\n  To use this tool, create folders in Google Drive first.")
            print("  Files will be matched to these folders by name.")
            return
        
        # Print each folder name with a bullet point.
        for folder in folders:
            print(f"  • {folder['name']}")
        
        print("-" * 40)
