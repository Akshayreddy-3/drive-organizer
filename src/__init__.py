"""
src/__init__.py - Package initializer for Drive Organizer source modules

This file makes the src/ directory a Python package, allowing imports like:
    from src.drive_client import DriveClient
    from src.file_scanner import FileScanner

Author: Akshay Reddy
Date: 2026-02-03
"""

# Version of the package
__version__ = "2.0.0"

# List of modules that should be imported when using 'from src import *'
__all__ = [
    "drive_client",
    "folder_navigator", 
    "file_scanner",
    "file_grouper",
    "uploader",
    "config"
]
