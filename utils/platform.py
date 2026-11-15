"""
platform.py - Cross-Platform Utilities

Provides helper functions for running the Drive Organizer on
both macOS and Windows without code changes.

Functions:
    get_desktop_path() → Path to the user's Desktop folder
    setup_encoding()   → Fix emoji/unicode output on Windows terminals

Author: Akshay Reddy
"""

import sys
import io
import platform
from pathlib import Path


def get_desktop_path() -> Path:
    """
    Find the user's Desktop folder on any OS.

    - macOS / Linux: ~/Desktop
    - Windows: reads the actual Desktop location from the Windows registry.
      This handles localized Windows (e.g. German "Schreibtisch") and
      cases where the user has moved their Desktop to another drive.

    Returns:
        Path object pointing to the Desktop folder.

    Raises:
        FileNotFoundError: if the Desktop folder does not exist.
    """
    desktop = None

    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            desktop = Path(winreg.QueryValueEx(key, "Desktop")[0])
            winreg.CloseKey(key)
        except Exception:
            # Fall through to the default below
            pass

    if desktop is None:
        desktop = Path.home() / "Desktop"

    if not desktop.exists():
        raise FileNotFoundError(f"Desktop folder not found at: {desktop}")

    return desktop


def setup_encoding():
    """
    Ensure stdout can handle emoji / unicode characters.

    On older Windows terminals (cmd.exe, PowerShell < 7) the default
    encoding is cp1252 or similar, which chokes on emoji like ✅ ❌ 📂.
    This function wraps stdout in a UTF-8 TextIOWrapper with 'replace'
    error handling so that emojis render or degrade gracefully instead
    of crashing the program.

    Safe to call on macOS / Linux — it's a no-op if encoding is already utf-8.
    """
    if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
        except Exception:
            pass  # If it fails (e.g. no buffer), just leave stdout alone

    if sys.stderr and sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        try:
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )
        except Exception:
            pass
