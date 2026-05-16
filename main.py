#!/usr/bin/env python3
"""
main.py - Interactive Menu-Based Entry Point (Legacy Version)

WHAT IS THIS FILE?
==================
This is the INTERACTIVE version of the Drive Organizer. When you run it,
you get a menu where you can choose what to do:
- Upload all files from your Desktop
- Upload from a specific folder
- Manually type in file paths
- View a summary of files on your Desktop

Think of it like a restaurant ordering system:
1. You see a menu of options
2. You pick what you want
3. The system does the work

NOTE: This is the OLDER (legacy) version. The NEWER version is run_upload.py,
which uses the improved modules in the src/ folder. This file uses the
root-level modules (drive_service.py, folder_manager.py, file_uploader.py,
desktop_scanner.py).

USAGE:
------
    python main.py
    (Then follow the on-screen prompts)

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS
# =============================================================================

# 'os' provides operating system functions — file existence checks, path handling.
import os

# 'sys' provides system-level functions.
# sys.exit(1) stops the program with an error code.
# Error code 0 = success, 1 = failure (a convention in programming).
import sys

# 'Path' from pathlib provides smarter file path handling.
from pathlib import Path

# Import our custom modules:
# DriveService = connects to Google Drive API (handles authentication + API calls)
from drive_service import DriveService

# FolderManager = creates/manages folder hierarchy in Drive (project/month/date)
from folder_manager import FolderManager

# FileUploader = uploads files with duplicate detection and handling
from file_uploader import FileUploader

# DesktopScanner = scans your Desktop (or any folder) for files
from desktop_scanner import DesktopScanner


def display_menu():
    """
    Display the main menu options in the terminal.
    
    This just prints text — it doesn't take any input or do any logic.
    The actual choice handling happens in main().
    
    '-> None' is implied (no return statement), meaning this function
    doesn't return anything — it only prints to the screen.
    """
    # Print a banner/header with emojis for visual appeal.
    # "=" * 50 creates a line of 50 equal signs for a visual border.
    print("\n" + "=" * 50)
    print("  📁 Google Drive File Organizer")
    print("=" * 50)
    
    # Print the available options, numbered 1-5.
    # The indentation (two spaces before each option) makes it look clean.
    print("\nWhat would you like to do?\n")
    print("  1. Upload files from Desktop (auto-scan)")
    print("  2. Upload files from a specific folder")
    print("  3. Upload specific files manually")
    print("  4. View Desktop files summary")
    print("  5. Exit")
    print()  # Empty line for spacing


def get_user_choice(prompt: str, valid_options: list) -> str:
    """
    Get validated input from the user.
    
    This function keeps asking until the user enters a valid option.
    It's like a bouncer at a door — you can't get in unless you have
    a valid answer.
    
    Args:
        prompt: The text to show when asking for input (e.g., "Enter choice: ")
        valid_options: List of acceptable answers (e.g., ['1', '2', '3', '4', '5'])
    
    Returns:
        The user's valid choice as a string
    
    Example:
        >>> choice = get_user_choice("Pick 1-3: ", ['1', '2', '3'])
        Pick 1-3: 4
          Invalid choice. Please enter one of: 1, 2, 3
        Pick 1-3: 2
        >>> print(choice)  # "2"
    """
    # 'while True' creates an infinite loop — it keeps running until we
    # explicitly 'return' (which exits the function and the loop).
    while True:
        # input() pauses the program and waits for the user to type something.
        # .strip() removes any extra whitespace (spaces/tabs) the user typed.
        choice = input(prompt).strip()
        
        # Check if the user's input is in our list of valid options.
        if choice in valid_options:
            return choice  # Valid! Return it and exit the loop.
        
        # If we get here, the input was invalid. Show an error and loop again.
        # ', '.join(valid_options) turns ['1', '2', '3'] into "1, 2, 3"
        print(f"  Invalid choice. Please enter one of: {', '.join(valid_options)}")


def select_files_from_list(files: list) -> list:
    """
    Let the user select specific files from a numbered list.
    
    After showing files, the user can pick which ones to upload by
    entering their numbers (like "1, 3, 5") or "all" for everything.
    
    This gives users control — they don't HAVE to upload every file.
    
    Args:
        files: List of file Path objects to choose from
    
    Returns:
        List of selected file paths as strings.
        Empty list if no valid files were selected.
    
    Example:
        >>> selected = select_files_from_list([Path("a.pdf"), Path("b.pdf")])
        Enter file numbers to upload (comma-separated, or 'all' for all):
        → 1, 2
        >>> print(selected)  # ["/path/to/a.pdf", "/path/to/b.pdf"]
    """
    # If no files to choose from, return empty list immediately.
    if not files:
        return []
    
    # Show instructions for the user.
    print("\nEnter file numbers to upload (comma-separated, or 'all' for all):")
    print("Example: 1, 3, 5 or all")
    
    # Get the user's selection.
    # .strip() removes extra whitespace, .lower() makes it case-insensitive.
    selection = input("→ ").strip().lower()
    
    # If user typed "all", return ALL files (converted to string paths).
    # str(f) converts a Path object to a regular string.
    if selection == 'all':
        return [str(f) for f in files]
    
    # Otherwise, parse the comma-separated numbers.
    selected = []
    try:
        # Split "1, 3, 5" into ["1", " 3", " 5"], then convert each to int.
        # int(x.strip()) removes spaces and converts to a number.
        indices = [int(x.strip()) for x in selection.split(',')]
        
        for i in indices:
            # Check if the number is in valid range (1 to number-of-files).
            # Remember, the list is displayed 1-indexed to the user, but
            # Python lists are 0-indexed, so files[i-1] gets the right file.
            if 1 <= i <= len(files):
                selected.append(str(files[i - 1]))
            else:
                print(f"  Skipping invalid number: {i}")
    except ValueError:
        # If the user typed something that's not a number (like "abc"),
        # int() throws a ValueError. We catch it and ask again.
        # This uses RECURSION — the function calls itself to retry.
        print("  Invalid input. Please enter numbers separated by commas.")
        return select_files_from_list(files)
    
    return selected


def upload_from_desktop(drive_service, folder_manager, file_uploader):
    """
    Scan the Desktop and upload selected files.
    
    This function:
    1. Scans the Desktop for all files
    2. Shows a category menu (all, documents, images, recent, search)
    3. Lets the user select specific files
    4. Uploads each selected file to the appropriate Drive folder
    
    Args:
        drive_service: Authenticated DriveService instance
        folder_manager: FolderManager for creating folder structures
        file_uploader: FileUploader for handling uploads
    """
    # Create a scanner for the Desktop.
    # DesktopScanner auto-detects the Desktop folder location.
    scanner = DesktopScanner()
    
    # Show a summary of what's on the Desktop (file count, types, etc.)
    scanner.display_summary()
    
    # Ask the user WHAT type of files to upload.
    print("\nWhat would you like to upload?\n")
    print("  1. All files")
    print("  2. Documents only (PDF, DOC, etc.)")
    print("  3. Images only")
    print("  4. Recent files (last 24 hours)")
    print("  5. Search by name")
    print("  6. Cancel")
    
    choice = get_user_choice("→ ", ['1', '2', '3', '4', '5', '6'])
    
    # If user chose Cancel, exit this function early.
    if choice == '6':
        return
    
    # Get the appropriate files based on the user's choice.
    # Each option calls a different method on the scanner.
    if choice == '1':
        files = scanner.get_all_files()
    elif choice == '2':
        files = scanner.get_files_by_category('documents')
    elif choice == '3':
        files = scanner.get_files_by_category('images')
    elif choice == '4':
        files = scanner.get_recent_files(hours=24)
    elif choice == '5':
        pattern = input("Enter search pattern: ").strip()
        files = scanner.get_files_by_name_pattern(pattern)
    
    # If no files matched the criteria, tell the user and exit.
    if not files:
        print("\n⚠ No files found matching your criteria.")
        return
    
    # Show the files that were found.
    print(f"\n📄 Found {len(files)} file(s):")
    scanner.display_files(files)
    
    # Let the user select which files to actually upload.
    selected_files = select_files_from_list(files)
    
    if not selected_files:
        print("\n⚠ No files selected.")
        return
    
    # Counters for the final summary.
    total_scanned = len(selected_files)
    total_uploaded = 0
    not_uploaded = []
    
    # Upload each selected file.
    for path in selected_files:
        try:
            filename = os.path.basename(path)
            project_name = folder_manager.sanitize_project_name(filename)
            target_folder = folder_manager.setup_folder_structure(project_name)
            
            # If no matching folder was found, skip this file.
            if not target_folder:
                not_uploaded.append({'name': filename, 'reason': f'No matching folder in Drive'})
                continue
            
            # Actually upload the file.
            result = file_uploader.upload_file(path, target_folder['id'])
            
            if result['status'] == 'uploaded':
                total_uploaded += 1
            elif result['status'] == 'skipped':
                not_uploaded.append({'name': filename, 'reason': 'Duplicate'})
        except Exception as e:
            not_uploaded.append({'name': os.path.basename(path), 'reason': str(e)})

    # Show the summary report.
    display_final_summary(
        total_scanned, 
        total_uploaded, 
        folder_manager.folders_created_count, 
        not_uploaded,
        folder_manager.created_project_names
    )
    run_counter_program()


def upload_from_folder(drive_service, folder_manager, file_uploader):
    """
    Upload files from a user-specified folder (not Desktop).
    
    Same logic as upload_from_desktop, but the user provides a custom
    folder path instead of using the Desktop.
    
    Args:
        drive_service: Authenticated DriveService instance
        folder_manager: FolderManager instance
        file_uploader: FileUploader instance
    """
    # Ask the user for a folder path.
    print("\n📂 Enter the folder path to scan:")
    folder_path = input("→ ").strip()
    
    # Validate the path — make sure it's a real directory.
    # os.path.isdir() returns False for files and non-existent paths.
    if not os.path.isdir(folder_path):
        print(f"❌ Folder not found: {folder_path}")
        return
    
    # Scan the specified folder.
    # DesktopScanner can scan ANY folder, not just the Desktop
    # (despite its name — it's a general-purpose scanner).
    scanner = DesktopScanner(folder_path)
    files = scanner.get_all_files()
    
    if not files:
        print("\n⚠ No files found in folder.")
        return
    
    # Display and let user select files (same flow as Desktop upload).
    print(f"\n📄 Found {len(files)} file(s):")
    scanner.display_files(files)
    
    selected_files = select_files_from_list(files)
    
    if not selected_files:
        return
    
    # Counters for the final summary.
    total_scanned = len(selected_files)
    total_uploaded = 0
    not_uploaded = []

    # Upload each selected file with auto-detected folder names.
    for path in selected_files:
        try:
            filename = os.path.basename(path)
            project_name = folder_manager.sanitize_project_name(filename)
            target_folder = folder_manager.setup_folder_structure(project_name)
            
            # If no matching folder was found, skip this file.
            if not target_folder:
                not_uploaded.append({'name': filename, 'reason': f'No matching folder in Drive'})
                continue
            
            result = file_uploader.upload_file(path, target_folder['id'])
            
            if result['status'] == 'uploaded':
                total_uploaded += 1
            elif result['status'] == 'skipped':
                not_uploaded.append({'name': filename, 'reason': 'Duplicate'})
        except Exception as e:
            not_uploaded.append({'name': os.path.basename(path), 'reason': str(e)})

    # Show the summary report.
    display_final_summary(
        total_scanned, 
        total_uploaded, 
        folder_manager.folders_created_count, 
        not_uploaded,
        folder_manager.created_project_names
    )
    run_counter_program()


def upload_manual(drive_service, folder_manager, file_uploader):
    """
    Manual file upload — user types in file paths one at a time.
    
    This is for when you know exactly which files you want to upload
    and don't want to scan a whole folder.
    
    Instructions:
    1. Type a file path and press Enter
    2. Repeat for as many files as you want
    3. Type 'done' when finished
    
    Args:
        drive_service: Authenticated DriveService instance
        folder_manager: FolderManager instance
        file_uploader: FileUploader instance
    """
    # Show instructions to the user.
    print("\n📄 Enter file paths to upload (one per line)")
    print("   Type 'done' when finished:\n")
    
    file_paths = []  # Collect valid file paths
    
    # Keep asking for paths until the user types 'done'.
    while True:
        user_input = input("→ ").strip()
        
        # Check if the user is done entering files.
        if user_input.lower() == 'done':
            break  # Exit the input loop
        
        # Skip empty input (user just pressed Enter).
        if not user_input:
            continue
        
        # Validate that the file exists.
        if os.path.exists(user_input):
            file_paths.append(user_input)
            # Show confirmation so the user knows it was accepted.
            print(f"  Added: {os.path.basename(user_input)}")
        else:
            print(f"  File not found: {user_input}")
    
    # If no valid files were entered, exit.
    if not file_paths:
        return
    
    # Counters for the final summary.
    total_scanned = len(file_paths)
    total_uploaded = 0
    not_uploaded = []

    # Upload each file.
    for path in file_paths:
        try:
            filename = os.path.basename(path)
            project_name = folder_manager.sanitize_project_name(filename)
            target_folder = folder_manager.setup_folder_structure(project_name)
            
            # If no matching folder was found, skip this file.
            if not target_folder:
                not_uploaded.append({'name': filename, 'reason': f'No matching folder in Drive'})
                continue
            
            result = file_uploader.upload_file(path, target_folder['id'])
            
            if result['status'] == 'uploaded':
                total_uploaded += 1
            elif result['status'] == 'skipped':
                not_uploaded.append({'name': filename, 'reason': 'Duplicate'})
        except Exception as e:
            not_uploaded.append({'name': os.path.basename(path), 'reason': str(e)})

    # Show the summary report.
    display_final_summary(
        total_scanned, 
        total_uploaded, 
        folder_manager.folders_created_count, 
        not_uploaded,
        folder_manager.created_project_names
    )
    run_counter_program()


def view_desktop_summary():
    """
    Display a summary of files on the Desktop without uploading anything.
    
    This is a "read-only" option — it just shows information about
    what's on your Desktop. Useful for reviewing before deciding to upload.
    
    The user can then choose to drill down into a specific category
    (documents, images, etc.) for more detail.
    """
    # Scan the Desktop.
    scanner = DesktopScanner()
    
    # Show the overall summary (total files, size, types).
    scanner.display_summary()
    
    # Categorize files by type (documents, images, etc.)
    # Returns a dict like: {'documents': [...], 'images': [...], ...}
    categorized = scanner.categorize_files()
    
    # Offer to show details for a specific category.
    print("\nView details for a category? (enter category name or 'skip')")
    category = input("→ ").strip().lower()
    
    # If the user entered a valid category name, show its files.
    # 'skip' means they don't want to see details.
    if category != 'skip' and category in categorized:
        print(f"\n📁 {category.capitalize()} files:")
        scanner.display_files(categorized[category])
        
    # Also trigger the counter program for reference
    run_counter_program()


def display_final_summary(total_scanned, total_uploaded, folders_created, not_uploaded, created_names=None):
    """
    Display a clear, beautiful summary of the upload results.
    """
    print("\n" + "=" * 50)
    print("  ✅ UPLOAD COMPLETE")
    print("=" * 50)
    print(f"\n📊 Final Results:")
    print(f"   • Total files scanned:  {total_scanned}")
    print(f"   • Files uploaded:       {total_uploaded}")
    print(f"   • Name folders created: {folders_created}")
    
    # If we created new folders, list them!
    if created_names:
        print("     → Created: " + ", ".join(created_names))
    
    if not_uploaded:
        print(f"\n⚠ Files NOT uploaded ({len(not_uploaded)}):")
        for item in not_uploaded:
            print(f"   - {item['name']} ({item['reason']})")
    else:
        print("\n✓ All selected files were successfully uploaded!")
    print("\n" + "=" * 50)


def run_counter_program():
    """
    Execute the desktop_file_counter.py script.
    """
    import subprocess
    import os
    
    print("\n📦 Running Desktop File Counter...")
    print("-" * 50)
    
    # Path to the counter script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    counter_script = os.path.join(script_dir, "desktop_file_counter.py")
    
    if os.path.exists(counter_script):
        try:
            # sys.executable ensures we use the same Python version
            subprocess.run([sys.executable, counter_script], check=True)
        except Exception as e:
            print(f"⚠ Could not run counter program: {e}")
    else:
        print("⚠ desktop_file_counter.py not found.")
    print("-" * 50)


def main():
    """
    Main entry point — runs the interactive menu loop.
    
    This function:
    1. Connects to Google Drive (authenticates)
    2. Creates helper objects (folder manager, file uploader)
    3. Shows a menu and handles the user's choices in a loop
    4. Keeps running until the user chooses "Exit"
    
    The 'while True' loop means the menu shows again after each action,
    so the user can perform multiple operations in one session.
    """
    # =========================================================================
    # STEP 1: Connect to Google Drive
    # =========================================================================
    # try/except handles errors gracefully — if something goes wrong during
    # authentication, we show a helpful message instead of a scary traceback.
    try:
        print("\n🔐 Connecting to Google Drive...")
        # DriveService() creates a new connection and handles OAuth login.
        drive_service = DriveService()
    except FileNotFoundError as e:
        # This happens if credentials.json is missing.
        print(f"\n❌ Error: {e}")
        print("\n📋 Please download credentials.json from Google Cloud Console")
        sys.exit(1)  # Exit with error code 1 (failure)
    except Exception as e:
        # Catch any other authentication errors.
        print(f"\n❌ Authentication failed: {e}")
        sys.exit(1)
    
    # =========================================================================
    # STEP 2: Initialize helper objects
    # =========================================================================
    # FolderManager handles creating project/month/date folders in Drive.
    folder_manager = FolderManager(drive_service)
    
    # FileUploader handles uploading files with duplicate checking.
    file_uploader = FileUploader(drive_service)
    
    # =========================================================================
    # STEP 3: Main menu loop
    # =========================================================================
    # This loop runs forever until the user chooses option 5 (Exit),
    # which triggers 'break' to exit the loop.
    while True:
        # Show the menu options.
        display_menu()
        
        # Get the user's choice (validated — must be 1-5).
        choice = get_user_choice("Enter choice (1-5): ", ['1', '2', '3', '4', '5'])
        
        # Execute the chosen action.
        # Each option calls a different function that handles that workflow.
        if choice == '1':
            upload_from_desktop(drive_service, folder_manager, file_uploader)
        elif choice == '2':
            upload_from_folder(drive_service, folder_manager, file_uploader)
        elif choice == '3':
            upload_manual(drive_service, folder_manager, file_uploader)
        elif choice == '4':
            view_desktop_summary()
        elif choice == '5':
            print("\n👋 Goodbye!\n")
            break  # Exit the while loop (and the program)
        
        # After each action completes, pause so the user can read the output.
        # input() waits for the user to press Enter before showing the menu again.
        input("\nPress Enter to continue...")


# =============================================================================
# ENTRY POINT
# =============================================================================
# This block runs ONLY when you execute this file directly:
#   python main.py
# It does NOT run when this file is imported by another file.
# __name__ is "__main__" when run directly, and "main" when imported.
if __name__ == "__main__":
    main()
