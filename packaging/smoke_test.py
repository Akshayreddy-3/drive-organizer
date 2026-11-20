#!/usr/bin/env python3
"""
packaging/smoke_test.py — end-to-end check of the PACKAGED app (not the source).

    python packaging/smoke_test.py "<path to the packaged program>"

Mac:     dist/Drive Organizer.app/Contents/MacOS/Drive Organizer
Windows: the installed  Drive Organizer.exe

It starts the packaged app on a spare port, with a stand-in model server and made-up
letters, and drives it the way the page does: settings, company list, a rename preview
(including the vision fallback), applying the renames, Stop, a second start, and Quit.
Needs only Python itself. Uploading to Google Drive is not covered (it needs an account).

On a Mac the app's data goes to a temporary home folder, so a real install is untouched.
On Windows it uses the real %APPDATA%\\Drive Organizer; run it there on a build machine only.
"""

import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WINDOWS = platform.system() == "Windows"
FABRIKAM = "Fabrikam Holdings LLC"
failures = []


def check(name: str, ok: bool, detail=""):
    print(("  ✓ " if ok else "  ✗ ") + name + (f"   [{detail}]" if detail and not ok else ""), flush=True)
    if not ok:
        failures.append(name)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── Stand-in model server: answers like Ollama, and records what it was sent ──
model_requests = []     # True for a request that carried page images
models_used = []        # the model name each request asked for
server_models = [{"name": "qwen3:4b", "digest": "aaa", "capabilities": ["completion"]},
                 {"name": "gemma4:latest", "digest": "bbb", "capabilities": ["completion", "vision"]}]


class FakeOllama(BaseHTTPRequestHandler):
    def _reply(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._reply({"models": server_models})

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/copy":             # Settings pointing a fixed name at a chosen model
            source = next(m for m in server_models if m["name"] == request["source"])
            server_models[:] = [m for m in server_models if m["name"] != request["destination"]]
            server_models.append(dict(source, name=request["destination"]))
            return self._reply({})
        models_used.append(request["model"])
        message = request["messages"][0]
        model_requests.append(bool(message.get("images")))
        if "WHO IS IT ADDRESSED TO" in message["content"].upper():
            answer = {"recipient": "UNKNOWN"}        # the stray letter isn't for any of your companies
        elif message.get("images"):
            answer = {"sender": "Globex Insurance"}
        elif "NORTHWIND" in message["content"].upper():
            answer = {"sender_as_printed": "NORTHWIND UTILITIES CORPORATION", "sender": "Northwind Utilities"}
        else:
            answer = {"sender_as_printed": "UNKNOWN", "sender": "UNKNOWN"}
        self._reply({"message": {"content": json.dumps(answer)}})

    def log_message(self, *args):
        pass


# Run inside the packaged app (its own PDF library): three made-up letters and one stray file.
MAKE_LETTERS = r'''
import os, sys, fitz
folder = sys.argv[3]
def letter(name, lines):
    doc = fitz.open(); page = doc.new_page(); y = 80
    for size, text in lines:
        page.insert_text((60, y), text, fontsize=size); y += size * 1.8
    doc.save(os.path.join(folder, name))
to = [(12, ""), (12, "Fabrikam Holdings LLC"), (12, "12 Example Road"), (12, "Springfield"), (12, "")]
letter("scan05142026212549.pdf", [(22, "NORTHWIND UTILITIES CORPORATION"), (11, "500 Example Avenue")] + to
       + [(12, "Dear customer, your monthly statement is enclosed.")])
letter("scan05142026212550.pdf", to + [(12, "Dear customer, please find your renewal notice enclosed.")])
letter("scan05142026212551.pdf", [(12, "Initech Partners"), (12, "77 Sample Street"), (12, "Dear customer, hello.")])
open(os.path.join(folder, "notes.txt"), "w").write("not a scan")
'''

BUNDLED_LIBRARIES = r'''
import cryptography, fitz, PIL, rapidfuzz, httplib2
from googleapiclient.discovery_cache import get_static_doc
assert get_static_doc("drive", "v3"), "Google Drive API description is missing from the package"
status = httplib2.Http(timeout=30).request("https://www.googleapis.com/discovery/v1/apis?name=drive")[0].status
assert status == 200, f"secure connection to Google failed: {status}"
print("libraries ok")
'''


def main():
    exe = os.path.abspath(sys.argv[1])
    work = tempfile.mkdtemp(prefix="drive-organizer-test-")
    scans = os.path.join(work, "scans")
    os.makedirs(scans)
    app_env = dict(os.environ)
    if WINDOWS:
        data_dir = os.path.join(os.environ["APPDATA"], "Drive Organizer")
    else:                                   # a throwaway home folder keeps a real install untouched
        app_env["HOME"] = work
        os.makedirs(os.path.join(work, "Desktop"))
        data_dir = os.path.join(work, "Library", "Application Support", "Drive Organizer")

    def run_in_app(code, *args, timeout=300):
        return subprocess.run([exe, "-c", code, *args], env=app_env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)

    print("\nPackaged program:", exe)
    print("\n1. What is inside the package")
    out = run_in_app(BUNDLED_LIBRARIES)
    check("libraries load, Google's API description is included, secure connection to Google works",
          "libraries ok" in out.stdout, (out.stdout + out.stderr)[-400:])
    out = run_in_app(MAKE_LETTERS, scans)
    check("the app's PDF library writes the test letters", len(os.listdir(scans)) == 4, out.stderr[-400:])

    model = ThreadingHTTPServer(("127.0.0.1", free_port()), FakeOllama)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    model_url = f"http://127.0.0.1:{model.server_address[1]}"

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    app = subprocess.Popen([exe, "--no-open", "--port", str(port)], env=app_env)

    def call(path, body=None, headers=None, raw=False):
        """(status, parsed JSON or text) for a GET, or a JSON POST when body is given."""
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(base + path, data=data,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                status, text = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, text = e.code, e.read().decode("utf-8", "replace")
        return status, (text if raw else json.loads(text or "{}"))

    def wait_for_job(limit=900):
        deadline = time.time() + limit
        while time.time() < deadline:
            job = call("/api/job")[1]
            if not job["running"] and job["code"] is not None:
                return job
            time.sleep(1)
        return {"code": "timed out", "lines": call("/api/job")[1]["lines"]}

    try:
        print("\n2. Starting")
        started = False
        for _ in range(90):
            try:
                started = call("/api/state")[0] == 200
                break
            except (urllib.error.URLError, OSError):
                time.sleep(1)
        check("the app starts and answers", started)
        if not started:
            return
        state = call("/api/state")[1]
        check("a fresh install starts empty", not state["drive_link"] and state["companies_count"] == 0
              and not state["signed_in"] and not state["has_credentials"], json.dumps(state)[:300])

        print("\n3. Pages and safety")
        check("the app page loads", call("/", raw=True)[0] == 200)
        check("the History page loads", call("/tracker.html", raw=True)[0] == 200)
        check("History shows empty data before the first upload", call("/tracker_data.json")[1].get("total_files") == 0)
        check("settings files are never served", call("/.env", raw=True)[0] == 404 and call("/token.json", raw=True)[0] == 404)
        check("requests addressed to another site are refused", call("/api/state", headers={"Host": "evil.example"})[0] == 403)
        check("form posts from other websites are refused",
              call("/api/quit", body=b"{}", headers={"Content-Type": "text/plain"})[0] == 403)

        print("\n4. Settings")
        check("a wrong Drive link is refused", call("/api/settings", {"drive_link": "hello"})[0] == 400)
        check("a Drive link is saved", call("/api/settings", {"drive_link": "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWx"})[0] == 200
              and "1AbCdEfGhIjKlMnOpQrStUvWx" in call("/api/state")[1]["drive_link"])
        check("a model server on the public internet over plain http is refused",
              call("/api/ollama", {"url": "http://8.8.8.8:11434"})[0] == 400)
        status, saved = call("/api/ollama", {"url": model_url})
        check("the model server address is saved and reachable", status == 200 and saved.get("status") == "ready", str(saved))
        status, models = call("/api/models")
        check("Settings lists the server's models and the default choice", status == 200 and models.get("text") == "qwen3:4b"
              and models.get("vision") == "gemma4:latest" and [m["name"] for m in models["models"] if m["vision"]] == ["gemma4:latest"], str(models))
        check("a picture model that can't read pictures is refused",
              call("/api/models", {"text": "qwen3:4b", "vision": "qwen3:4b"})[0] == 400)
        status, _ = call("/api/models", {"text": "gemma4:latest", "vision": "gemma4:latest"})
        check("a model choice is saved on the server", status == 200 and call("/api/models")[1].get("text") == "gemma4:latest")
        check("something that isn't a Google access file is refused", call("/api/credentials", {"text": "{\"a\": 1}"})[0] == 400)
        fake_credentials = json.dumps({"installed": {"client_id": "test", "client_secret": "test"}})
        check("a Google access file is added", call("/api/credentials", {"text": fake_credentials})[0] == 200
              and call("/api/state")[1]["has_credentials"])
        check("a rename with no company list is refused with a reason",
              call("/api/run", {"action": "rename_preview", "folder": scans})[0] == 400)
        imported = call("/api/companies/import", {"text": "name,address\nFabrikam Holdings LLC,12 Example Road Springfield\n"})[1]
        check("a CSV company list is read", imported.get("companies") == [{"name": FABRIKAM, "addresses": ["12 Example Road Springfield"]}],
              str(imported))
        check("the same company twice is refused", call("/api/companies", {"companies": [{"name": "A Co"}, {"name": "a co"}]})[0] == 400)
        check("the company list is saved (encrypted) and read back", call("/api/companies", imported)[0] == 200
              and call("/api/companies")[1] == imported and call("/api/state")[1]["companies_count"] == 1)
        check("settings are stored in the user's data folder, not in the app",
              os.path.exists(os.path.join(data_dir, ".env")) and os.path.exists(os.path.join(data_dir, "companies_reference.enc")),
              data_dir)
        if WINDOWS:
            call("/api/autostart", {"on": True})
            startup = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs",
                                   "Startup", "Drive Organizer.vbs")
            check("Start automatically writes a Startup entry for the installed program",
                  call("/api/state")[1]["autostart"] and os.path.basename(exe) in open(startup).read())
            call("/api/autostart", {"on": False})
            check("Start automatically can be turned off", not call("/api/state")[1]["autostart"] and not os.path.exists(startup))

        print("\n5. Renaming")
        check("a folder that doesn't exist is refused", call("/api/run", {"action": "rename_preview", "folder": scans + "-missing"})[0] == 400)
        call("/api/run", {"action": "rename_preview", "folder": scans})
        check("a second job is refused while one is running", call("/api/run", {"action": "rename_preview", "folder": scans})[0] == 400)
        call("/api/stop", {})
        stopped = wait_for_job(120)
        check("Stop ends the running job", stopped["code"] not in (0, "timed out"), str(stopped["code"]))

        model_requests.clear()
        models_used.clear()
        call("/api/run", {"action": "rename_preview", "folder": scans})
        job = wait_for_job()
        output = "\n".join(job["lines"])
        check("the rename preview finishes", job["code"] == 0, f"exit {job['code']}: {output[-600:]}")
        check("on-device OCR reads the letterhead and the sender is named",
              f"{FABRIKAM} - From Northwind Utilities.pdf" in output, output[-600:])
        check("the vision fallback names a sender the text didn't show",
              f"{FABRIKAM} - From Globex Insurance.pdf" in output, output[-600:])
        check("page images are sent only for the two letters that needed them", model_requests.count(True) == 2,
              f"{model_requests.count(True)} image requests of {len(model_requests)}")
        check("renaming uses the models chosen in Settings", models_used and set(models_used) <= {
              "drive-organizer-text:latest", "drive-organizer-vision:latest"}, str(sorted(set(models_used))))
        check("output with emoji arrives intact", "📄" in output or "✅" in output)
        check("a preview changes no files", sorted(os.listdir(scans)) == sorted(
            ["notes.txt", "scan05142026212549.pdf", "scan05142026212550.pdf", "scan05142026212551.pdf"]))

        call("/api/run", {"action": "rename_apply", "folder": scans})
        job = wait_for_job()
        files = sorted(os.listdir(scans))
        check("Apply renames the two matched letters and leaves the rest alone", job["code"] == 0 and files == sorted(
            [f"{FABRIKAM} - From Northwind Utilities.pdf", f"{FABRIKAM} - From Globex Insurance.pdf",
             "scan05142026212551.pdf", "notes.txt"]), f"exit {job['code']}: {files}")
        check("the scan folder is remembered", call("/api/state")[1]["scan_folder"].replace("\\", "/").rstrip("/")
              == scans.replace("\\", "/").rstrip("/"))

        print("\n6. Uploading without a Google sign-in")
        call("/api/run", {"action": "upload_preview", "folder": scans})
        job = wait_for_job(180)
        check("the upload preview stops with an error instead of hanging", job["code"] not in (0, "timed out"),
              f"exit {job['code']}: " + "\n".join(job["lines"])[-400:])

        print("\n7. Second start and Quit")
        second = subprocess.Popen([exe, "--no-open", "--port", str(port)], env=app_env)
        try:
            code = second.wait(timeout=60)
        except subprocess.TimeoutExpired:       # it took the port too: two copies are now running
            code = "kept running"
            second.kill()
        check("a second start notices the running app and steps aside", code == 0 and app.poll() is None, f"exit {code}")
        check("the running app kept its state after the second start", call("/api/state")[1]["companies_count"] == 1)
        call("/api/quit", {})
        try:
            app.wait(timeout=20)
            check("Quit stops the app", True)
        except subprocess.TimeoutExpired:
            check("Quit stops the app", False)
    finally:
        if app.poll() is None:
            app.kill()

    print(f"\n{'❌ ' + str(len(failures)) + ' check(s) failed: ' + '; '.join(failures) if failures else '✅ All checks passed'}\n")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
