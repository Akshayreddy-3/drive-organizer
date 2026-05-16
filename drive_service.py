"""
drive_service.py - Google Drive API Service (Legacy Version)

WHAT IS THIS FILE?
==================
This is the LEGACY version of the Google Drive API client.
The NEWER version is src/drive_client.py, which has more features.

This file handles:
1. OAuth 2.0 authentication (logging in to Google)
2. Searching for folders in Drive
3. Creating new folders
4. Listing files in folders
5. Uploading files
6. Deleting files

NOTE: This module is used by main.py and the root-level helper files.
The newer run_upload.py uses src/drive_client.py instead.

SECURITY REMINDER:
------------------
credentials.json and token.json contain sensitive data.
NEVER commit these to Git or share them publicly!

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS
# =============================================================================

# 'os' for file system operations (checking if files exist, getting paths).
import os
from typing import Optional, Dict, List

# Google API libraries for OAuth authentication and Drive API calls.
# See src/drive_client.py for detailed explanations of each import.

# Request = makes HTTP calls to Google (for refreshing tokens)
from google.auth.transport.requests import Request

# Credentials = represents our login credentials (access + refresh tokens)
from google.oauth2.credentials import Credentials

# InstalledAppFlow = handles the OAuth login process (opens browser)
from google_auth_oauthlib.flow import InstalledAppFlow

# build = creates a service object for talking to Google Drive
from googleapiclient.discovery import build

# MediaFileUpload = handles reading and sending files to Google
from googleapiclient.http import MediaFileUpload

# Import configuration from the ROOT-level config.py (NOT src/config.py).
# This is the key difference from src/drive_client.py.
from config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES, BASE_FOLDER_ID


class DriveService:
    """
    Wrapper for Google Drive API operations (legacy version).
    
    This class provides simple methods for common Drive operations.
    Think of it as a "remote control" for Google Drive — press a button
    (call a method) and something happens in Drive.
    
    This is the LEGACY version. The newer DriveClient in src/drive_client.py
    has more features and better error messages. Both work the same way
    at a basic level.
    
    Attributes:
        service: The Google Drive API service object (our connection)
    """
    
    def __init__(self):
        """
        Initialize the DriveService and authenticate with Google.
        
        This constructor:
        1. Sets up the service attribute (starts as None)
        2. Calls authenticate() to log into Google Drive
        
        After this runs, self.service is ready to make API calls.
        """
        # Will hold the Google Drive API service object.
        # Starts as None, gets set during authenticate().
        self.service = None
        
        # Run the authentication process.
        # This either loads a saved token or opens a browser for login.
        self.authenticate()
    
    def authenticate(self):
        """
        Authenticate with Google Drive API using OAuth 2.0.
        
        AUTHENTICATION FLOW:
        1. Check for saved token (from previous login)
        2. If token exists and is valid → use it (fastest path)
        3. If token is expired → refresh it (no browser needed)
        4. If no token → open browser for full login
        5. Save token for future use
        
        See src/drive_client.py._authenticate() for detailed explanations
        of the OAuth 2.0 process with analogies and examples.
        """
        creds = None
        
        # Try to load existing token from previous authentication.
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
        # If no valid credentials, we need to authenticate.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Token expired but we have a refresh token → auto-renew.
                creds.refresh(Request())
            else:
                # No valid token at all → full login required.
                if not os.path.exists(CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"Credentials file not found: {CREDENTIALS_FILE}\n"
                        "Please download OAuth credentials from Google Cloud Console "
                        "and save as 'credentials.json' in the project folder."
                    )
                
                # Check if client credentials are in environment variables.
                # This is more secure than storing them in a file.
                client_id = os.getenv('GOOGLE_CLIENT_ID')
                client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
                
                if client_id and client_secret:
                    # Build config from environment variables.
                    client_config = {
                        "installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": os.getenv('GOOGLE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
                            "token_uri": os.getenv('GOOGLE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
                            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                        }
                    }
                    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                else:
                    # Use the credentials.json file.
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                
                # Open browser for the user to log in.
                # port=0 = use any available port on the computer.
                creds = flow.run_local_server(port=0)
            
            # Save the token for future use (so user doesn't need to log in again).
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        # Build the Drive API service object.
        # 'drive' = Google Drive, 'v3' = version 3 of the API.
        self.service = build('drive', 'v3', credentials=creds)
        print("✓ Successfully connected to Google Drive")
    
    def search_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[dict]:
        """
        Search for a folder by name in Google Drive.
        
        Works like a search bar — looks for a folder with the exact name.
        NEW: Now handles case-insensitivity by falling back to a manual
        search of the parent's contents if an exact match isn't found.
        
        Args:
            folder_name: Name of the folder to find (exact match)
            parent_id: Optional - search only within this parent folder.
        
        Returns:
            Folder info dict (id, name, parents) if found.
            None if no folder with that name exists.
        """
        # 1. Try exact search (fastest)
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, parents)'
        ).execute()
        
        files = results.get('files', [])
        if files:
            return files[0]
            
        # 2. Case-insensitive fallback (prevent duplicates like "Feb" and "feb")
        # List all folders in the target area (root or specific parent)
        list_query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            list_query += f" and '{parent_id}' in parents"
        else:
            list_query += f" and '{BASE_FOLDER_ID}' in parents"
            
        all_folders = self.service.files().list(
            q=list_query,
            spaces='drive',
            fields='files(id, name, parents)'
        ).execute().get('files', [])
        
        target_clean = folder_name.strip().lower()
        for folder in all_folders:
            if folder['name'].strip().lower() == target_clean:
                return folder
                
        return None
    
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> dict:
        """
        Create a new folder in Google Drive.
        
        Args:
            folder_name: Name for the new folder
            parent_id: Optional - create inside this parent folder.
                       If None, creates at the Drive root level.
        
        Returns:
            New folder info dict (id, name)
        """
        # In Google Drive, folders are special "files" with a specific mimeType.
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        # If a parent folder is specified, nest the new folder inside it.
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        # Send the create request to Google's servers.
        folder = self.service.files().create(
            body=file_metadata,
            fields='id, name'
        ).execute()
        
        print(f"✓ Created folder: {folder_name}")
        return folder
    
    def list_files_in_folder(self, folder_id: str) -> list:
        """
        List all files and subfolders inside a specific folder.
        
        Args:
            folder_id: ID of the folder to look inside
        
        Returns:
            List of file info dicts (id, name, mimeType)
        """
        # Query for items whose parent is this folder.
        query = f"'{folder_id}' in parents and trashed=false"
        
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType)'
        ).execute()
        
        return results.get('files', [])
    
    def upload_file(self, file_path: str, folder_id: str, file_name: str = None) -> dict:
        """
        Upload a file from your computer to Google Drive.
        
        Args:
            file_path: Full path to the local file
            folder_id: ID of the target Drive folder
            file_name: Optional custom name. If None, uses original filename.
        
        Returns:
            Uploaded file info dict (id, name)
        
        Raises:
            FileNotFoundError: If the local file doesn't exist
        """
        # Safety check — make sure the file actually exists.
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Use custom name or fall back to original filename.
        if file_name is None:
            file_name = os.path.basename(file_path)
        
        # Prepare metadata (name and destination folder).
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        # Create the upload handler.
        # resumable=True enables chunk-based uploading (can resume if interrupted).
        media = MediaFileUpload(file_path, resumable=True)
        
        # Execute the upload.
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name'
        ).execute()
        
        print(f"✓ Uploaded file: {file_name}")
        return file
    
    def delete_file(self, file_id: str):
        """
        Permanently delete a file from Google Drive.
        
        ⚠️ WARNING: This is a PERMANENT delete (not moved to trash).
        Used when DUPLICATE_HANDLING is 'overwrite' — the old file is
        deleted before uploading the replacement.
        
        Args:
            file_id: The unique ID of the file to delete
        """
        self.service.files().delete(fileId=file_id).execute()
