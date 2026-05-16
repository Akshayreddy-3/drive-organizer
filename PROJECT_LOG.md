# Drive Organizer - Project History & Logic

This document serves as a permanent record of the requirements and logic that built this project. You can refer to this anytime to understand the "why" and "how" behind the code.

---

## 📅 Initial Request & Workflow
The project started from a manual workflow diagram. The goal was to automate Google Drive uploads from the Desktop with specific folder logic:
1. **Search/Create Project Folder**
2. **Current Month Subfolder** (e.g., "Feb")
3. **Current Date Subfolder** (e.g., "2026-02-03")
4. **Duplicate Checking** (Compare filenames)
5. **Upload**

---

## 🚀 Iterative Improvements (v1)

### 1. Standardized Naming
- Changed month folders from numeric (e.g., `2026-02`) to short names (e.g., `Jan`, `Feb`, `Mar`) for better readability.

### 2. Fully Automatic Mode (`auto_upload.py`)
- Created a zero-interaction script that scans the Desktop and uploads everything instantly without asking for project names or confirmation.

### 3. Smart File Grouping
- **Requirement**: Files like `akshay123.pdf` and `akshay876.pdf` should go to the same `akshay/` folder.
- **Logic**: Built a "Base Name Extractor" using Regex to strip trailing numbers and dates.
- **Rules**:
  - `akshay12345` → `akshay`
  - `Screenshot 2024-01-15...` → `screenshots`
  - `IMG_20240115...` → `photos`

---

## 🏛️ Professional Refactor (v2)

Based on the need for **private/confidential data** handling and high modularity:

### 1. Existing Folder Only Mode
- Shifted from creating new project folders to **matching files against folders you've already created**.
- This ensures data only goes to authorized, pre-existing locations.

### 2. Modular Architecture
- Split the code into specialized source files (`src/`) and test files (`tests/`).
- **`drive_client.py`**: Handles low-level Google API & OAuth.
- **`file_scanner.py`**: Scans and filters local files.
- **`file_grouper.py`**: Performs the smart naming logic.
- **`folder_navigator.py`**: Handles Drive hierarchy (existing folder → Month → Date).
- **`uploader.py`**: Manages safe binary uploads and duplicate detection.

### 3. Comprehensive Testing
- Added **45 unit tests** to verify that grouping, scanning, and navigation work perfectly on every run.

### 4. Educational Documentation
- Every function includes a detailed "Docstring" explaining its Purpose, Arguments, and Returns, along with inline comments for every line of logic.

---

## 🛠️ How to Maintain
- **To change grouping logic**: Edit `src/file_grouper.py`.
- **To change folder formats**: Edit `src/config.py`.
- **To update Drive permissions**: Edit `src/drive_client.py`.

---

*This document was generated as a summary of the collaborative session between Akshay Reddy and Antigravity (AI assistant) on February 3, 2026.*
