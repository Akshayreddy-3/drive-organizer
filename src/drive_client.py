"""
src/drive_client.py - Google Drive API Client

WHAT IS THIS FILE?
==================
This is the "translator" between our Python app and Google Drive.
Google Drive has an API (Application Programming Interface) — think of it
like a menu at a restaurant. The API tells us what we can order (request),
and this file places those orders for us.

Without this file, our app wouldn't be able to talk to Google Drive at all.

WHY A SEPARATE CLASS?
=====================
We wrap all Drive operations in one class (DriveClient) so that the rest
of our code doesn't need to know HOW Google Drive works internally.
Other files just call simple methods like:
    client.upload_file("resume.pdf", folder_id)
They don't need to worry about authentication, API queries, or HTTP requests.
This is called "abstraction" — hiding complex details behind simple interfaces.

SECURITY NOTE:
--------------
This module requires credentials.json from Google Cloud Console.
The token.json file contains sensitive authentication data.
NEVER commit these files to version control (like GitHub)!

Author: Akshay Reddy
Date: 2026-02-03
"""

# =============================================================================
# IMPORTS — Loading the tools we need
# =============================================================================

# 'os' lets us interact with the operating system (check if files exist, 
# get file paths, read environment variables, etc.)
import os

# 'typing' provides type hints — labels that tell other developers what kind
# of data a function expects and returns. They don't change how the code runs,
# but they make the code easier to understand.
# Optional[Dict] means "either a Dict, or None"
# List[Dict] means "a list where every item is a Dict"
from typing import Optional, Dict, List

# --- Google API Libraries ---
# These are all third-party libraries installed via pip.
# They handle the complex work of talking to Google's servers.

# 'Request' is used to make HTTP requests to Google's servers.
# When our token expires, we use Request() to ask Google for a new one.
# Think of it as making a phone call to Google to renew our access pass.
from google.auth.transport.requests import Request

# 'Credentials' represents our login credentials (access token + refresh token).
# It's like an ID card that proves we're allowed to access the user's Drive.
# We can save these credentials to a file and load them later so the user
# doesn't have to log in every time.
from google.oauth2.credentials import Credentials

# 'InstalledAppFlow' handles the OAuth 2.0 login process.
# OAuth 2.0 is a secure way to let apps access your account WITHOUT giving
# them your password. Instead, you log in through Google's own website,
# and Google gives the app a special token.
# It's like a hotel key card — the hotel (Google) gives you the card (token),
# and you use it to access your room (Drive), but the hotel can revoke it anytime.
from google_auth_oauthlib.flow import InstalledAppFlow

# 'build' creates a service object for interacting with Google APIs.
# It's like getting a walkie-talkie that's already tuned to the right channel
# for talking to Google Drive.
from googleapiclient.discovery import build

# 'MediaFileUpload' handles the actual file transfer when uploading.
# It reads a file from your computer and sends it to Google's servers in chunks.
# "Resumable" means if the upload fails halfway, it can continue from where
# it stopped instead of starting over (useful for large files).
from googleapiclient.http import MediaFileUpload

# VERBOSE_MODE = whether to show detailed status messages
# BASE_FOLDER_ID = the specific parent folder to act as root
from src.config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES, VERBOSE_MODE, BASE_FOLDER_ID


class DriveClient:
    """
    A client class for interacting with Google Drive API.
    
    Think of this class as a "remote control" for Google Drive.
    Just like a TV remote has buttons (power, volume, channel),
    this class has methods (find_folder, create_folder, upload_file).
    
    This class handles:
    1. OAuth 2.0 authentication with Google (logging in)
    2. Searching for files and folders
    3. Creating new folders
    4. Uploading files
    5. Listing folder contents
    
    Attributes:
        service: The Google Drive API service object (our "connection" to Drive)
    
    Example:
        >>> client = DriveClient()           # Connect to Drive
        >>> folders = client.list_root_folders()  # List all folders
        >>> print(f"Found {len(folders)} folders in Drive root")
    """
    
    def __init__(self):
        """
        Initialize the DriveClient and authenticate with Google.
        
        This is called automatically when you create a new DriveClient:
            client = DriveClient()  ← This line triggers __init__
        
        __init__ is a special Python method called the "constructor."
        It runs once when you create an object. Think of it like the setup
        that happens when you first turn on a new phone — it configures
        everything before you can use it.
        
        This constructor:
        1. Creates an empty 'service' attribute (will be filled later)
        2. Calls _authenticate() to log into Google Drive
        
        Raises:
            FileNotFoundError: If credentials.json is missing
            Exception: If authentication fails for any reason
        """
        # The Drive API service object — our "connection" to Google Drive.
        # We set it to None first because authentication hasn't happened yet.
        # After _authenticate() runs, this will be set to a real service object.
        self.service = None
        
        # Call the private authentication method.
        # The underscore prefix '_' is a Python convention meaning
        # "this method is for internal use only" — other files shouldn't
        # call _authenticate() directly, they just create a DriveClient().
        self._authenticate()
    
    def _authenticate(self) -> None:
        """
        Authenticate with Google Drive API using OAuth 2.0.
        
        WHY IS AUTHENTICATION NEEDED?
        ==============================
        Google Drive contains your private files. Google needs to make sure
        that only YOU (or apps you've approved) can access them.
        
        Authentication is like going through airport security:
        1. Show your passport (credentials.json = your app's identity)
        2. Get a boarding pass (token = proof you're allowed access)
        3. Next time, just show the boarding pass (reuse saved token)
        4. If boarding pass expired, get a new one (refresh token)
        
        AUTHENTICATION FLOW:
        ====================
        1. Check if we have a saved token (token.json)
        2. If token exists and is still valid → use it (fastest)
        3. If token is expired → try to refresh it automatically
        4. If no token at all → open browser for user to log in
        5. Save the new/refreshed token for future use
        
        This is a private method (prefixed with _) because it's only
        used internally by the class. Outside code never calls this directly.
        
        '-> None' means this method doesn't return anything.
        It just sets up self.service as a side effect.
        """
        # Will hold our authentication credentials (like a key card).
        # Start as None because we haven't loaded anything yet.
        creds = None
        
        # =====================================================================
        # STEP 1: Try to load an existing token from a previous login
        # =====================================================================
        # token.json stores the user's access and refresh tokens from last time.
        # If this file exists, the user has logged in before, so we can skip
        # the browser login and reuse the saved credentials.
        if os.path.exists(TOKEN_FILE):
            if VERBOSE_MODE:
                print("→ Loading existing authentication token...")
            
            # Load credentials from the saved JSON file.
            # SCOPES is passed to verify the token has the right permissions.
            # If the saved token was for different permissions, it will be invalid.
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
        # =====================================================================
        # STEP 2: Check if credentials need to be refreshed or created
        # =====================================================================
        # 'not creds' = no credentials loaded (token file didn't exist)
        # 'not creds.valid' = credentials exist but are expired/invalid
        # If either is true, we need to fix the situation.
        if not creds or not creds.valid:
            
            # -----------------------------------------------------------------
            # STEP 2a: Try to refresh expired credentials
            # -----------------------------------------------------------------
            # If we have credentials AND they're expired AND we have a refresh
            # token, we can ask Google for a fresh token WITHOUT the user logging
            # in again. This happens silently behind the scenes.
            #
            # A refresh token is like a coupon that says "come back for a new
            # key card without re-doing security." It lasts longer than the
            # regular token.
            if creds and creds.expired and creds.refresh_token:
                if VERBOSE_MODE:
                    print("→ Refreshing expired token...")
                # Send a request to Google to get a fresh access token.
                # Request() creates an HTTP transport to communicate with Google.
                creds.refresh(Request())
                
            # -----------------------------------------------------------------
            # STEP 2b: No valid credentials at all — need full login
            # -----------------------------------------------------------------
            else:
                # First, make sure the credentials.json file exists.
                # Without it, we can't even start the login process.
                if not os.path.exists(CREDENTIALS_FILE):
                    # Raise a helpful error message with instructions.
                    # 'raise' stops the program and shows an error message.
                    raise FileNotFoundError(
                        f"\n❌ Credentials file not found: {CREDENTIALS_FILE}\n"
                        "\n📋 To fix this:\n"
                        "1. Go to https://console.cloud.google.com\n"
                        "2. Create a project and enable Google Drive API\n"
                        "3. Go to APIs & Services > Credentials\n"
                        "4. Create OAuth 2.0 credentials (Desktop App)\n"
                        "5. Download and save as 'credentials.json' in the project folder\n"
                    )
                
                if VERBOSE_MODE:
                    print("→ Opening browser for Google authentication...")
                    print("  (A browser window will open for you to log in)")
                
                # Check if the user has stored their Google API credentials
                # as environment variables (in a .env file) instead of in
                # the credentials.json file. This is more secure because
                # env variables are not committed to version control.
                client_id = os.getenv('GOOGLE_CLIENT_ID')
                client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
                
                if client_id and client_secret:
                    # Build the client config dictionary from environment variables.
                    # This dictionary mimics the structure of credentials.json.
                    # "installed" means this is a desktop app (not a web app).
                    client_config = {
                        "installed": {
                            "client_id": client_id,         # Unique ID for our app
                            "client_secret": client_secret, # Secret key for our app
                            # URLs that Google uses for the login process:
                            "auth_uri": os.getenv('GOOGLE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
                            "token_uri": os.getenv('GOOGLE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
                            # Where Google redirects after login:
                            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                        }
                    }
                    # Create the OAuth flow from the config dictionary.
                    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                else:
                    # Create OAuth flow from the credentials.json file directly.
                    # This reads the client_id and client_secret from the file.
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CREDENTIALS_FILE,
                        SCOPES
                    )
                
                # Start the local login process.
                # This opens a browser window where the user logs into Google.
                # port=0 means "use any available port" on your computer.
                # A port is like a door number — Google will send the login
                # result back to this door after the user approves access.
                # The function waits until the user completes the login.
                creds = flow.run_local_server(port=0)
            
            # -----------------------------------------------------------------
            # STEP 3: Save the credentials for next time
            # -----------------------------------------------------------------
            # Write the token to a JSON file so the user doesn't need to
            # log in every single time they run the app.
            # 'w' means "write mode" — creates the file or overwrites it.
            with open(TOKEN_FILE, 'w') as token_file:
                # Convert credentials to JSON string and write to file.
                token_file.write(creds.to_json())
                if VERBOSE_MODE:
                    print(f"→ Token saved to {TOKEN_FILE}")
        
        # =====================================================================
        # STEP 4: Build the Drive API service object
        # =====================================================================
        # 'build()' creates a service object that we can use to call Drive API.
        # Think of it as connecting a phone call to Google Drive's headquarters:
        #   'drive' = which department (Drive, Gmail, Calendar, etc.)
        #   'v3'    = which version of the API (v3 is the latest)
        #   credentials = our ID card proving we're authorized
        #
        # After this line, self.service has methods like:
        #   self.service.files().list() — list files
        #   self.service.files().create() — create/upload files
        #   self.service.files().delete() — delete files
        self.service = build('drive', 'v3', credentials=creds)
        
        if VERBOSE_MODE:
            print("✓ Successfully connected to Google Drive")
    
    def find_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[Dict]:
        """
        Search for a folder by name in Google Drive.
        
        This is like using the search bar in Google Drive, but we only
        search for FOLDERS (not files) and we need an exact name match.
        
        NEW IMPROVEMENT: This search is now CASE-INSENSITIVE.
        Google Drive's API is case-sensitive by default. If we look for 
        "Akshay" but the folder is named "akshay", the API returns nothing.
        To fix this, if the exact search fails, we list all folders in the
        parent and check for a case-insensitive match in Python.
        
        Args:
            folder_name: The name of the folder to find
            parent_id: Optional - ID of parent folder to search within.
        
        Returns:
            Dict with folder info (id, name, parents) if found
            None if folder doesn't exist
        """
        # STEP 1: Try an exact case search first (fastest)
        query = (
            f"name='{folder_name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )
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
            
        # STEP 2: Case-insensitive fallback
        # If the exact search failed, we list all folders in the parent
        # and compare them case-insensitively. This prevents creating
        # duplicate folders like "akshay" and "Akshay".
        if VERBOSE_MODE:
            print(f"  → Exact match for '{folder_name}' not found. Checking case-insensitively...")
            
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
                if VERBOSE_MODE:
                    print(f"    ✓ Found case-insensitive match: '{folder['name']}'")
                return folder
                
        return None
    
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Dict:
        """
        Create a new folder in Google Drive.
        
        This is like right-clicking in Drive and selecting "New Folder."
        
        Args:
            folder_name: Name for the new folder (e.g., "Feb" or "2026-02-03")
            parent_id: Optional - ID of parent folder.
                       If None, creates in the Drive root (top level).
                       If provided, creates INSIDE that folder.
        
        Returns:
            Dict with the new folder's info (id, name)
        
        Example:
            >>> folder = client.create_folder("NewFolder")
            >>> print(f"Created folder with ID: {folder['id']}")
        """
        # Prepare the metadata (information) for the new folder.
        # In Google Drive, folders are special files with a specific mimeType.
        # 'mimeType': 'application/vnd.google-apps.folder' tells Google
        # "this is a folder, not a regular file."
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        # If a parent folder is specified, put the new folder inside it.
        # 'parents' takes a LIST of parent IDs (always a list, even for one parent).
        # This is how Google Drive handles folder nesting.
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        # Send the create request to Google Drive.
        # body = the metadata describing what to create
        # fields = what info to return about the newly created folder
        #          (we only need id and name)
        # .execute() sends the request to Google's servers
        folder = self.service.files().create(
            body=file_metadata,
            fields='id, name'
        ).execute()
        
        if VERBOSE_MODE:
            print(f"  ✓ Created folder: {folder_name}")
        
        # Return the folder info dict (contains 'id' and 'name').
        return folder
    
    def list_root_folders(self) -> List[Dict]:
        """
        List all folders at the ROOT level of Google Drive.
        
        "Root" means the top level — not inside any other folder.
        These are the main folders you see when you open Google Drive.
        
        WHY IS THIS IMPORTANT?
        Our app matches file groups to EXISTING folders in the Drive root.
        For example, if you have files named "akshay123.pdf", the app looks
        for a root folder called "akshay" to upload them to.
        
        Returns:
            List of folder info dicts, each containing 'id' and 'name'
        
        Example:
            >>> folders = client.list_root_folders()
            >>> for f in folders:
            ...     print(f"- {f['name']}")
            # Output:
            # - akshay
            # - invoices
            # - reports
        """
        # Build the search query for root-level folders:
        # '{BASE_FOLDER_ID}' in parents → only folders at the top level (not nested)
        #   of our target area.
        # mimeType filter → only folders (not regular files)
        # trashed=false → exclude deleted items
        query = (
            f"'{BASE_FOLDER_ID}' in parents "
            "and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        
        # Execute the search.
        # orderBy='name' sorts results alphabetically by folder name.
        # This makes the output more organized and predictable.
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            orderBy='name'  # Sort alphabetically
        ).execute()
        
        # Return the list of folders (or empty list if none found).
        return results.get('files', [])
    
    def list_files_in_folder(self, folder_id: str) -> List[Dict]:
        """
        List all files (and subfolders) inside a specific folder.
        
        This is like opening a folder in Google Drive and seeing what's inside.
        
        Args:
            folder_id: The ID of the folder to look inside.
                       Every file/folder in Google Drive has a unique ID
                       (a long string of characters) that acts like an address.
        
        Returns:
            List of file info dicts, each containing 'id', 'name', 'mimeType'
        """
        # Query for all items whose parent is this folder.
        # '{folder_id}' in parents → items inside this folder
        # trashed=false → exclude deleted items
        query = f"'{folder_id}' in parents and trashed=false"
        
        # Execute the search and return results.
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType)'
        ).execute()
        
        return results.get('files', [])
    
    def upload_file(
        self, 
        local_path: str, 
        folder_id: str, 
        custom_name: str = None
    ) -> Dict:
        """
        Upload a file from your computer to Google Drive.
        
        This is the core function — it takes a file on your computer
        and copies it to a specific folder in Google Drive.
        
        Args:
            local_path: Full path to the file on your computer
                        Example: "/Users/ak/Desktop/report.pdf"
            folder_id: ID of the target folder in Drive
                       Example: "1A2B3C4D5E6F" (a unique identifier)
            custom_name: Optional - rename the file in Drive.
                         If None, keeps the original filename.
                         Example: "report_v2.pdf"
        
        Returns:
            Dict with the uploaded file's info (id, name)
        
        Raises:
            FileNotFoundError: If the local file doesn't exist
        
        Example:
            >>> result = client.upload_file(
            ...     "/path/to/document.pdf",
            ...     "1234567890abcdef"
            ... )
            >>> print(f"Uploaded: {result['name']}")
        """
        # Safety check: make sure the file actually exists on this computer.
        # We don't want to try uploading a file that's not there!
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"File not found: {local_path}")
        
        # Decide what to name the file in Google Drive.
        # If custom_name is provided, use that. Otherwise, extract the
        # filename from the full path using os.path.basename().
        # Example: "/Users/ak/Desktop/report.pdf" → "report.pdf"
        file_name = custom_name if custom_name else os.path.basename(local_path)
        
        # Prepare the metadata (information) for the new file.
        # 'name' = what the file will be called in Drive
        # 'parents' = which folder to put it in (as a list)
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        # Create a MediaFileUpload object that handles reading the file
        # from your computer and sending it to Google's servers.
        # resumable=True enables "chunked" uploading — the file is sent
        # in pieces (chunks). If the upload fails halfway through (maybe
        # your internet disconnected), it can RESUME from where it stopped
        # instead of starting over. This is crucial for large files!
        media = MediaFileUpload(local_path, resumable=True)
        
        # Actually upload the file to Google Drive.
        # body = the metadata (name, parent folder)
        # media_body = the actual file content
        # fields = what info to return about the uploaded file
        # .execute() sends the request
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name'
        ).execute()
        
        if VERBOSE_MODE:
            print(f"  ✓ Uploaded: {file_name}")
        
        # Return info about the uploaded file (id and name).
        return file
    
    def delete_file(self, file_id: str) -> None:
        """
        Permanently delete a file from Google Drive.
        
        ⚠️ WARNING: This PERMANENTLY deletes the file!
        It does NOT move it to the Trash — it's gone forever.
        This is used when DUPLICATE_HANDLING is set to 'overwrite':
        the old file is deleted before uploading the replacement.
        
        WHY permanent delete instead of trash?
        Because if we're overwriting, we want a clean replacement.
        Trashed files would just pile up and waste storage.
        
        Args:
            file_id: The unique ID of the file to delete
                     (every file in Drive has a unique ID string)
        """
        # Call the Drive API to delete the file.
        # fileId = the unique identifier of the file to delete.
        # .execute() sends the delete request to Google's servers.
        self.service.files().delete(fileId=file_id).execute()
        
        if VERBOSE_MODE:
            print(f"  ✓ Deleted file: {file_id}")
