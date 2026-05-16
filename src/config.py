"""
src/config.py - Configuration settings for Drive Organizer

WHAT IS THIS FILE?
==================
This file holds all the "settings" for our application in one place.
Think of it like a control panel — if you want to change how the app
behaves (like which folder to scan, or what happens with duplicate files),
you change it HERE instead of digging through all the other files.

WHY USE A SEPARATE CONFIG FILE?
================================
Imagine you have a TV remote. Instead of opening the TV and rewiring it
every time you want to change the volume, you just press a button on the
remote. This config file is like that remote — it lets you change settings
easily without touching the main code.

This is a common pattern in software called "separation of concerns":
- config.py = WHAT the settings are (this file)
- Other files = HOW the app works (they READ settings from here)

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS - Loading tools we need
# =============================================================================

# 'os' is a built-in Python module that lets us interact with the operating system.
# We use it here to read file paths and environment variables.
# Think of it as Python's way of talking to your computer's file system.
import os

# 'dotenv' is a third-party library that reads settings from a ".env" file.
# A .env file is a simple text file where you can store secret settings
# (like API keys) that you don't want to put directly in your code.
# Why? Because if you share your code on GitHub, you don't want everyone
# to see your private API keys!
# 'load_dotenv()' reads the .env file and makes those values available
# through os.getenv() — like loading a secret cheat sheet.
from dotenv import load_dotenv

# Actually LOAD the environment variables from the .env file.
# After this line runs, any values in your .env file become accessible
# using os.getenv('VARIABLE_NAME').
# If no .env file exists, this does nothing (no error).
load_dotenv()

# =============================================================================
# FILE PATHS - Where to find important files
# =============================================================================

# Get the directory where THIS config file lives.
# __file__ is a special Python variable that holds the path of the current file.
# os.path.abspath(__file__) gives us the FULL path (not a relative one).
# os.path.dirname() strips away the filename and gives us the folder.
# The FIRST os.path.dirname gives us the 'src/' folder.
# The SECOND os.path.dirname goes up ONE MORE LEVEL to the project root.
#
# Example:
#   __file__ = "/Users/ak/drive-organizer/src/config.py"
#   First dirname → "/Users/ak/drive-organizer/src"
#   Second dirname → "/Users/ak/drive-organizer"  ← This is _BASE_DIR
#
# WHY? So we can build paths to other files relative to the project root,
# and they'll work no matter where you run the script from.
# The underscore prefix (_BASE_DIR) means it's a "private" variable —
# only used inside this file, not meant to be imported by other files.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Path to the Google OAuth credentials file.
# This file is downloaded from Google Cloud Console and contains your
# app's identity (client ID and secret). Google uses this to know WHICH
# app is requesting access to the user's Drive.
#
# os.getenv('CREDENTIALS_FILE', default_value) works like this:
# - First, check if there's an environment variable called CREDENTIALS_FILE
# - If yes, use that value (useful for servers/deployment)
# - If no, use the default: credentials.json in the project root
#
# WHY os.getenv? It lets you override the path without changing code.
# For example, on a server you might set CREDENTIALS_FILE=/etc/app/creds.json
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', os.path.join(_BASE_DIR, 'credentials.json'))

# Path to store the OAuth token after successful authentication.
# After you log into Google the first time, the app saves a "token" —
# think of it like a movie ticket stub that proves you already paid.
# Next time, instead of buying a new ticket (logging in again),
# you just show the stub (the token).
# This file is auto-generated — you should NEVER create or edit it manually.
TOKEN_FILE = os.getenv('TOKEN_FILE', os.path.join(_BASE_DIR, 'token.json'))

# =============================================================================
# GOOGLE DRIVE API SETTINGS
# =============================================================================

# API Scopes define what PERMISSIONS the app has.
# Think of scopes like permission slips at school:
# - A permission slip for a field trip lets you go on the trip
# - A scope for 'drive' lets the app access your Google Drive
#
# 'https://www.googleapis.com/auth/drive' = FULL access to Drive
# (read, write, delete files — everything)
#
# We check if scopes are set in environment variables first.
# This lets advanced users customize permissions without changing code.
# If multiple scopes are needed, they can be comma-separated in the env var.
_scopes_env = os.getenv('SCOPES')  # Try to get scopes from environment

if _scopes_env:
    # If environment variable exists, split it by commas into a list.
    # strip() removes extra spaces around each scope.
    # The 'if s.strip()' part filters out empty strings (from trailing commas).
    # Example: "scope1, scope2, " → ["scope1", "scope2"]
    SCOPES = [s.strip() for s in _scopes_env.split(',') if s.strip()]
else:
    # Default: full Drive access. We use a list because the Google API
    # expects scopes to always be a list, even if there's only one.
    SCOPES = ['https://www.googleapis.com/auth/drive']


# =============================================================================
# GOOGLE DRIVE TARGETING
# =============================================================================

# The ID of the folder where all project folders should be located.
# If set, the script will only search for and create folders INSIDE this one.
# Provided by user: https://drive.google.com/drive/folders/1NcpbemBBPxLzBjtkUml9KbAk8uWiCfLA
BASE_FOLDER_ID = os.getenv('BASE_FOLDER_ID', '1NcpbemBBPxLzBjtkUml9KbAk8uWiCfLA')


# =============================================================================
# FOLDER NAMING SETTINGS
# =============================================================================

# Format for MONTH folder names.
# This uses Python's strftime format codes — special codes that get replaced
# with parts of a date. Think of them like fill-in-the-blank templates.
#
# Common format codes:
#   %b  = Abbreviated month name → "Jan", "Feb", "Mar"
#   %B  = Full month name       → "January", "February", "March"
#   %m  = Month as a number     → "01", "02", "03"
#   %Y  = Four-digit year       → "2026"
#
# We use %b here, so folders are named "Jan", "Feb", etc.
# WHY abbreviated? It's shorter and cleaner in the Drive folder tree.
# Change to %B if you prefer full names like "February".
MONTH_FOLDER_FORMAT = "%b"  # Results in: "Feb"

# Format for DATE folder names.
# Uses the same strftime format codes as above.
#
# Common formats:
#   "%Y-%m-%d" → "2026-02-03" (ISO format, sorts correctly by date!)
#   "%d-%m-%Y" → "03-02-2026" (day first, common in some countries)
#   "%B %d, %Y" → "February 03, 2026" (human-readable)
#
# WHY "%Y-%m-%d"? It's the ISO standard format, and the BIG advantage is
# that folders automatically sort in chronological order because the year
# comes first. "2026-01-15" comes before "2026-02-03" alphabetically,
# which is also chronologically correct!
DATE_FOLDER_FORMAT = "%Y-%m-%d"  # Results in: "2026-02-03"


# =============================================================================
# DUPLICATE FILE HANDLING
# =============================================================================

# What to do when uploading a file that already exists in Drive.
# This is like what happens when you try to save a file with the same name:
#
# Options:
#   'skip'      - Don't upload, keep the existing file.
#                 Like saying "never mind, it's already there."
#
#   'rename'    - Upload with a number suffix: file1.pdf, file2.pdf, file3.pdf
#                 Like Word adding "Copy" to duplicate file names.
#                 This way BOTH the old and new file exist.
#
#   'overwrite' - Delete the existing file and upload the new one.
#                 Like replacing an old homework with an updated version.
#                 WARNING: The old file is permanently deleted!
#
# We use 'rename' so that NO files are ever lost or skipped.
# Every file gets uploaded — duplicates just get a number added to their name.
DUPLICATE_HANDLING = 'rename'


# =============================================================================
# FILE SCANNING SETTINGS
# =============================================================================

# Default location to scan for files.
# None means "use the user's Desktop folder" (the app will figure out where
# the Desktop is automatically based on your operating system).
# You can change this to any folder path, like:
#   DEFAULT_SCAN_PATH = "/Users/akshay/Documents/ToUpload"
DEFAULT_SCAN_PATH = None

# File extensions to INCLUDE (empty list = include ALL files).
# If you set this to ['.pdf', '.docx'], ONLY PDFs and Word docs will be scanned.
# Everything else (images, videos, etc.) will be ignored.
# An empty list [] means "don't filter — include everything."
#
# WHY an empty list as default? Most users want to upload all their files,
# not just specific types. They can change this if needed.
INCLUDE_EXTENSIONS = []

# File extensions to EXCLUDE (these files are always ignored).
# .tmp = temporary files (created by apps while working)
# .log = log files (usually just debug info, not useful to upload)
# .DS_Store = macOS system files (invisible files that Macs create in every
#             folder to store icon positions and folder settings)
#
# WHY exclude these? They're system/temporary files that clutter up your Drive
# and aren't actual documents you'd want to keep.
EXCLUDE_EXTENSIONS = ['.tmp', '.log', '.DS_Store']

# Whether to include hidden files (files whose names start with a dot).
# On Mac/Linux, any file starting with '.' is considered "hidden."
# Examples: .gitignore, .env, .DS_Store
# Usually you DON'T want to upload these to Drive — they're config/system files.
INCLUDE_HIDDEN_FILES = False

# =============================================================================
# DISPLAY SETTINGS
# =============================================================================

# Maximum number of files to show in preview mode.
# If you have 500 files on your Desktop, printing all 500 would flood the
# terminal and make it hard to read. So we cap it at 20.
# You can increase this if you want to see more files listed.
MAX_PREVIEW_FILES = 20

# Enable verbose logging (shows extra details during execution).
# When True, the app prints every step it's doing (connecting, searching, etc.).
# When False, it only shows important messages (uploaded, errors).
#
# os.getenv('VERBOSE_MODE', 'True') checks if VERBOSE_MODE is set as an
# environment variable. If not, defaults to 'True'.
# .lower() converts to lowercase so "True", "TRUE", "true" all work.
# Then we check if it's in the tuple of "truthy" values.
#
# WHY use os.getenv? So you can turn off verbose mode from the command line:
#   VERBOSE_MODE=false python run_upload.py
# without changing any code.
VERBOSE_MODE = os.getenv('VERBOSE_MODE', 'True').lower() in ('1', 'true', 'yes', 'y')
