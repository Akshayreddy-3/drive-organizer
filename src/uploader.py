"""
src/uploader.py - File Upload with Duplicate Detection

WHAT IS THIS FILE?
==================
This module handles the FINAL STEP — actually uploading files to Google Drive.
But before uploading, it checks if a similar file already exists. This prevents
accidentally uploading the same file twice.

Think of it like a mailroom worker:
1. Before putting a letter in a mailbox, they check if a similar letter
   is already there.
2. If a duplicate is found, they follow the rules:
   - 'skip' = "Don't deliver this letter, one's already there"
   - 'rename' = "Deliver it, but label it with a number (letter1, letter2)"
   - 'overwrite' = "Throw away the old letter, deliver the new one"

DUPLICATE DETECTION:
--------------------
We check for duplicates by comparing FILENAMES (not file contents).
Two files are considered "similar" if their names are ≥80% alike.

Example:
  "report.pdf" vs "report_v2.pdf" → 75% similar (NOT a duplicate)
  "report.pdf" vs "report.pdf"    → 100% similar (IS a duplicate)

WHY filename comparison (not content)?
- Comparing file contents requires downloading files from Drive (SLOW)
- Filename comparison is instant (just string comparison)
- For most use cases, same name = same file

STEP 4 (FINAL) in our pipeline:
  1. Scan files → 2. Group files → 3. Match to folders → [4. Upload]

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS — Loading the tools we need
# =============================================================================

# 'os' gives us file system functions like checking if files exist
# and extracting filenames from paths.
import os

# 'SequenceMatcher' from difflib compares two strings and calculates
# how similar they are (as a ratio from 0.0 to 1.0).
# It's part of Python's standard library — no need to install anything.
#
# HOW IT WORKS:
# SequenceMatcher finds the longest common subsequences between two strings.
# "akshay" vs "akshay" → 1.0 (100% identical)
# "report" vs "reports" → ~0.92 (92% similar)
# "hello" vs "world" → 0.2 (20% similar)
#
# WHY SequenceMatcher over other methods?
# - Simple to use (one line of code)
# - Good balance between accuracy and speed
# - Built into Python (no external dependencies)
from difflib import SequenceMatcher

# Type hints for better code readability:
# Dict = dictionary (key-value pairs like {'name': 'report.pdf'})
# List = ordered collection (like a numbered list)
# Optional = value can be the specified type OR None
from typing import Dict, List, Optional

# Import our DriveClient for making API calls to Google Drive.
from src.drive_client import DriveClient

# Import settings from config:
# DUPLICATE_HANDLING = what to do with duplicates ('skip', 'rename', 'overwrite')
# VERBOSE_MODE = whether to show detailed status messages
from src.config import DUPLICATE_HANDLING, VERBOSE_MODE


class FileUploader:
    """
    Uploads files to Google Drive with built-in duplicate detection.
    
    This is the class that does the actual heavy lifting of uploading.
    Before each upload, it checks if a similar file already exists in
    the target folder and handles it according to the DUPLICATE_HANDLING
    setting in config.
    
    Think of this class as a careful delivery person:
    1. Before dropping off a package, they check if one just like it
       was already delivered.
    2. If yes, they follow the instructions (skip, rename, or replace).
    3. Either way, they report back what happened.
    
    Attributes:
        client: DriveClient instance for making API calls
    
    Example:
        >>> uploader = FileUploader(drive_client)
        >>> result = uploader.upload_file("document.pdf", "folder123")
        >>> print(result['status'])  # 'uploaded', 'skipped', or 'error'
    """
    
    def __init__(self, drive_client: DriveClient):
        """
        Initialize the FileUploader.
        
        Args:
            drive_client: An authenticated DriveClient instance.
                          This handles the actual communication with Google Drive.
        """
        # Store the drive client for use in other methods.
        # We receive an already-authenticated client (dependency injection)
        # so we don't need to handle authentication ourselves.
        self.client = drive_client
    
    def calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate how similar two filenames are.
        
        Uses SequenceMatcher for "fuzzy" string comparison — it doesn't
        require an exact match, it measures HOW CLOSE the names are.
        
        We compare the BASE names (without extensions) because the file
        type shouldn't affect similarity. "report.pdf" and "report.docx"
        have the same name — they're just in different formats.
        
        Args:
            name1: First filename (e.g., "report.pdf")
            name2: Second filename (e.g., "report_v2.pdf")
        
        Returns:
            A float between 0.0 and 1.0:
            - 0.0 = completely different (e.g., "apple" vs "banana")
            - 1.0 = identical (e.g., "report" vs "report")
            - 0.5 = about half the characters match
        
        Example:
            >>> uploader.calculate_similarity("report.pdf", "report_v2.pdf")
            0.75
            >>> uploader.calculate_similarity("a.pdf", "b.pdf")
            0.0
            >>> uploader.calculate_similarity("test.pdf", "test.pdf")
            1.0
        """
        # STEP 1: Remove extensions for comparison.
        # os.path.splitext("report.pdf") → ("report", ".pdf")
        # [0] takes just the first part — the name without extension.
        # .lower() converts to lowercase for case-insensitive comparison.
        base1 = os.path.splitext(name1)[0].lower()
        base2 = os.path.splitext(name2)[0].lower()
        
        # STEP 2: Calculate and return the similarity ratio.
        # SequenceMatcher(None, string1, string2) sets up the comparison.
        # The first argument (None) is for a "junk" filter — None means
        # "don't ignore any characters."
        # .ratio() returns the similarity as a float between 0.0 and 1.0.
        return SequenceMatcher(None, base1, base2).ratio()
    
    def find_similar_files(
        self, 
        folder_id: str, 
        filename: str, 
        threshold: float = 0.8
    ) -> List[Dict]:
        """
        Find files in a Drive folder that have similar names to ours.
        
        This is the duplicate detection step. Before uploading "report.pdf",
        we look in the target folder and check: "Is there already a file
        with a name that's at least 80% similar?"
        
        Args:
            folder_id: ID of the Drive folder to search in.
            filename: Name of the file we want to upload (to compare against).
            threshold: Minimum similarity to consider a "match" (default 0.8 = 80%).
                       WHY 0.8? It catches exact duplicates and near-duplicates
                       (like "report" vs "report_v2") while ignoring unrelated
                       files (like "report" vs "invoice").
                       Lower = more false positives, Higher = might miss duplicates.
        
        Returns:
            List of similar files found, each with:
            - 'file': the file info dict (id, name, mimeType)
            - 'similarity': how similar it is (0.0 to 1.0)
            Returns empty list if no similar files found.
        
        Example:
            >>> similar = uploader.find_similar_files(folder_id, "report.pdf")
            >>> for s in similar:
            ...     print(f"{s['file']['name']}: {s['similarity']:.0%} similar")
            # Output: "report.pdf: 100% similar"
        """
        # Get ALL files currently in the target folder.
        # This makes one API call to Google Drive.
        existing_files = self.client.list_files_in_folder(folder_id)
        
        similar = []  # Will hold files that meet the similarity threshold
        
        # Compare our filename against every existing file in the folder.
        for file in existing_files:
            # Calculate how similar the existing file's name is to ours.
            similarity = self.calculate_similarity(filename, file['name'])
            
            # If similarity meets or exceeds our threshold, it's a match.
            # Example: threshold=0.8, similarity=0.95 → this IS a duplicate.
            # Example: threshold=0.8, similarity=0.30 → this is NOT a duplicate.
            if similarity >= threshold:
                similar.append({
                    'file': file,            # The existing file's info
                    'similarity': similarity  # How similar (for logging)
                })
        
        return similar
    
    def generate_unique_name(self, folder_id: str, filename: str) -> str:
        """
        Generate a unique filename by adding a number suffix.
        
        If "report.pdf" already exists, this returns "report1.pdf".
        If "report1.pdf" also exists, returns "report2.pdf", and so on.
        
        This is used when DUPLICATE_HANDLING = 'rename' — we keep both
        the old and new file by giving the new one a different name.
        
        Args:
            folder_id: ID of the target folder in Drive.
            filename: Original filename to make unique.
        
        Returns:
            A filename that doesn't already exist in the folder.
        
        Example:
            >>> # If "report.pdf" and "report1.pdf" already exist in the folder:
            >>> unique = uploader.generate_unique_name(folder_id, "report.pdf")
            >>> print(unique)  # "report2.pdf"
        """
        # Split the filename into name and extension.
        # os.path.splitext("report.pdf") → ("report", ".pdf")
        # This lets us insert a number BEFORE the extension.
        name, ext = os.path.splitext(filename)
        
        counter = 1        # Start numbering from 1
        new_name = filename  # Start with the original name
        
        # Keep checking names until we find one that doesn't exist.
        # This is a "while True" loop — it runs forever until we 'break'.
        while True:
            # Check if a file with this name exists in the folder.
            # find_folder() searches by name — if it finds a match, the name
            # is taken. If it returns None, the name is available.
            existing = self.client.find_folder(new_name, folder_id)
            
            if not existing:
                # No file with this name exists — it's available!
                break  # Exit the loop
            
            # Name is taken. Try the next number.
            # f"{name}{counter}{ext}" creates names like:
            #   "report1.pdf", "report2.pdf", "report3.pdf", etc.
            # Note: NO underscore between name and number (user requested this).
            new_name = f"{name}{counter}{ext}"
            counter += 1
            
            # Safety limit: if we've tried 1000 names and all are taken,
            # something is very wrong. Stop to prevent an infinite loop.
            # This should NEVER happen in practice (who has 1000 files
            # with the same name?), but it's good defensive programming.
            if counter > 1000:
                raise Exception(f"Could not generate unique name for {filename}")
        
        return new_name
    
    def upload_file(self, local_path: str, folder_id: str) -> Dict:
        """
        Upload a single file with duplicate handling.
        
        This is the MAIN UPLOAD METHOD. It's the one other modules call.
        It handles the complete upload process:
        1. Checks for similar files already in the target folder
        2. If duplicates found, handles them based on DUPLICATE_HANDLING config
        3. Uploads the file (possibly with a new name)
        4. Returns a detailed result dict
        
        The three modes of duplicate handling:
        ┌──────────────┬───────────────────────────────────────────────┐
        │ 'skip'       │ Don't upload. Return status = 'skipped'.     │
        │ 'rename'     │ Upload with a number suffix (file1.pdf).     │
        │ 'overwrite'  │ Delete old file(s), upload new one.          │
        └──────────────┴───────────────────────────────────────────────┘
        
        Args:
            local_path: Full path to the file on your computer.
                        Example: "/Users/ak/Desktop/report.pdf"
            folder_id: ID of the target folder in Google Drive.
        
        Returns:
            A dictionary with upload results:
            - 'status': 'uploaded', 'skipped', or 'error'
            - 'file': info about the uploaded file (if uploaded)
            - 'reason': why it was skipped (if skipped)
            - 'similar_files': names of similar files found
            - 'local_path': the original file path
            - 'renamed_from': original name before renaming (if renamed)
            - 'overwritten': names of deleted files (if overwritten)
        
        Example:
            >>> result = uploader.upload_file("/path/to/doc.pdf", "folder123")
            >>> if result['status'] == 'uploaded':
            ...     print(f"Uploaded as: {result['file']['name']}")
            >>> elif result['status'] == 'skipped':
            ...     print(f"Skipped: {result['reason']}")
        """
        # Extract just the filename from the full path.
        # "/Users/ak/Desktop/report.pdf" → "report.pdf"
        filename = os.path.basename(local_path)
        
        # =====================================================================
        # STEP 1: Check for similar existing files (duplicate detection)
        # =====================================================================
        # Look in the target folder for files with names similar to ours.
        # Returns a list of similar files (empty if none found).
        similar = self.find_similar_files(folder_id, filename)
        
        # =====================================================================
        # STEP 2: Handle duplicates if any were found
        # =====================================================================
        if similar:
            # Get the names of similar files for logging purposes.
            # List comprehension: extract 'name' from each similar file's info.
            similar_names = [s['file']['name'] for s in similar]
            
            if VERBOSE_MODE:
                # Show the user which similar files were found.
                print(f"  ⚠ Similar files found: {', '.join(similar_names)}")
            
            # -----------------------------------------------------------------
            # OPTION 1: SKIP — Don't upload if a similar file exists
            # -----------------------------------------------------------------
            # This is the safest option — preserves the existing file.
            # Good for when you don't want any duplicates at all.
            if DUPLICATE_HANDLING == 'skip':
                if VERBOSE_MODE:
                    print(f"    → Skipping (duplicate handling: skip)")
                
                # Return a result dict indicating the file was skipped.
                # The caller can use this info to display a summary.
                return {
                    'status': 'skipped',
                    'reason': 'similar_file_exists',
                    'similar_files': similar_names,
                    'local_path': local_path
                }
            
            # -----------------------------------------------------------------
            # OPTION 2: RENAME — Upload with a unique name (add number suffix)
            # -----------------------------------------------------------------
            # This is the middle ground — keeps BOTH old and new files.
            # The new file gets a number appended: report.pdf → report1.pdf
            elif DUPLICATE_HANDLING == 'rename':
                # Generate a unique name that doesn't conflict with existing files.
                new_name = self.generate_unique_name(folder_id, filename)
                
                if VERBOSE_MODE:
                    print(f"    → Renaming to: {new_name}")
                
                # Upload with the new name (pass custom_name to upload_file).
                file = self.client.upload_file(local_path, folder_id, new_name)
                
                return {
                    'status': 'uploaded',
                    'renamed_from': filename,  # The original name (for reference)
                    'file': file               # Info about the uploaded file
                }
            
            # -----------------------------------------------------------------
            # OPTION 3: OVERWRITE — Delete old files, upload new one
            # -----------------------------------------------------------------
            # This is the most aggressive option — replaces old with new.
            # ⚠️ WARNING: Old files are PERMANENTLY deleted!
            elif DUPLICATE_HANDLING == 'overwrite':
                # Delete ALL similar files first.
                for s in similar:
                    if VERBOSE_MODE:
                        print(f"    → Deleting: {s['file']['name']}")
                    # Permanently delete the old file from Google Drive.
                    self.client.delete_file(s['file']['id'])
                
                # Now upload the new file (with its original name).
                file = self.client.upload_file(local_path, folder_id)
                
                return {
                    'status': 'uploaded',
                    'overwritten': similar_names,  # Names of deleted files
                    'file': file
                }
        
        # =====================================================================
        # STEP 3: No duplicates found — upload normally (simplest case!)
        # =====================================================================
        # No similar files exist, so we just upload with the original name.
        file = self.client.upload_file(local_path, folder_id)
        
        return {
            'status': 'uploaded',
            'file': file
        }
    
    def upload_multiple(self, file_paths: List[str], folder_id: str) -> List[Dict]:
        """
        Upload multiple files to a folder.
        
        This is a convenience method that loops through a list of files
        and uploads each one using upload_file(). It handles errors
        for individual files without stopping the entire batch.
        
        Args:
            file_paths: List of local file paths to upload.
                        Example: ["/path/to/a.pdf", "/path/to/b.pdf"]
            folder_id: ID of the target folder in Drive.
        
        Returns:
            List of result dictionaries (one per file).
            Each dict has the same format as upload_file()'s return value.
        
        Example:
            >>> files = ["/path/to/a.pdf", "/path/to/b.pdf"]
            >>> results = uploader.upload_multiple(files, folder_id)
            >>> uploaded = sum(1 for r in results if r['status'] == 'uploaded')
            >>> print(f"Uploaded {uploaded} of {len(files)} files")
        """
        results = []  # Will hold one result dict per file
        
        if VERBOSE_MODE:
            print(f"\n📤 Uploading {len(file_paths)} file(s)...")
            print("-" * 40)
        
        # Process each file one by one.
        for path in file_paths:
            # SAFETY CHECK: Make sure the file exists on this computer.
            # os.path.exists() returns True if the path is valid.
            if not os.path.exists(path):
                if VERBOSE_MODE:
                    print(f"  ✗ File not found: {path}")
                # Skip this file and record the error.
                results.append({
                    'status': 'error',
                    'local_path': path,
                    'reason': 'file_not_found'
                })
                continue  # Move to the next file
            
            # Try to upload the file. If anything goes wrong, catch the error
            # and continue with the remaining files instead of crashing.
            # This is called "graceful error handling" — one bad file
            # shouldn't prevent all the other files from being uploaded.
            try:
                result = self.upload_file(path, folder_id)
                results.append(result)
            except Exception as e:
                # 'Exception as e' catches ANY error and stores it in 'e'.
                if VERBOSE_MODE:
                    print(f"  ✗ Error uploading {path}: {e}")
                results.append({
                    'status': 'error',
                    'local_path': path,
                    'reason': str(e)  # Convert exception to string for logging
                })
        
        # =====================================================================
        # Print a summary of the batch upload
        # =====================================================================
        if VERBOSE_MODE:
            print("-" * 40)
            # Count results by status using a generator expression with sum().
            # sum(1 for r in results if r['status'] == 'uploaded')
            # This counts how many results have status == 'uploaded'.
            uploaded = sum(1 for r in results if r['status'] == 'uploaded')
            skipped = sum(1 for r in results if r['status'] == 'skipped')
            errors = sum(1 for r in results if r['status'] == 'error')
            print(f"✓ Complete: {uploaded} uploaded, {skipped} skipped, {errors} errors")
        
        return results
