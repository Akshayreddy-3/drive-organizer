#!/usr/bin/env python3
"""
compare_scan.py - Compare Desktop files vs. Drive folders

Matches files on your Desktop to existing project folders in Google Drive.
Logic: Ignores 'INC', spaces, numbers, and special characters.
"""

import os
import sys
import re
from typing import Dict, List

# Add current directory to path so we can import src.drive_client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from src.drive_client import DriveClient
    from src.config import BASE_FOLDER_ID
except ImportError:
    print("❌ Error: Could not find project source. Please run this from the project root.")
    sys.exit(1)

def clean_name(name: str) -> str:
    """Removes 'INC', spaces, numbers, symbols, and ' - From ...' suffix for fuzzy matching."""
    # Remove extension
    name = os.path.splitext(name)[0]
    # Remove ' - From [sender]' suffix added by ai_pdf_renamer (case-insensitive)
    name = re.sub(r'\s*-\s*From\s+.*', '', name, flags=re.IGNORECASE).strip()
    # Remove 'inc' (case-insensitive)
    name = re.sub(r'inc', '', name, flags=re.IGNORECASE).strip()
    # Remove everything except letters
    return re.sub(r'[^a-zA-Z]', '', name).lower()

def main():
    try:
        # 1. Connect to Drive
        print("→ Connecting to Google Drive...")
        client = DriveClient()
        
        # 2. Fetch Drive Folders
        print(f"→ Scanning Drive folders in 'Houston Mails' ({BASE_FOLDER_ID})...")
        q = f"'{BASE_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = client.service.files().list(q=q, fields='files(id, name)').execute()
        drive_folders = results.get('files', [])
        
        folder_map = {} # cleaned -> original
        for f in drive_folders:
            c = clean_name(f['name'])
            if c:
                folder_map[c] = f['name']
        
        # 3. Scan Desktop
        desktop_path = os.path.expanduser("~/Desktop")
        print(f"→ Scanning local Desktop: {desktop_path}...")
        desktop_files = [
            f for f in os.listdir(desktop_path) 
            if not f.startswith('.') and f != 'DS_Store' and os.path.isfile(os.path.join(desktop_path, f))
        ]
        
        # 4. Compare
        matches = {} # folder_name -> list of desktop_files
        missing = [] # list of desktop_files
        
        for f in desktop_files:
            c = clean_name(f)
            if c in folder_map:
                folder_name = folder_map[c]
                if folder_name not in matches:
                    matches[folder_name] = []
                matches[folder_name].append(f)
            else:
                missing.append(f)
        
        # 5. Display Results
        print("\n" + "="*70)
        print(" SCAN RESULT: DESKTOP vs. DRIVE FOLDERS")
        print(" (Ignoring 'INC', spaces, numbers, and characters)")
        print("="*70)
        print(f" Total Desktop Files: {len(desktop_files)}")
        print(f" Matched to Folders:  {len(desktop_files) - len(missing)}")
        print(f" Unique New Projects: {len(missing)}")
        print("-" * 70)
        
        if matches:
            print("\n✅ MATCHED TO EXISTING FOLDERS:")
            for folder in sorted(matches.keys()):
                print(f"  📁 {folder}")
                for file in sorted(matches[folder]):
                    print(f"    - {file}")
                    
        if missing:
            print("\n❌ NO MATCHING FOLDERS (NEW PROJECTS):")
            for file in sorted(missing):
                print(f"{file}")
        
        print("\n" + "="*70)
        print(" DONE. Use 'python3 run_upload.py' to sync these files to Drive.")
        print("="*70)

    except KeyboardInterrupt:
        print("\n\n👋 Scan cancelled.")
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
