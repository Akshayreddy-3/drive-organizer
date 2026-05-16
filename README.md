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

1. **Install Dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Google Cloud Credentials:**
   - Place your `credentials.json` in the project root.
   - The app will generate `token.json` after your first login.

## 🎬 How to Use

### 1. Run the Upload
This will scan your Desktop, group files, and upload them to matching folders in your Drive.
```bash
python3 run_upload.py
```

### 2. Preview First (Recommended)
See which files will be grouped and where they would go without uploading anything:
```bash
python3 run_upload.py --preview
```

### 3. Run Tests
Verify the code is working perfectly:
```bash
python3 run_tests.py
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

