# PyInstaller recipe for the packaged Drive Organizer app (Python and every library inside).
# Build on the system you are building for:  pyinstaller packaging/drive_organizer.spec --noconfirm
# Result: dist/Drive Organizer.app on a Mac, dist/Drive Organizer/ on Windows. See BUILD.md.
import os
import sys

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(SPECPATH)
MAC = sys.platform == "darwin"

# The app's pages; desktop_file_counter.py is looked up as a file by run_upload.py.
datas = [(os.path.join(ROOT, name), ".") for name in ("app.html", "tracker.html", "desktop_file_counter.py")]
# Scripts the app runs by name (ACTIONS in app.py), so PyInstaller can't see them being imported.
hidden = ["ai_pdf_renamer", "run_upload", "desktop_file_counter", "src.drive_client"]
binaries = []
for package in (["ocrmac"] if MAC else ["rapidocr", "onnxruntime"]):      # on-device OCR and its models
    d, b, h = collect_all(package)
    datas += d; binaries += b; hidden += h

a = Analysis([os.path.join(ROOT, "app.py")], pathex=[ROOT], datas=datas, binaries=binaries,
             hiddenimports=hidden, excludes=["tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts,
          [("u", None, "OPTION"),            # unbuffered output: the page shows progress line by line
           ("X utf8", None, "OPTION")],      # emoji in the output on any Windows code page
          exclude_binaries=True, name="Drive Organizer", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Drive Organizer")
if MAC:
    BUNDLE(coll, name="Drive Organizer.app", bundle_identifier="com.driveorganizer.app",
           info_plist={
               "CFBundleShortVersionString": "1.0",
               "LSUIElement": True,          # runs in the background: no Dock icon, the app is a browser page
               "NSDesktopFolderUsageDescription": "Drive Organizer reads the scanned files in the folder you choose.",
               "NSDocumentsFolderUsageDescription": "Drive Organizer reads the scanned files in the folder you choose.",
               "NSDownloadsFolderUsageDescription": "Drive Organizer reads the scanned files in the folder you choose.",
           })
