"""
config.py - Configuration Settings (Root-Level / Legacy)

WHAT IS THIS FILE?
==================
This is the root-level configuration file for the LEGACY version of the
Drive Organizer (used by main.py, file_uploader.py, etc.).

The NEWER version of the app uses src/config.py instead.
If you're running run_upload.py, that uses src/config.py.
If you're running main.py directly, it uses THIS config.

Both files have similar settings — think of this as the "original remote
control" and src/config.py as the "upgraded remote control."

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS
# =============================================================================

# 'os' lets us interact with the operating system — file paths, env vars, etc.
import os

# 'dotenv' reads secret settings from a .env file.
# Think of .env as a secret cheat sheet that keeps your API keys private.
# load_dotenv() reads that file and makes values available via os.getenv().
from dotenv import load_dotenv

# Load environment variables from .env file.
# If no .env file exists, this does nothing (no error).
load_dotenv()

# =============================================================================
# FILE PATHS
# =============================================================================

# Path to Google OAuth credentials file.
# This file is your app's "ID card" — downloaded from Google Cloud Console.
# os.getenv() checks if there's an environment variable override first.
# If not, defaults to credentials.json in the same folder as this script.
# os.path.dirname(__file__) = the folder containing this config.py file.
# os.path.join() combines folder + filename into a full path.
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', os.path.join(os.path.dirname(__file__), 'credentials.json'))

# Path to store the OAuth token after the user logs in.
# This is like a movie ticket stub — proves you already authenticated.
# Saved so you don't have to log in every time.
TOKEN_FILE = os.getenv('TOKEN_FILE', os.path.join(os.path.dirname(__file__), 'token.json'))

# =============================================================================
# GOOGLE DRIVE API SETTINGS
# =============================================================================

# API Scopes = permission levels for what the app can do.
# 'https://www.googleapis.com/auth/drive' = FULL Drive access.
# Can be overridden via SCOPES environment variable (comma-separated).
_scopes_env = os.getenv('SCOPES')
if _scopes_env:
	# Split comma-separated scopes into a list, removing whitespace.
	SCOPES = [s.strip() for s in _scopes_env.split(',') if s.strip()]
else:
	# Default: full Drive access (read + write + delete).
	SCOPES = ['https://www.googleapis.com/auth/drive']

# =============================================================================
# GOOGLE DRIVE TARGETING
# =============================================================================

# The ID of the folder where all project folders should be located.
# Provided by user: https://drive.google.com/drive/folders/1NcpbemBBPxLzBjtkUml9KbAk8uWiCfLA
BASE_FOLDER_ID = os.getenv('BASE_FOLDER_ID', '1NcpbemBBPxLzBjtkUml9KbAk8uWiCfLA')

# =============================================================================
# FOLDER NAMING SETTINGS
# =============================================================================

# Format for month folder names using Python's strftime codes:
# %b = abbreviated month ("Jan", "Feb") | %B = full month ("January", "February")
MONTH_FOLDER_FORMAT = "%b"  # Results in: "Feb"

# Format for date folder names:
# "%Y-%m-%d" gives ISO format like "2026-02-03" (sorts chronologically!)
DATE_FOLDER_FORMAT = "%Y-%m-%d"  # Results in: "2026-02-03"

# =============================================================================
# DUPLICATE FILE HANDLING
# =============================================================================

# What to do when a file with the same name already exists in Drive:
#   'skip'      → Don't upload (keep existing file)
#   'rename'    → Upload with number suffix: file1.pdf, file2.pdf
#   'overwrite' → Delete old file, upload new one (CAUTION: permanent!)
#
# Set to 'rename' so every file gets uploaded — duplicates get a number.
DUPLICATE_HANDLING = 'rename'
