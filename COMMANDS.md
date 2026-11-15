# Project Commands Reference

This file contains the core commands for the Drive Organizer workflow.

## 1. PDF Renaming (runs on this Mac)
Read scanned PDFs on-device and rename them to the `Company - From Sender` format.
Nothing leaves your Mac unless you add `--gemini-fallback`.

*   **One-time setup:**
    1. Install the Ollama app from https://ollama.com (the renamer starts it in the background when needed).
       No Ollama on this PC? Use your own cloud server instead — see `SERVER_SETUP.md` and skip step 2.
    2. Download the local model:
       ```bash
       ollama pull qwen3:4b
       ```
    3. Install packages: `pip install -r requirements.txt`
    4. Scan at 300 DPI or higher.

*   **Recommended Workflow:**
    1. **Preview & Cache:**
       ```bash
       python3 ai_pdf_renamer.py --dry-run
       ```
    2. **Apply from Cache (no re-analysis):**
       ```bash
       python3 ai_pdf_renamer.py --apply
       ```

*   **Direct Rename (1-step without preview):**
    ```bash
    python3 ai_pdf_renamer.py
    ```

*   **If no sender is found**, the file is named `Company - From UNKNOWN.pdf`.
    **If the company can't be confirmed**, the file keeps its original name and is listed at the
    end. Rename those by hand, or send just those files (plus the UNKNOWN-sender ones) to Gemini:
    ```bash
    python3 ai_pdf_renamer.py --gemini-fallback
    ```
    This uploads their page images and your company list to Google. Use a billing-enabled
    (paid) key — free-tier content may be used to train Google's models.

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
*   **Gemini fallback, several files per request:** `python3 ai_pdf_renamer.py --gemini-fallback --batch-size 3`
*   **Scan Specific Folder:** `python3 ai_pdf_renamer.py /path/to/folder`

### Drive Uploader
*   **Help:** `python3 run_upload.py --help`
*   **Scan Specific Folder:** `python3 run_upload.py --path /path/to/folder`
*   **Quiet Mode:** `python3 run_upload.py --quiet`


Update companies list in encrypted file
        ""---  python3 secure_companies.py decrypt ""
# make changes in companies_reference.json