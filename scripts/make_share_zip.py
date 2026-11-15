#!/usr/bin/env python3
"""
scripts/make_share_zip.py — build a copy of the app that is safe to give a coworker.

  python3 scripts/make_share_zip.py                      → dist/Drive-Organizer.zip
  python3 scripts/make_share_zip.py --with-credentials   also include credentials.json

The zip contains the app only. It never includes your settings or data: .env (keys),
token.json (your Google sign-in), your company list, upload history, or the rename cache.
Each coworker enters their own Drive link and company list in the app's Settings.

credentials.json identifies the Google Cloud app (not your account). Coworkers need it
to sign in, so pass --with-credentials if you're happy for them to use the same one.
"""

import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dist", "Drive-Organizer.zip")
SKIP_DIRS = ("scratch/", "dist/")


def main():
    # Everything git tracks or would track; .gitignore already keeps secrets and data out.
    listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    files = [f for f in listed if not f.startswith(SKIP_DIRS)]
    files.append("tracker.html")                     # the History page (ignored by git, holds no data)
    if "--with-credentials" in sys.argv:
        files.append("credentials.json")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if os.path.isfile(os.path.join(ROOT, f)):
                z.write(os.path.join(ROOT, f), os.path.join("Drive Organizer", f))
    print(f"✅ {len(files)} files → {OUT}")
    if "--with-credentials" not in sys.argv:
        print("   credentials.json not included — coworkers need one to sign in to Google "
              "(re-run with --with-credentials to include yours).")


if __name__ == "__main__":
    main()
