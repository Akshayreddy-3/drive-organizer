# Google Drive File Organizer v2

A modular, heavily-commented Python tool for automating file organization in Google Drive. Optimized for private/confidential data by using **existing Drive folders**.

## 🚀 Key Features

- 📁 **Target Existing Folders** - Files are matched to folders you've already created in Drive.
- 🧠 **Smart File Grouping** - Automatically groups files (e.g., `akshay123.pdf` → `akshay/` folder).
- 📅 **Month & Date Sorting** - Creates subfolders like `Feb/2026-02-03/` for perfect organization.
- 🧪 **45 Unit Tests** - Robust test suite verifying every component.
- 📖 **Educational Comments** - Every function is thoroughly documented for easy understanding.
- 🛡️ **Safe Uploads** - Includes preview mode and duplicate detection.

## 📂 Project Structure

```
drive_organizer/
├── src/                 # Heavily-commented source modules
│   ├── drive_client.py  # Google Drive API handling
│   ├── file_grouper.py  # Name extraction & grouping
│   ├── config.py        # All settings in one place
│   └── ...
├── tests/               # Unit tests (45 tests total)
├── run_upload.py        # Main entry point for uploading
└── run_tests.py         # Entry point for running tests
```

## 🛠️ Setup

### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Windows
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> **Note:** On Windows, use `python` instead of `python3` for all commands below.

2. **Google Cloud Credentials:**
   - Place your `credentials.json` in the project root.
   - The app will generate `token.json` after your first login.

## 🖥️ The App (easiest way)

Double-click **`Drive Organizer.command`** (Mac) or **`Drive Organizer.bat`** (Windows). The first
run installs everything the app needs, then it opens in your browser. It runs only on your computer.
Turn on **Start automatically** in Settings to keep it running in the background from sign-in on, so
`app.html` or `http://localhost:8686` always opens it; opening `app.html` while the app is stopped waits
and connects by itself once it starts.
On a computer that received the app as a download, the system blocks the launcher the first time —
`START HERE.txt` has the steps.

- **Run** — rename scanned PDFs and upload to Drive, each with a preview first.
- **History** — the upload dashboard.
- **Settings** — your Drive destination link, your company list and addresses, Google sign-in,
  and a setup check that says what is still missing.

To give the app to a coworker, run `python3 scripts/make_share_zip.py` and send them
`dist/Drive-Organizer.zip`. It leaves out your keys, Google sign-in, company list and history;
they enter their own Drive link and companies in Settings.

## 🎬 How to Use

### 1. Run the Upload
This will scan your Desktop, group files, and upload them to matching folders in your Drive.
```bash
# macOS / Linux
python3 run_upload.py

# Windows
python run_upload.py
```

### 2. Preview First (Recommended)
See which files will be grouped and where they would go without uploading anything:
```bash
# macOS / Linux
python3 run_upload.py --preview

# Windows
python run_upload.py --preview
```

### 3. Run Tests
Verify the code is working perfectly:
```bash
# macOS / Linux
python3 run_tests.py

# Windows
python run_tests.py
```

## 📊 Live Dashboard

Visualize your file organization in a premium, real-time dashboard.

1. **Launch the Server:**
   ```bash
   python3 dashboard_server.py
   ```
2. **Features:**
   - **Real-time Sync**: Dashboard updates automatically as you upload files.
   - **Persistent Verification**: Mark files as checked; status is saved to the server.
   - **Search & Filter**: Find files instantly by name or group.
   - **Folder Tree**: Explore your Drive's project hierarchy visually.
   - **Settings**: Monitor server health and quick-access CLI commands.

---

## ⚙️ Configuration
Edit `src/config.py` to change behavior:
- `DUPLICATE_HANDLING`: Set to `'skip'`, `'rename'`, or `'overwrite'`.
- `MONTH_FOLDER_FORMAT`: Change how months are named (e.g., `Jan` vs `January`).
- `DEFAULT_SCAN_PATH`: Scan a different folder instead of Desktop.

