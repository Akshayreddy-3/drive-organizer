"""
folder_manager.py - Folder Structure Manager (Legacy)

WHAT IS THIS FILE?
==================
This module manages the folder hierarchy in Google Drive.
It creates and navigates the structure: Project → Month → Date

Example:
    If you upload "akshay123.pdf", this module ensures the folder path
    akshay/ → Feb/ → 2026-02-03/ exists in Drive, creating any missing
    folders along the way.

NOTE: Auto-creation of top-level project folders has been DISABLED.
If a project folder doesn't exist, files are skipped with a warning.
Month/date subfolders are still auto-created inside existing projects.

This module also has sanitize_project_name() which cleans up filenames
into safe folder names by removing numbers and special characters:
    "akshay12345.pdf" → "Akshay"
    "invoice_001.pdf" → "Invoice"
    "12345.pdf" → "Misc"

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS
# =============================================================================

# 'datetime' for generating month/date folder names from the current date.
from datetime import datetime

# Import the DriveService class for making Google Drive API calls.
from drive_service import DriveService

# MONTH_FOLDER_FORMAT = "%b" → "Feb"
# DATE_FOLDER_FORMAT = "%Y-%m-%d" → "2026-02-03"
# BASE_FOLDER_ID = target root folder
from config import MONTH_FOLDER_FORMAT, DATE_FOLDER_FORMAT, BASE_FOLDER_ID


class FolderManager:
    """
    Manages the folder hierarchy in Google Drive: Project > Month > Date.
    
    Think of this like a filing cabinet organizer:
    - Drawer = Project folder (e.g., "Akshay")
    - Divider = Month folder (e.g., "Feb")
    - Folder = Date folder (e.g., "2026-02-03")
    
    This class creates this structure automatically when uploading files.
    
    Attributes:
        drive: DriveService instance for making API calls
    """
    
    def __init__(self, drive_service: DriveService):
        """
        Initialize the FolderManager.
        
        Args:
            drive_service: An authenticated DriveService instance.
        """
        # Store the drive service for use in other methods.
        self.drive = drive_service
        
        # Counter for how many NEW project folders we create in this session.
        self.folders_created_count = 0
        self.created_project_names = []  # List of names for the final summary

    def sanitize_project_name(self, raw_name: str) -> str:
        """
        Clean up a filename into a safe, readable folder name.
        
        This takes a raw filename (like "akshay12345.pdf") and produces
        a clean project name (like "Akshay") suitable for a Google Drive
        folder name.
        
        SANITIZATION RULES:
        1. Remove the file extension (.pdf, .docx, etc.)
        2. Remove all digits and special characters (!@#$%^&*, etc.)
        3. Keep only letters and spaces
        4. Collapse multiple spaces into one
        5. Convert to Title Case (first letter of each word capitalized)
        6. If nothing is left (name was all numbers), return "Misc"
        
        Args:
            raw_name: The original filename (e.g., "akshay12345.pdf")
        
        Returns:
            A cleaned-up, Title Case project name string.
        
        Examples:
            >>> fm.sanitize_project_name("akshay12345.pdf")
            'Akshay'
            >>> fm.sanitize_project_name("invoice_001.pdf")
            'Invoice'
            >>> fm.sanitize_project_name("12345.pdf")
            'Misc'
            >>> fm.sanitize_project_name("my report 2024.docx")
            'My Report'
        """
        # Import 're' (regular expressions) — a tool for pattern matching.
        # Imported here (not at the top) because it's only used in this method.
        import re

        # Handle empty input — return "Misc" as a fallback.
        if not raw_name:
            return 'Misc'

        # Start with the raw name.
        name = raw_name
        
        # Remove the file extension if present.
        # rsplit('.', 1) splits from the RIGHT on the FIRST dot.
        # Example: "report.v2.pdf" → ["report.v2", "pdf"]
        # [0] takes the part before the last dot = "report.v2"
        if '.' in name:
            name = name.rsplit('.', 1)[0]

        # Remove everything that's NOT a letter or space.
        # re.sub(pattern, replacement, string) replaces matches with ''.
        # [^A-Za-z\s] means "any character that is NOT a letter or whitespace."
        # The ^ inside [] means "NOT" — it's the negation operator.
        cleaned = re.sub(r'[^A-Za-z\s]', '', name)

        # Clean up whitespace: collapse multiple spaces and trim edges.
        # cleaned.split() splits on any whitespace and removes empty strings.
        # ' '.join() puts them back together with single spaces.
        # .strip() removes leading/trailing whitespace.
        cleaned = ' '.join(cleaned.split()).strip()

        # If the cleaned name is empty (original was all numbers/symbols),
        # return "Misc" as a catch-all folder name.
        if not cleaned:
            return 'Misc'

        # Convert to Title Case for nice-looking folder names.
        # title() capitalizes the first letter of EACH word:
        # "my report" → "My Report"
        result = cleaned.title()

        # STEP 1: Handle Special Exceptions
        # Some project names have numbers that MUST be kept (like "I1 Tech Inc").
        # We check for these before the main stripping logic removes them.
        # We compare lowercase search strings to the original raw_name.
        raw_lower = raw_name.lower()
        if 'i1 tech inc' in raw_lower:
            return 'I1 Tech Inc'
        if 'cloud 9 bee inc' in raw_lower:
            return 'Cloud 9 Bee Inc'

        return result
    
    def find_or_create_folder(self, folder_name: str, parent_id: str = None) -> dict:
        """
        Find an existing folder or create it if it doesn't exist.
        
        This is the "find-or-create" pattern — also known as "upsert"
        (update or insert). It ensures the folder exists without creating
        duplicates.
        
        KEY DIFFERENCE from src/folder_navigator.py:
        This method WILL create folders at ANY level, including project
        folders in the Drive root. The newer version only creates
        month/date subfolders, not project folders.
        
        Args:
            folder_name: Name of the folder to find or create.
            parent_id: Optional parent folder ID.
                       If None, operates at the Drive root level.
        
        Returns:
            Folder info dict (id, name) — either existing or newly created.
        """
        # First, try to find the folder by name.
        folder = self.drive.search_folder(folder_name, parent_id)
        
        if folder:
            # Folder exists — reuse it (don't create a duplicate).
            print(f"→ Found existing folder: {folder['name']}")
            return folder
        else:
            # Folder doesn't exist.
            # If parent_id is None, it's a top-level project folder.
            # We do NOT auto-create project folders — skip with a warning.
            if parent_id is None:
                print(f"⚠️  WARNING: No matching folder found for '{folder_name}' in Google Drive!")
                print(f"   → These files will be SKIPPED. Create a '{folder_name}' folder in Drive first.")
                return None
            
            # For subfolders (month/date), still auto-create them.
            print(f"→ Subfolder not found, creating: {folder_name}")
            return self.drive.create_folder(folder_name, parent_id)
    
    def get_or_create_month_folder(self, parent_id: str, date: datetime = None) -> dict:
        """
        Find or create a month subfolder inside a parent folder.
        
        Uses the MONTH_FOLDER_FORMAT from config to generate the name.
        Default format "%b" gives abbreviated month names like "Feb".
        
        Args:
            parent_id: ID of the parent folder (the project folder).
            date: Date to use for the month name. Defaults to today.
        
        Returns:
            Month folder info dict (id, name).
        """
        # Default to today's date if none specified.
        if date is None:
            date = datetime.now()
        
        # Generate the month folder name.
        # strftime() converts the date to a formatted string.
        # MONTH_FOLDER_FORMAT = "%b" → "Feb"
        month_name = date.strftime(MONTH_FOLDER_FORMAT)
        
        # Find or create the month folder inside the parent.
        return self.find_or_create_folder(month_name, parent_id)
    
    def create_date_folder(self, parent_id: str, date: datetime = None) -> dict:
        """
        Find or create a date subfolder inside a month folder.
        
        Uses DATE_FOLDER_FORMAT from config for the name.
        Default format "%Y-%m-%d" gives ISO dates like "2026-02-03".
        
        Args:
            parent_id: ID of the parent folder (the month folder).
            date: Date to use. Defaults to today.
        
        Returns:
            Date folder info dict (id, name).
        """
        if date is None:
            date = datetime.now()
        
        # Generate the date folder name.
        # DATE_FOLDER_FORMAT = "%Y-%m-%d" → "2026-02-03"
        date_name = date.strftime(DATE_FOLDER_FORMAT)
        
        return self.find_or_create_folder(date_name, parent_id)
    
    def setup_folder_structure(self, project_name: str) -> dict:
        """
        Set up the COMPLETE folder structure: Project > Month > Date.
        
        This is the MAIN METHOD that other modules call. It creates
        the full 3-level folder hierarchy and returns the deepest folder
        (the date folder) where files should be uploaded.
        
        Args:
            project_name: Name of the project folder (e.g., "Akshay").
        
        Returns:
            Date folder info dict — this is the upload destination.
            The complete path is: ProjectName/MonthAbbr/YYYY-MM-DD
            Example: Akshay/Feb/2026-02-03
        
        Example:
            >>> target = fm.setup_folder_structure("Akshay")
            >>> uploader.upload_file("report.pdf", target['id'])
        """
        # Print a header for this operation.
        print(f"\n📁 Setting up folder structure for: {project_name}")
        print("-" * 40)
        
        # STEP 1: Find the PROJECT folder at Drive root.
        # Example: "Akshay" folder at the top level of Google Drive.
        # NOTE: We no longer auto-create project folders.
        project_folder = self.find_or_create_folder(project_name)
        
        # If no matching project folder was found, return None.
        if not project_folder:
            return None
        
        # STEP 2: Find or create the MONTH folder inside the project folder.
        # Example: "Feb" folder inside "Akshay".
        month_folder = self.get_or_create_month_folder(project_folder['id'])
        
        # STEP 3: Find or create the DATE folder inside the month folder.
        # Example: "2026-02-03" folder inside "Feb".
        date_folder = self.create_date_folder(month_folder['id'])
        
        # Print the complete folder path for confirmation.
        print("-" * 40)
        print(f"✓ Folder structure ready: {project_name}/{month_folder['name']}/{date_folder['name']}")
        
        # Return the date folder — this is where files will be uploaded.
        return date_folder
