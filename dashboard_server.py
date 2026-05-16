#!/usr/bin/env python3
"""
dashboard_server.py — Live Dashboard Server for Drive Organizer

Starts a local web server to serve the tracker dashboard with real-time
data from tracker_data.json. Provides REST API endpoints for file
verification that persist to disk.

USAGE:
    python dashboard_server.py                  # Start on port 8686
    python dashboard_server.py --port 9000      # Custom port
    python dashboard_server.py --no-open        # Don't open browser

Author: Drive Organizer
"""

import argparse
import json
import os
import sys
import webbrowser
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add project root to path so we can import DataTracker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The path to tracker_data.json (same directory as this script)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(PROJECT_DIR, "tracker_data.json")


def load_tracker_data():
    """Load the tracker data JSON file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "total_files": 0,
        "total_groups": 0,
        "last_upload": None,
        "groups": {},
        "history": [],
        "folder_tree": {},
        "verified_files": {},
        "all_files": [],
    }


def save_tracker_data(data):
    """Save data to the tracker JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


class DashboardHandler(SimpleHTTPRequestHandler):
    """
    Custom HTTP handler that serves static files and provides
    REST API endpoints for the dashboard.
    """

    def __init__(self, *args, **kwargs):
        # Serve files from the project directory
        super().__init__(*args, directory=PROJECT_DIR, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Root → serve tracker.html
        if path == "/":
            self.path = "/tracker.html"
            return super().do_GET()

        # API: Get tracker data
        if path == "/api/data":
            data = load_tracker_data()
            self._send_json(data)
            return

        # API: Server status / health check
        if path == "/api/status":
            self._send_json({
                "status": "online",
                "data_file": DATA_FILE,
                "data_exists": os.path.exists(DATA_FILE),
            })
            return

        # Everything else: serve as static file
        return super().do_GET()

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # API: Toggle file verification
        if path == "/api/verify":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode("utf-8"))

                key = payload.get("key", "")
                verified = payload.get("verified", False)

                if not key:
                    self._send_json({"error": "Missing 'key' field"}, status=400)
                    return

                # Load, update, save
                data = load_tracker_data()
                if "verified_files" not in data:
                    data["verified_files"] = {}

                if verified:
                    data["verified_files"][key] = True
                else:
                    data["verified_files"].pop(key, None)

                save_tracker_data(data)

                self._send_json({
                    "success": True,
                    "key": key,
                    "verified": verified,
                    "total_verified": len(data["verified_files"]),
                })
            except (json.JSONDecodeError, ValueError) as e:
                self._send_json({"error": f"Invalid request: {str(e)}"}, status=400)
            except Exception as e:
                self._send_json({"error": f"Server error: {str(e)}"}, status=500)
            return

        # API: Bulk verify (for syncing localStorage → server)
        if path == "/api/verify/sync":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode("utf-8"))

                verified_files = payload.get("verified_files", {})

                data = load_tracker_data()
                if "verified_files" not in data:
                    data["verified_files"] = {}

                # Merge: client-side verified files into server data
                data["verified_files"].update(verified_files)

                # Remove entries that are False
                data["verified_files"] = {
                    k: v for k, v in data["verified_files"].items() if v
                }

                save_tracker_data(data)

                self._send_json({
                    "success": True,
                    "total_verified": len(data["verified_files"]),
                })
            except Exception as e:
                self._send_json({"error": f"Server error: {str(e)}"}, status=500)
            return

        self._send_json({"error": "Not found"}, status=404)

    def _send_json(self, data, status=200):
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def end_headers(self):
        """Add CORS headers to all responses."""
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        """Custom log formatting."""
        # Color-code by status
        status = args[1] if len(args) > 1 else ""
        method_path = args[0] if args else ""

        if "200" in str(status) or "204" in str(status):
            indicator = "✓"
        elif "304" in str(status):
            indicator = "→"
        elif "404" in str(status):
            indicator = "✗"
        else:
            indicator = "●"

        print(f"  {indicator}  {method_path}")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Drive Organizer — Dashboard Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port", type=int, default=8686, help="Port to run the server on (default: 8686)"
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't automatically open the browser",
    )
    return parser.parse_args()


def main():
    """Start the dashboard server."""
    args = parse_args()
    port = args.port

    # Check if data file exists
    data_exists = os.path.exists(DATA_FILE)

    # Print startup banner
    print()
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║                                                  ║")
    print("  ║   ⚡  Drive Organizer — Dashboard Server         ║")
    print("  ║                                                  ║")
    print("  ╠══════════════════════════════════════════════════╣")
    print(f"  ║                                                  ║")
    url_str = f"http://localhost:{port}"
    print(f"  ║   🌐  {url_str:<39s}  ║")
    print(f"  ║                                                  ║")
    print(f"  ║   📁  Data: {'Found ✓' if data_exists else 'Not found ✗':<33s} ║")
    print(f"  ║   📄  File: tracker_data.json{' ' * 19}  ║")
    print(f"  ║                                                  ║")
    print("  ║   Press Ctrl+C to stop                           ║")
    print("  ║                                                  ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print()

    if not data_exists:
        print("  ⚠  No tracker_data.json found.")
        print("     Run 'python run_upload.py' first to generate data,")
        print("     or the dashboard will show empty state.")
        print()

    # Print API info
    print("  API Endpoints:")
    print(f"    GET  http://localhost:{port}/api/data    → Tracker data")
    print(f"    GET  http://localhost:{port}/api/status  → Server status")
    print(f"    POST http://localhost:{port}/api/verify  → Toggle verification")
    print()
    print("  ─────────────────────────────────────────────────")
    print("  Request Log:")
    print()

    # Create the server
    server = HTTPServer(("", port), DashboardHandler)

    # Auto-open browser (in a separate thread to not block)
    if not args.no_open:
        url = f"http://localhost:{port}"
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    # Run the server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  👋  Server stopped. Goodbye!\n")
        server.server_close()


if __name__ == "__main__":
    main()
