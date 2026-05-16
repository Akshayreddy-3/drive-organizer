#!/usr/bin/env python3
"""
Auto Upload - Fully automatic desktop file uploader with smart grouping

Runs without any user interaction:
1. Connects to Google Drive
2. Scans Desktop for all files
3. Groups files by base name (akshay12345 → akshay folder)
4. Creates folder structure: BaseName > Month (Jan/Feb) > Date
5. Uploads all files automatically
6. Skips duplicates

Usage:
    python3 auto_upload.py                    # Upload all desktop files
    python3 auto_upload.py --preview          # Preview groups without uploading
"""
import sys
from datetime import datetime
from pathlib import Path

from drive_service import DriveService
from folder_manager import FolderManager
from file_uploader import FileUploader
from desktop_scanner import DesktopScanner
from file_grouper import FileGrouper
from config import MONTH_FOLDER_FORMAT, DATE_FOLDER_FORMAT


def auto_upload(source_path: str = None, preview_only: bool = False):
    """
    Fully automatic upload with smart file grouping
    
    Files are grouped by their base name:
    - akshay12345466.pdf → akshay/Feb/2026-02-03/akshay12345466.pdf
    - akshay8765445.pdf → akshay/Feb/2026-02-03/akshay8765445.pdf
    
    Args:
        source_path: Path to scan for files (default: Desktop)
        preview_only: If True, only show what would be uploaded
    """
    print("\n" + "=" * 50)
    print("  🚀 Auto Upload - Smart Grouping Mode")
    print("=" * 50)
    print(f"\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Scan Desktop (or custom path)
    print("\n📂 Scanning for files...")
    try:
        if source_path:
            scanner = DesktopScanner(source_path)
        else:
            scanner = DesktopScanner()
        
        files = scanner.get_all_files()
    except Exception as e:
        print(f"❌ Failed to scan: {e}")
        return False
    
    if not files:
        print("⚠ No files found. Nothing to upload.")
        return True
    
    # Step 2: Group files by base name
    print(f"\n🔍 Grouping {len(files)} file(s) by name...")
    grouper = FileGrouper()
    file_paths = [str(f) for f in files]
    groups = grouper.group_files(file_paths)
    
    # Display groups
    grouper.display_groups(groups)
    print(f"\n📊 Summary: {grouper.get_group_summary(groups)}")
    
    # If preview only, stop here
    if preview_only:
        print("\n✓ Preview complete. No files uploaded.")
        return True
    
    # Step 3: Connect to Google Drive
    print("\n🔐 Connecting to Google Drive...")
    try:
        drive_service = DriveService()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False
    
    # Initialize managers
    folder_manager = FolderManager(drive_service)
    file_uploader = FileUploader(drive_service)
    
    # Step 4: Upload each group to its own folder
    print("\n📤 Uploading files to Google Drive...")
    print("-" * 50)
    
    total_uploaded = 0
    total_skipped = 0
    total_errors = 0
    
    for base_name, group_files in sorted(groups.items()):
        print(f"\n📁 {base_name}/ ({len(group_files)} files)")
        
        # Create folder structure for this group
        try:
            target_folder = folder_manager.setup_folder_structure(base_name)
        except Exception as e:
            print(f"   ❌ Failed to create folder: {e}")
            total_errors += len(group_files)
            continue
        
        # Upload files in this group
        try:
            results = file_uploader.upload_multiple_files(group_files, target_folder['id'])
            
            for r in results:
                if r['status'] == 'uploaded':
                    total_uploaded += 1
                elif r['status'] == 'skipped':
                    total_skipped += 1
                else:
                    total_errors += 1
        except Exception as e:
            print(f"   ❌ Upload failed: {e}")
            total_errors += len(group_files)
    
    # Final summary
    print("\n" + "=" * 50)
    print("  ✅ Auto Upload Complete!")
    print("=" * 50)
    print(f"\n📊 Final Summary:")
    print(f"   • Groups created: {len(groups)}")
    print(f"   • Files uploaded: {total_uploaded}")
    print(f"   • Files skipped (duplicates): {total_skipped}")
    print(f"   • Errors: {total_errors}")
    print(f"\n📁 Folder Structure in Drive:")
    print(f"   [base_name] / {datetime.now().strftime(MONTH_FOLDER_FORMAT)} / {datetime.now().strftime(DATE_FOLDER_FORMAT)}")
    print()
    
    return True


if __name__ == "__main__":
    # Check for --preview flag
    preview = '--preview' in sys.argv
    
    # Run auto upload
    success = auto_upload(preview_only=preview)
    sys.exit(0 if success else 1)
