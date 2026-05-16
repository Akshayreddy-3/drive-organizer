"""
file_uploader.py - File Upload with Duplicate Detection (Legacy)

WHAT IS THIS FILE?
==================
This module handles uploading files to Google Drive with built-in
duplicate detection. Before uploading a file, it checks if a similar
file already exists in the target folder.

This is the LEGACY version used by main.py. The newer version is
src/uploader.py, which has more features (like upload_multiple).

DUPLICATE DETECTION:
--------------------
We compare filenames using the SequenceMatcher algorithm:
- If two filenames are ≥80% similar → considered a "duplicate"
- Based on the DUPLICATE_HANDLING setting, we either skip, rename,
  or overwrite the existing file

RENAMING FORMAT:
----------------
When DUPLICATE_HANDLING is 'rename', duplicates get a number suffix:
    report.pdf → report1.pdf → report2.pdf → report3.pdf
(No underscore before the number — per user request)

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS
# =============================================================================

# 'os' for file system operations (path handling, file existence checks).
import os

# 'SequenceMatcher' compares two strings and calculates how similar they are.
# Returns a ratio between 0.0 (completely different) and 1.0 (identical).
# Built into Python's standard library — no installation needed.
from difflib import SequenceMatcher

# DriveService handles the actual Google Drive API calls.
from drive_service import DriveService

# DUPLICATE_HANDLING = 'skip', 'rename', or 'overwrite' (from config.py).
from config import DUPLICATE_HANDLING


class FileUploader:
    """
    Handles file uploads with duplicate detection (legacy version).
    
    Before uploading a file, this class:
    1. Lists all files in the target folder
    2. Compares each existing file's name to the new file's name
    3. If similarity ≥ 80% → handles as duplicate (skip/rename/overwrite)
    4. If no similar files found → uploads normally
    
    Attributes:
        drive: DriveService instance for making API calls
    """
    
    def __init__(self, drive_service: DriveService):
        """
        Initialize the FileUploader.
        
        Args:
            drive_service: An authenticated DriveService instance.
        """
        # Store the drive service for use in other methods.
        self.drive = drive_service
    
    def get_similarity_ratio(self, name1: str, name2: str) -> float:
        """
        Calculate how similar two filenames are (0.0 to 1.0).
        
        Compares base names (without extensions) for better matching.
        This way, "report.pdf" and "report.docx" would be 100% similar,
        since they share the same base name.
        
        Args:
            name1: First filename (e.g., "report.pdf")
            name2: Second filename (e.g., "report_v2.pdf")
        
        Returns:
            Float between 0.0 (completely different) and 1.0 (identical).
        
        Examples:
            >>> uploader.get_similarity_ratio("report.pdf", "report.pdf")
            1.0
            >>> uploader.get_similarity_ratio("hello.pdf", "world.pdf")
            0.2
        """
        # Remove extensions and convert to lowercase for fair comparison.
        # os.path.splitext("report.pdf") → ("report", ".pdf")
        # [0] takes just the name part, .lower() makes it case-insensitive.
        base1 = os.path.splitext(name1)[0].lower()
        base2 = os.path.splitext(name2)[0].lower()
        
        # SequenceMatcher(None, str1, str2) compares the two strings.
        # .ratio() returns the similarity as a float.
        # None means "don't ignore any characters."
        return SequenceMatcher(None, base1, base2).ratio()
    
    def check_similar_files(self, folder_id: str, filename: str, threshold: float = 0.8) -> list:
        """
        Find files in a Drive folder that have names similar to ours.
        
        This is the "duplicate detector." It looks at every file in the
        target folder and checks if any names are ≥80% similar to the
        file we want to upload.
        
        Args:
            folder_id: ID of the Google Drive folder to check.
            filename: Name of the file we're about to upload.
            threshold: Minimum similarity to consider a "match" (default 0.8).
                       0.8 = 80% similar. Higher = stricter matching.
        
        Returns:
            List of dicts, each containing:
            - 'file': the existing file's info (id, name, mimeType)
            - 'similarity': how similar it is (float 0.0-1.0)
            Empty list if no similar files found.
        """
        # Get all files currently in the target folder.
        existing_files = self.drive.list_files_in_folder(folder_id)
        similar_files = []
        
        # Compare our filename against every existing file.
        for file in existing_files:
            similarity = self.get_similarity_ratio(filename, file['name'])
            
            # If the similarity meets/exceeds the threshold, it's a match.
            if similarity >= threshold:
                similar_files.append({
                    'file': file,
                    'similarity': similarity
                })
        
        return similar_files
    
    def generate_unique_name(self, folder_id: str, filename: str) -> str:
        """
        Generate a unique filename by adding a number suffix.
        
        If "report.pdf" exists, returns "report1.pdf".
        If "report1.pdf" also exists, returns "report2.pdf", and so on.
        
        NOTE: The number is appended DIRECTLY to the name (no underscore).
        This was specifically requested by the user:
            ✓ "report1.pdf"  (correct)
            ✗ "report_1.pdf" (old behavior, changed)
        
        Args:
            folder_id: Target folder ID in Drive.
            filename: Original filename to make unique.
        
        Returns:
            A filename that doesn't currently exist in the folder.
        """
        # Split filename into name and extension.
        # "report.pdf" → name="report", ext=".pdf"
        name, ext = os.path.splitext(filename)
        counter = 1
        new_name = filename
        
        # Keep trying names until we find one that's not taken.
        # search_folder() returns None if the name doesn't exist in the folder.
        while self.drive.search_folder(new_name, folder_id):
            # Create a new name with the counter appended DIRECTLY.
            # "report" + "1" + ".pdf" = "report1.pdf"
            new_name = f"{name}{counter}{ext}"
            counter += 1
        
        return new_name
    
    def upload_file(self, file_path: str, folder_id: str) -> dict:
        """
        Upload a single file with duplicate checking.
        
        This is the MAIN UPLOAD METHOD. It:
        1. Checks for similar files in the target folder
        2. Handles duplicates based on DUPLICATE_HANDLING config
        3. Uploads the file (possibly with a renamed name)
        4. Returns a result dict with status info
        
        DUPLICATE HANDLING MODES:
        ┌──────────────┬──────────────────────────────────────────┐
        │ 'skip'       │ Don't upload (existing file wins)       │
        │ 'rename'     │ Upload as report1.pdf, report2.pdf etc  │
        │ 'overwrite'  │ Delete existing, upload new (PERMANENT) │
        └──────────────┴──────────────────────────────────────────┘
        
        Args:
            file_path: Full local path to the file.
            folder_id: Target folder ID in Google Drive.
        
        Returns:
            Dict with:
            - 'status': 'uploaded', 'skipped', or 'error'
            - 'file': uploaded file info (if uploaded)
            - 'reason': why skipped (if skipped)
            - 'similar_files': names of similar existing files
            - 'renamed_from': original name (if renamed)
            - 'overwritten': deleted file names (if overwritten)
        """
        # Get just the filename from the full path.
        filename = os.path.basename(file_path)
        
        # STEP 1: Check for similar existing files.
        similar = self.check_similar_files(folder_id, filename)
        
        # STEP 2: Handle duplicates if any were found.
        if similar:
            # Get names of similar files for display.
            similar_names = [s['file']['name'] for s in similar]
            print(f"⚠ Found similar files: {', '.join(similar_names)}")
            
            # --- SKIP MODE ---
            if DUPLICATE_HANDLING == 'skip':
                print(f"→ Skipping upload (duplicate handling: skip)")
                return {
                    'status': 'skipped',
                    'reason': 'similar_file_exists',
                    'similar_files': similar_names
                }
            
            # --- RENAME MODE ---
            elif DUPLICATE_HANDLING == 'rename':
                # Generate a unique name (e.g., report1.pdf).
                new_name = self.generate_unique_name(folder_id, filename)
                print(f"→ Renaming to: {new_name}")
                # Upload with the new name.
                file = self.drive.upload_file(file_path, folder_id, new_name)
                return {
                    'status': 'uploaded',
                    'renamed_from': filename,
                    'file': file
                }
            
            # --- OVERWRITE MODE ---
            elif DUPLICATE_HANDLING == 'overwrite':
                # Delete all similar existing files first.
                for s in similar:
                    print(f"→ Deleting existing: {s['file']['name']}")
                    self.drive.delete_file(s['file']['id'])
                
                # Upload the new file with its original name.
                file = self.drive.upload_file(file_path, folder_id)
                return {
                    'status': 'uploaded',
                    'overwritten': similar_names,
                    'file': file
                }
        
        # STEP 3: No duplicates found — upload normally.
        file = self.drive.upload_file(file_path, folder_id)
        return {
            'status': 'uploaded',
            'file': file
        }
    
    def upload_multiple_files(self, file_paths: list, folder_id: str) -> list:
        """
        Upload multiple files to a folder, one at a time.
        
        Handles errors for individual files without stopping the batch.
        Shows a summary when complete.
        
        Args:
            file_paths: List of local file paths to upload.
            folder_id: Target folder ID in Google Drive.
        
        Returns:
            List of result dicts (one per file), same format as upload_file().
        """
        results = []
        
        print(f"\n📤 Uploading {len(file_paths)} file(s)...")
        print("-" * 40)
        
        for path in file_paths:
            # Check if the file exists before trying to upload.
            if os.path.exists(path):
                result = self.upload_file(path, folder_id)
                results.append(result)
            else:
                # File doesn't exist — record the error but continue.
                print(f"✗ File not found: {path}")
                results.append({
                    'status': 'error',
                    'path': path,
                    'error': 'File not found'
                })
        
        print("-" * 40)
        
        # Print a summary of the batch upload.
        # sum(1 for r in results if condition) counts matching items.
        uploaded = sum(1 for r in results if r['status'] == 'uploaded')
        skipped = sum(1 for r in results if r['status'] == 'skipped')
        errors = sum(1 for r in results if r['status'] == 'error')
        
        print(f"✓ Upload complete: {uploaded} uploaded, {skipped} skipped, {errors} errors")
        
        return results
