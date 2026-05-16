#!/usr/bin/env python3
"""
run_upload.py - Main Entry Point for Drive Organizer (v2)

WHAT IS THIS FILE?
==================
This is the MAIN SCRIPT you run to upload files to Google Drive.
It's the "conductor" of the orchestra — it doesn't play any instruments
(doesn't do the actual work), but it tells each section (module) when
to play and coordinates everything.

THE 5-STEP PIPELINE:
====================
  STEP 1: Scan your Desktop (or a specified folder) for files
  STEP 2: Group files by base name (akshay123.pdf → "akshay" group)
  STEP 3: Connect to Google Drive (authenticate)
  STEP 4: Check which folders exist in your Drive root
  STEP 5: Match groups to folders and upload files

REQUIREMENTS:
-------------
Before running, you need:
1. Google Cloud credentials (credentials.json) — your app's identity
2. Existing folders in your Google Drive to upload to
   (the app matches files to these folders by name)

USAGE:
------
    # Run the upload (scans Desktop by default)
    python run_upload.py

    # Preview what will be uploaded (no actual upload — safe to run!)
    python run_upload.py --preview

    # Scan a specific folder instead of Desktop
    python run_upload.py --path /path/to/folder

    # Suppress detailed output
    python run_upload.py --quiet

    # Show all available options
    python run_upload.py --help

WORKFLOW DIAGRAM:
-----------------
    Desktop Files          Grouped By Name         Matched to Drive
    ─────────────          ──────────────          ────────────────
    akshay123.pdf    →     akshay/ (2 files)   →   akshay/Feb/2026-02-03/
    akshay456.pdf
    invoice_001.pdf  →     invoice/ (1 file)   →   invoice/Feb/2026-02-03/
    random.pdf       →     random/ (1 file)    →   ⚠ SKIPPED (no folder)

NOTE vs main.py:
================
This file uses the NEWER modules in the src/ folder.
main.py uses the older root-level modules.
Both work, but this one (run_upload.py) is recommended.

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS
# =============================================================================

# 'sys' provides system-level functions like sys.exit() to stop the program.
# sys.exit(0) = exit successfully, sys.exit(1) = exit with an error.
import sys

# 'argparse' is Python's built-in library for parsing command-line arguments.
# It lets users pass options like --preview or --path /some/folder when
# running the script from the terminal.
# Think of it like filling out a form: "--preview" is a checkbox, 
# "--path" is a text field where you type a folder path.
import argparse
import os

# 'datetime' handles dates and times.
# We use it to show when the upload started in the terminal.
from datetime import datetime

# Import our custom modules from the src/ package.
# Each module handles one specific job (separation of concerns):
from src.drive_client import DriveClient        # Talks to Google Drive API
from src.file_scanner import FileScanner        # Finds files on your computer
from src.file_grouper import FileGrouper        # Groups files by base name
from src.folder_navigator import FolderNavigator  # Navigates Drive folder structure
from src.uploader import FileUploader           # Uploads files with duplicate handling
from src.config import VERBOSE_MODE             # Whether to show detailed output
from src.data_tracker import DataTracker        # Tracks history for the dashboard


def parse_arguments():
    """
    Parse command-line arguments.
    
    Command-line arguments let you customize the script's behavior
    WITHOUT changing the code. They're the options you type after
    "python run_upload.py" in the terminal.
    
    AVAILABLE ARGUMENTS:
    --preview  : Show what WOULD happen without actually uploading
    --path     : Specify a folder to scan (default: Desktop)
    --quiet    : Don't show detailed output
    
    Returns:
        Namespace object with these attributes:
        - args.preview (bool): True if --preview was passed
        - args.path (str or None): custom folder path, or None for Desktop
        - args.quiet (bool): True if --quiet was passed
    
    Example:
        >>> args = parse_arguments()
        >>> if args.preview:
        ...     print("Preview mode!")
    """
    # Create an argument parser with a description and examples.
    # description = shown when user runs: python run_upload.py --help
    # formatter_class = preserves the whitespace in our epilog text
    # epilog = shown at the bottom of the help text
    parser = argparse.ArgumentParser(
        description="Upload files from Desktop to Google Drive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_upload.py                    Upload from Desktop
  python run_upload.py --preview          Preview only (no upload)
  python run_upload.py --path /my/folder  Scan specific folder
        """
    )
    
    # Add the --preview flag.
    # 'action=store_true' means: if --preview is present, set it to True.
    # If not present, it defaults to False.
    # This is a "flag" argument — it has no value, just on or off.
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Preview what will be uploaded without actually uploading'
    )
    
    # Add the --path option.
    # 'type=str' means the value should be a string (a folder path).
    # 'default=None' means if not provided, path is None (use Desktop).
    # This is a "value" argument — it requires a value after it.
    parser.add_argument(
        '--path',
        type=str,
        default=None,
        help='Path to scan for files (default: Desktop)'
    )
    
    # Add the --quiet flag.
    # When enabled, suppresses detailed (verbose) output.
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress detailed output'
    )
    
    # Parse and return the arguments.
    # parse_args() reads sys.argv (the command-line input) and extracts
    # the values into a Namespace object.
    return parser.parse_args()


def main():
    """
    Main entry point for the Drive Organizer v2.
    
    This function orchestrates the ENTIRE upload process in 5 steps:
    1. Parse command-line arguments
    2. Scan local files
    3. Group files by base name
    4. Connect to Google Drive and check existing folders
    5. Match groups to folders and upload
    
    Each step prints a clear header so the user knows what's happening.
    If anything goes wrong, errors are caught and shown clearly.
    """
    # =========================================================================
    # STEP 0: Parse command-line arguments
    # =========================================================================
    # Read --preview, --path, and --quiet from the command line.
    args = parse_arguments()
    
    # Print a styled header banner.
    print("\n" + "=" * 60)
    print("  📁 Google Drive File Organizer v2")
    print("=" * 60)
    
    # Show the current date and time so the user knows when the upload started.
    # strftime() formats the datetime as a readable string.
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # If in preview mode, show a clear banner so the user doesn't panic
    # thinking files are actually being uploaded.
    if args.preview:
        print("🔍 PREVIEW MODE - No files will be uploaded")
    
    # =========================================================================
    # STEP 1: Scan local files
    # =========================================================================
    # Find all files in the target directory (Desktop or custom path).
    print("\n" + "-" * 60)
    print("STEP 1: Scanning for files")
    print("-" * 60)
    
    try:
        # Create a FileScanner for the specified path (or Desktop by default).
        # args.path is None if the user didn't specify --path, which makes
        # FileScanner default to the Desktop folder.
        scanner = FileScanner(args.path)
        
        # Get all files (with filtering applied from config settings).
        files = scanner.get_all_files()
    except Exception as e:
        # If scanning fails (bad path, permissions error, etc.), show error and exit.
        print(f"❌ Error scanning: {e}")
        sys.exit(1)
    
    # If no files were found, there's nothing to do.
    if not files:
        print("⚠ No files found. Nothing to upload.")
        sys.exit(0)  # Exit with code 0 (success — not an error, just nothing to do)
    
    print(f"✓ Found {len(files)} files")
    
    # Show a summary of the scanned files (total size, etc.)
    summary = scanner.get_summary()
    print(f"  Total size: {summary['total_size_human']}")
    
    # =========================================================================
    # STEP 2: Group files by base name
    # =========================================================================
    # Organize files into groups based on their core filename.
    # "akshay123.pdf" and "akshay456.pdf" → both go in the "akshay" group.
    print("\n" + "-" * 60)
    print("STEP 2: Grouping files by name")
    print("-" * 60)
    
    # Create a FileGrouper instance.
    grouper = FileGrouper()
    
    # Convert Path objects to strings (grouper expects string paths).
    # str(f) turns Path("/Users/ak/Desktop/report.pdf") into a string.
    file_paths = [str(f) for f in files]
    
    # Group the files by base name.
    # Returns: {"akshay": [path1, path2], "invoice": [path3], ...}
    groups = grouper.group_files(file_paths)
    
    print(f"✓ Created {len(groups)} groups")
    
    # Show the groups visually so the user can verify the grouping.
    grouper.display_groups(groups)
    
    # =========================================================================
    # STEP 3: Connect to Google Drive
    # =========================================================================
    # Authenticate with Google and create a Drive API connection.
    print("\n" + "-" * 60)
    print("STEP 3: Connecting to Google Drive")
    print("-" * 60)
    
    try:
        # DriveClient() handles OAuth authentication automatically.
        # First run: opens browser for Google login.
        # Subsequent runs: uses saved token (no browser needed).
        client = DriveClient()
    except FileNotFoundError as e:
        # credentials.json is missing — show the error and exit.
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        # Any other authentication error.
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)
    
    # =========================================================================
    # STEP 4: Check existing folders in Drive
    # =========================================================================
    # List all top-level folders in the user's Google Drive.
    # Files can only be uploaded to EXISTING folders — we don't auto-create.
    print("\n" + "-" * 60)
    print("STEP 4: Checking existing folders in Drive")
    print("-" * 60)
    
    # Create a FolderNavigator to manage Drive folder operations.
    navigator = FolderNavigator(client)
    
    # Display all existing folders so the user can see what's available.
    navigator.display_existing_folders()
    
    # Get lowercase folder names for matching.
    # Used to check: "does a folder named 'akshay' exist in Drive?"
    existing_names = navigator.get_folder_names()
    
    # =========================================================================
    # STEP 5: Match groups to folders and upload
    # =========================================================================
    # For each file group, check if a matching folder exists in Drive.
    # If yes → upload files to that folder (inside month/date subfolders).
    # If no → skip those files (user needs to create the folder first).
    print("\n" + "-" * 60)
    print("STEP 5: Uploading files to matching folders")
    print("-" * 60)
    
    if args.preview:
        print("\n🔍 PREVIEW - showing what would happen:\n")
    
    # Create a FileUploader for uploading with duplicate handling.
    uploader = FileUploader(client)
    
    # Counters for the final summary.
    total_scanned = len(files)  # Total files found during Step 1
    total_uploaded = 0          # Files successfully uploaded
    total_skipped = 0           # Files skipped (duplicates)
    total_errors = 0            # Files that failed to upload
    
    # Track files that were NOT uploaded for the final list.
    not_uploaded = []
    
    # Track folder paths and upload results for the dashboard.
    folder_paths = {}      # {group_name: "project/month/date"}
    upload_results = {}    # {group_name: [result_dicts]}
    
    # Process each group of files.
    # sorted() processes groups alphabetically for organized output.
    # .items() gives us (key, value) pairs: (base_name, list_of_files)
    for base_name, group_files in sorted(groups.items()):
        print(f"\n📂 Processing: {base_name}/ ({len(group_files)} files)")
        
        # CHECK: Does a folder with this name exist in the user's Drive?
        # If no matching folder exists, files are SKIPPED with a warning.
        # We do NOT auto-create project folders.
        
        # If in preview mode, just show what WOULD happen, don't upload.
        if args.preview:
            print(f"   ✓ Would upload to: {base_name}/[month]/[date]/")
            for f in group_files:
                print(f"      └── {os.path.basename(f)}")
            continue  # Move to the next group (no actual upload)
        
        # Get the full target folder path (project/month/date).
        # This also creates the month and date subfolders if they don't exist.
        target = navigator.get_upload_folder(base_name)
        
        if not target:
            # No matching folder found in Drive — skip these files.
            for f in group_files:
                not_uploaded.append({'name': os.path.basename(f), 'reason': f'No matching folder in Drive for "{base_name}"'})
            continue
        
        # Build the folder path string for the dashboard tracker.
        # Format: "ProjectName/Month/Date"
        from datetime import datetime as dt
        month_name = dt.now().strftime("%b")
        date_name = dt.now().strftime("%Y-%m-%d")
        folder_paths[base_name] = f"{base_name.title()}/{month_name}/{date_name}"
        
        # Upload ALL files in this group to the target folder.
        # upload_multiple handles each file individually and returns results.
        results = uploader.upload_multiple(group_files, target['id'])
        
        # Store results for the dashboard tracker.
        upload_results[base_name] = results
        
        # Count the results for our summary.
        for r in results:
            if r['status'] == 'uploaded':
                total_uploaded += 1
            elif r['status'] == 'skipped':
                total_skipped += 1
                not_uploaded.append({'name': os.path.basename(r['local_path']), 'reason': 'Duplicate'})
            else:  # 'error'
                total_errors += 1
                not_uploaded.append({'name': os.path.basename(r.get('local_path', 'unknown')), 'reason': 'Upload error'})
    
    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    # Show a clear summary of what happened.
    print("\n" + "=" * 60)
    print("  ✅ UPLOAD COMPLETE")
    print("=" * 60)
    
    if args.preview:
        # Preview mode summary — no actual uploads happened.
        print(f"\n📊 Preview Summary:")
        print(f"   • Groups to process: {len(groups)}")
        print(f"   • Files found:      {total_scanned}")
        print("   ℹ Files are only uploaded to EXISTING folders in Drive.")
    else:
        # Full upload summary.
        print(f"\n📊 Final Results:")
        print(f"   • Total files scanned:  {total_scanned}")
        print(f"   • Files uploaded:       {total_uploaded}")
        print(f"   • Name folders created: {navigator.folders_created_count}")
        
        # If we created new folders, list them so the user knows which ones.
        if navigator.created_project_names:
            print("     → Created: " + ", ".join(navigator.created_project_names))
        
        # List files that were NOT uploaded if any exist.
        if not_uploaded:
            print(f"\n⚠ Files NOT uploaded ({len(not_uploaded)}):")
            for item in not_uploaded:
                print(f"   - {item['name']} ({item['reason']})")
        else:
            print("\n✓ All scanned files were successfully uploaded!")

    print("\n" + "=" * 60)
    
    # =========================================================================
    # STEP 6: Run the Counter Program
    # =========================================================================
    # User requested to run the desktop_file_counter after the upload.
    # We use subprocess to run it as a separate script.
    import subprocess


    print("\n📦 Running Desktop File Counter...")
    print("-" * 60)
    
    # Path to the counter script (should be in the same folder as this script)
    counter_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop_file_counter.py")
    
    if os.path.exists(counter_script):
        try:
            # Run the script and let it print its own output directly to the terminal.
            subprocess.run([sys.executable, counter_script], check=True)
        except Exception as e:
            print(f"⚠ Could not run counter program: {e}")
    else:
        print("⚠ desktop_file_counter.py not found.")

    print("\n" + "=" * 60 + "\n")
    
    # =========================================================================
    # STEP 7: Log data for Dashboard
    # =========================================================================
    # Save the run details to tracker_data.json
    try:
        tracker = DataTracker()
        tracker.log_run(
            groups, 
            is_preview=args.preview,
            upload_results=upload_results if not args.preview else None,
            folder_paths=folder_paths if not args.preview else None
        )
        if not args.quiet:
            print("📊 Run data logged for dashboard.")
    except Exception as e:
        print(f"⚠ Could not log run data: {e}")

# =============================================================================
# ENTRY POINT
# =============================================================================
# This block runs ONLY when this file is executed directly:
#   python run_upload.py
# It does NOT run if this file is imported as a module.
if __name__ == "__main__":
    main()
