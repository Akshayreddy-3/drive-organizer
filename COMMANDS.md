# Project Commands Reference

This file contains the core commands for the Drive Organizer workflow.

## 1. AI PDF Renaming
Analyze PDFs using OCR and rename them to the `Company - From Sender` format.
*   **Dry Run (Preview only):**
    ```bash
    python3 ai_pdf_renamer.py --dry-run
    ```
*   **Actual Rename:**
    ```bash
    python3 ai_pdf_renamer.py
    ```

## 2. Matching Verification
Check if the files on your Desktop correctly match the folders in your Google Drive.
*   **Run Comparison:**
    ```bash
    python3 compare_scan.py
    ```

## 3. Uploading to Google Drive
Sync renamed files from your Desktop to the correct folders in Drive.
*   **Preview (Check folders/groups):**
    ```bash
    python3 run_upload.py --preview
    ```
*   **Actual Upload:**
    ```bash
    python3 run_upload.py
    ```

---

## Utility & Advanced Options

### AI PDF Renamer
*   **Help:** `python3 ai_pdf_renamer.py --help`
*   **Custom Batch Size:** `python3 ai_pdf_renamer.py --batch-size 3`
*   **Scan Specific Folder:** `python3 ai_pdf_renamer.py /path/to/folder`

### Drive Uploader
*   **Help:** `python3 run_upload.py --help`
*   **Scan Specific Folder:** `python3 run_upload.py --path /path/to/folder`
*   **Quiet Mode:** `python3 run_upload.py --quiet`
