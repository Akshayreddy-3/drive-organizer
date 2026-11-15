#!/usr/bin/env python3
"""
app.py — Drive Organizer app (runs in your browser, on this computer only)

Start it with the launcher ("Drive Organizer.command" on Mac, "Drive Organizer.bat"
on Windows) or:  python3 app.py

Pages:
  Run       — rename scanned PDFs, upload to Drive (each with a preview first)
  History   — the upload tracker dashboard
  Settings  — your Drive destination link, your company list, Google sign-in, setup check

Each person's settings stay on their own computer: the Drive folder and scan folder
in .env, the company list encrypted in companies_reference.enc.
"""

import argparse
import csv
import io
import json
import os
import platform
import plistlib
import re
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values, set_key

import secure_companies
from dashboard_server import DashboardHandler, PROJECT_DIR, load_tracker_data
from utils.platform import get_desktop_path, setup_encoding

ENV_FILE = os.path.join(PROJECT_DIR, ".env")
LOCAL_MODEL = "qwen3:4b"          # keep in sync with LOCAL_MODEL in ai_pdf_renamer.py


# ── Settings (.env) ──────────────────────────────────────────────────────────
def env() -> dict:
    return dotenv_values(ENV_FILE) if os.path.exists(ENV_FILE) else {}


def save_env(key: str, value: str):
    if not os.path.exists(ENV_FILE):
        open(ENV_FILE, "w").close()
    set_key(ENV_FILE, key, value)


def drive_folder_id(link: str):
    """Folder ID from a Drive folder link (or a bare ID); None if it isn't one."""
    link = link.strip()
    m = (re.search(r"/folders/([\w-]+)", link) or re.search(r"[?&]id=([\w-]+)", link)
         or re.fullmatch(r"([\w-]{10,})", link))
    return m.group(1) if m else None


def scan_folder() -> str:
    return env().get("SCAN_FOLDER") or str(get_desktop_path())


def clean_folder(text: str) -> str:
    """A typed or pasted folder in the form that is safe to keep in .env: forward slashes and no
    trailing separator. A Windows path ending in a backslash makes the rest of .env unreadable,
    and a network path (\\\\server\\share) is read back with a backslash missing."""
    text = text.strip().strip('"').strip()        # Windows "Copy as path" adds the quotes
    return Path(os.path.expanduser(text)).as_posix() if text else ""


LAUNCH_LABEL = "com.driveorganizer.app"


def autostart_path() -> str:
    """The file that makes this computer start the app at sign-in ('' where that isn't supported)."""
    if platform.system() == "Darwin":
        return os.path.expanduser(f"~/Library/LaunchAgents/{LAUNCH_LABEL}.plist")
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu",
                            "Programs", "Startup", "Drive Organizer.vbs")
    return ""


def autostart_enabled() -> bool:
    path = autostart_path()
    return bool(path) and os.path.exists(path)


def set_autostart(on: bool):
    """Turn 'start when I sign in' on or off for this user only (no administrator needed)."""
    path = autostart_path()
    if not path:
        raise ValueError("Starting automatically isn't available on this system.")
    if platform.system() == "Darwin":
        service = f"gui/{os.getuid()}/{LAUNCH_LABEL}"
        subprocess.run(["launchctl", "bootout", service], capture_output=True)     # replace any older copy
        if on:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                plistlib.dump({
                    "Label": LAUNCH_LABEL,
                    "ProgramArguments": [sys.executable, os.path.join(PROJECT_DIR, "app.py"), "--no-open"],
                    "WorkingDirectory": PROJECT_DIR,
                    "RunAtLoad": True,
                    "KeepAlive": {"SuccessfulExit": False},      # restart if it crashes, not if it quits
                    "StandardOutPath": os.path.expanduser("~/Library/Logs/DriveOrganizer.log"),
                    "StandardErrorPath": os.path.expanduser("~/Library/Logs/DriveOrganizer.log"),
                }, f)
            started = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", path],
                                     capture_output=True, text=True)
            if started.returncode:
                os.remove(path)
                raise ValueError("macOS wouldn't start it: " + (started.stderr.strip() or "unknown error"))
        elif os.path.exists(path):
            os.remove(path)
    elif on:
        pythonw = sys.executable[:-len("python.exe")] + "pythonw.exe" if sys.executable.lower().endswith("python.exe") else sys.executable
        script = (f'Set s = CreateObject("WScript.Shell")\r\ns.CurrentDirectory = "{PROJECT_DIR}"\r\n'
                  f's.Run """{pythonw}"" ""app.py"" --no-open", 0, False\r\n')   # 0 = no window
        with open(path, "w", encoding="ascii", newline="") as f:
            f.write(script)
    elif os.path.exists(path):
        os.remove(path)


PICK_PROMPT = "Choose the folder with your scanned files"


def pick_folder() -> str:
    """Show the system's own folder chooser on this computer; '' if the user cancels."""
    system = platform.system()
    if system == "Darwin":
        cmd = ["osascript", "-e", f'POSIX path of (choose folder with prompt "{PICK_PROMPT}")']
    elif system == "Windows":
        cmd = ["powershell", "-NoProfile", "-STA", "-Command",
               "Add-Type -AssemblyName System.Windows.Forms; "
               "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
               f"$d.Description = '{PICK_PROMPT}'; "
               "$top = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}; "
               "if ($d.ShowDialog($top) -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }"]
    else:
        raise ValueError("Type the folder path instead; there is no folder chooser on this system.")
    return clean_folder(subprocess.run(cmd, capture_output=True, text=True).stdout)


def project_path(value, default_name: str) -> str:
    return os.path.join(PROJECT_DIR, value or default_name)   # absolute values pass through


# ── Company list ─────────────────────────────────────────────────────────────
def load_companies() -> list:
    """Raises RuntimeError if a saved list exists but can't be opened (missing or wrong key)."""
    return secure_companies.load_encrypted_reference(strict=True).get("companies", [])


def clean_companies(rows) -> list:
    """Validate what the Settings page sends; raises ValueError with a readable message."""
    if not isinstance(rows, list):
        raise ValueError("Expected a list of companies.")
    cleaned, seen = [], set()
    for row in rows:
        name = str(row.get("name", "")).strip() if isinstance(row, dict) else ""
        if not name:
            continue
        if name.lower() in seen:
            raise ValueError(f'"{name}" is in the list twice.')
        seen.add(name.lower())
        addresses = row.get("addresses", [])
        if not isinstance(addresses, list):
            raise ValueError(f'Addresses for "{name}" must be a list.')
        cleaned.append({"name": name,
                        "addresses": [str(a).strip() for a in addresses if str(a).strip()]})
    return cleaned


def parse_import(text: str) -> list:
    """Companies from a pasted/loaded file: this app's JSON, or CSV with the name in
    the first column and one address in each following column."""
    try:
        data = json.loads(text)
        return clean_companies(data.get("companies", []) if isinstance(data, dict) else data)
    except json.JSONDecodeError:
        pass
    merged = {}
    for i, row in enumerate(csv.reader(io.StringIO(text))):
        cells = [c.strip() for c in row]
        if not cells or not cells[0]:
            continue
        if i == 0 and cells[0].lower() in ("name", "company", "company name"):
            continue
        entry = merged.setdefault(cells[0].lower(), {"name": cells[0], "addresses": []})
        entry["addresses"] += [c for c in cells[1:] if c and c not in entry["addresses"]]
    return list(merged.values())


# ── Setup check ──────────────────────────────────────────────────────────────
def ollama_status(url: str) -> str:
    """'ready', 'no-model' or 'offline'."""
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=2) as resp:
            names = {m["name"] for m in json.loads(resp.read()).get("models", [])}
    except Exception:
        return "offline"
    return "ready" if LOCAL_MODEL in names or f"{LOCAL_MODEL}:latest" in names else "no-model"


def state() -> dict:
    e = env()
    folder_id = e.get("BASE_FOLDER_ID") or ""
    try:
        companies_count, companies_error = len(load_companies()), ""
    except RuntimeError as err:
        companies_count, companies_error = 0, str(err)
    return {
        "platform": platform.system(),
        "local_model": LOCAL_MODEL,
        "can_autostart": bool(autostart_path()),
        "autostart": autostart_enabled(),
        "scan_folder": scan_folder(),
        "drive_link": f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else "",
        "companies_count": companies_count,
        "companies_error": companies_error,
        "has_credentials": os.path.exists(project_path(e.get("CREDENTIALS_FILE"), "credentials.json")),
        "signed_in": os.path.exists(project_path(e.get("TOKEN_FILE"), "token.json")),
        "ollama": ollama_status(e.get("OLLAMA_URL") or "http://localhost:11434"),
    }


# ── Jobs: run the existing scripts and collect their output ─────────────────
ACTIONS = {
    "rename_preview": lambda folder: ["ai_pdf_renamer.py", folder, "--dry-run"],
    "rename_apply":   lambda folder: ["ai_pdf_renamer.py", folder, "--apply"],
    "upload_preview": lambda folder: ["run_upload.py", "--preview", "--path", folder],
    "upload":         lambda folder: ["run_upload.py", "--path", folder],
    "signin":         lambda folder: ["-c", "from src.drive_client import DriveClient; DriveClient()"],
}

job = {"action": None, "lines": [], "running": False, "code": None, "proc": None}
job_lock = threading.Lock()


def start_job(action: str, folder: str):
    """Start one action; raises ValueError (shown to the user) if it can't run."""
    if action not in ACTIONS:
        raise ValueError("Unknown action.")
    if action != "signin" and not os.path.isdir(folder):
        raise ValueError(f"Folder not found: {folder}")
    if action == "rename_preview" and not load_companies():
        raise ValueError("Your company list is empty. Add your companies in Settings first.")
    if action.startswith("upload") and not env().get("BASE_FOLDER_ID"):
        raise ValueError("No Drive destination yet. Add your Drive folder link in Settings first.")

    with job_lock:
        if job["running"]:
            raise ValueError("Something is already running. Wait for it to finish or press Stop.")
        # .env is re-read here so a setting saved a moment ago applies to this run
        child_env = {**os.environ, **{k: v for k, v in env().items() if v is not None},
                     "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen([sys.executable] + ACTIONS[action](folder), cwd=PROJECT_DIR,
                                env=child_env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        job.update(action=action, lines=[], running=True, code=None, proc=proc)

    def collect():
        for line in proc.stdout:
            job["lines"].append(line.rstrip("\n"))
        job.update(code=proc.wait(), running=False)

    threading.Thread(target=collect, daemon=True).start()


# ── HTTP ─────────────────────────────────────────────────────────────────────
class AppHandler(DashboardHandler):
    """The app's pages and API, on top of the tracker dashboard's routes."""

    def _is_local(self) -> bool:
        """Only answer requests addressed to this computer (blocks DNS-rebinding pages)."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if host in ("localhost", "127.0.0.1"):
            return True
        self._send_json({"error": "Forbidden"}, status=403)
        return False

    def do_GET(self):
        if not self._is_local():
            return
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/app.html"):
            self.path = "/app.html"
            return SimpleHTTPRequestHandler.do_GET(self)
        if parsed.path == "/api/state":
            return self._send_json(state())
        if parsed.path == "/api/companies":
            try:
                return self._send_json({"companies": load_companies()})
            except RuntimeError as err:      # an unreadable list is an error, never an empty list
                return self._send_json({"error": str(err)}, status=500)
        if parsed.path == "/api/job":
            since = int(parsed.query.split("=")[1]) if parsed.query.startswith("since=") else 0
            return self._send_json({"action": job["action"], "running": job["running"],
                                    "code": job["code"], "lines": job["lines"][since:]})
        if parsed.path == "/tracker_data.json":      # empty history instead of a 404 before the first upload
            return self._send_json(load_tracker_data())
        return super().do_GET()

    def do_POST(self):
        if not self._is_local():
            return
        # Other websites can't send JSON here without permission this server never gives
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._send_json({"error": "Forbidden"}, status=403)
        path = urlparse(self.path).path
        if path.startswith("/api/verify"):
            return super().do_POST()
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self._send_json(self._handle(path, body))
        except (ValueError, RuntimeError) as e:      # bad input, or a company list that can't be opened
            self._send_json({"error": str(e)}, status=400)
        except Exception as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, status=500)

    def _handle(self, path: str, body: dict) -> dict:
        if path == "/api/settings":
            folder_id = drive_folder_id(body.get("drive_link", ""))
            if not folder_id:
                raise ValueError("That doesn't look like a Google Drive folder link. Open the folder "
                                 "in Drive and copy the address from the browser.")
            save_env("BASE_FOLDER_ID", folder_id)
        elif path == "/api/companies":
            companies = clean_companies(body.get("companies"))
            secure_companies.save_encrypted_reference({"companies": companies})
        elif path == "/api/companies/import":
            return {"companies": parse_import(body.get("text", ""))}
        elif path == "/api/run":
            folder = clean_folder(str(body.get("folder") or "")) or scan_folder()
            start_job(body.get("action"), folder)
            if body.get("action") != "signin":
                save_env("SCAN_FOLDER", folder)
        elif path == "/api/autostart":
            set_autostart(bool(body.get("on")))
        elif path == "/api/pick-folder":
            return {"folder": pick_folder()}
        elif path == "/api/stop":
            if job["running"]:
                job["proc"].terminate()
        elif path == "/api/signout":
            token = project_path(env().get("TOKEN_FILE"), "token.json")
            if os.path.exists(token):
                os.remove(token)
        else:
            raise ValueError("Not found")
        return {"ok": True}

    def log_message(self, format, *args):
        pass   # the page polls every second; don't flood the launcher window


def main():
    parser = argparse.ArgumentParser(description="Drive Organizer app")
    parser.add_argument("--port", type=int, default=8686)
    parser.add_argument("--no-open", action="store_true", help="Don't open the browser")
    args = parser.parse_args()
    setup_encoding()

    url = f"http://localhost:{args.port}"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), AppHandler)   # this computer only
    except OSError:
        print(f"Drive Organizer is already running at {url}")
        if not args.no_open:
            webbrowser.open(url)
        return

    print(f"\n  📁 Drive Organizer is running at {url}")
    print("     Keep this window open while you use the app. Close it (or press Ctrl+C) to quit.\n")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if job["running"]:
            job["proc"].terminate()
        print("\n  👋 Drive Organizer stopped.\n")


if __name__ == "__main__":
    main()
