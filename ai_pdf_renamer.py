#!/usr/bin/env python3
"""
ai_pdf_renamer.py - AI-Powered Scanned PDF Renamer (Gemini Edition)

  ⚡ SCALABLE: Batching + API Key Rotation

  Batching  — groups files (default 5) into a single API call → ~80% fewer requests
  Key Rotation — distributes requests across multiple API keys → no quota errors

REQUIREMENTS:
  pip install google-generativeai PyMuPDF Pillow python-dotenv

Get FREE Gemini API keys at: https://aistudio.google.com/apikey
Add them to .env:
  GEMINI_API_KEYS=key1,key2,key3        (preferred — multiple keys)
  GEMINI_API_KEY=single-key             (still works as fallback)

USAGE:
  python3 ai_pdf_renamer.py                           # Scans ~/Desktop
  python3 ai_pdf_renamer.py /path/to/folder
  python3 ai_pdf_renamer.py --dry-run
  python3 ai_pdf_renamer.py --batch-size 3            # Custom batch size
"""

import os, sys, json, re, argparse, time, io, warnings
from typing import Optional, List
warnings.filterwarnings("ignore")

try:
    import site
    _us = site.getusersitepackages()
    if _us and _us not in sys.path:
        sys.path.insert(0, _us)
except Exception:
    pass

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

try:
    import google.generativeai as genai
except ImportError:
    print("❌ Run: pip install google-generativeai"); sys.exit(1)

try:
    import fitz
except ImportError:
    print("❌ Run: pip install PyMuPDF"); sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("❌ Run: pip install Pillow"); sys.exit(1)

# ── Config ───────────────────────────────────────────────────────────────────
_SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
GEMINI_MODEL   = "gemini-2.5-flash"   # FREE tier, fast, supports vision
DEFAULT_BATCH_SIZE = 7                # fits 130 files into ~19 calls (under 20 limit)
IMAGE_DPI      = 200                  # higher DPI for better text legibility
MAX_IMAGE_DIM  = 1600                 # larger images for clearer address details
RPM_PER_KEY    = 10                   # Gemini free tier: 10 requests/min/key
MIN_REQUEST_GAP = 7                   # seconds between API calls (safe for 10 RPM)

# ── API Key Management ───────────────────────────────────────────────────────
class APIKeyManager:
    """Manages multiple Gemini API keys with round-robin rotation."""

    def __init__(self):
        self.keys = self._load_keys()
        self.current_index = 0
        self.exhausted_keys = set()   # track keys that hit quota

    def _load_keys(self) -> List[str]:
        """Load API keys from environment. Supports both single and multi-key."""
        # Prefer comma-separated list
        multi = os.getenv("GEMINI_API_KEYS", "").strip()
        if multi:
            keys = [k.strip() for k in multi.split(",") if k.strip()]
            if keys:
                return keys

        # Fall back to single key
        single = os.getenv("GEMINI_API_KEY", "").strip()
        if single:
            return [single]

        return []

    @property
    def count(self) -> int:
        return len(self.keys)

    @property
    def available_count(self) -> int:
        return len(self.keys) - len(self.exhausted_keys)

    def get_next_key(self) -> Optional[str]:
        """Get next available API key via round-robin. Returns None if all exhausted."""
        if not self.keys:
            return None

        # Try each key once before giving up
        for _ in range(len(self.keys)):
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)
            if key not in self.exhausted_keys:
                return key

        return None  # all keys exhausted

    def mark_exhausted(self, key: str):
        """Mark a key as quota-exhausted for this session."""
        self.exhausted_keys.add(key)
        remaining = self.available_count
        if remaining > 0:
            print(f"    🔑 Key exhausted — {remaining} key(s) still available")
        else:
            print("    🔑 All API keys exhausted!")

    def reset(self):
        """Reset exhausted status (e.g. for a new day)."""
        self.exhausted_keys.clear()


# ── Already-renamed detection ─────────────────────────────────────────────────
RENAMED_PATTERN = re.compile(r"^.+ - From .+\.pdf$", re.IGNORECASE)

def is_already_renamed(filename: str) -> bool:
    """Check if a file looks like it was already renamed by this tool."""
    return bool(RENAMED_PATTERN.match(filename))

# ── Smart RPM throttler ──────────────────────────────────────────────────────
class SmartThrottler:
    """Enforces RPM limits across API keys to avoid rate-limit errors."""

    def __init__(self, rpm_per_key: int, num_keys: int):
        self.rpm_per_key = rpm_per_key
        self.num_keys = max(num_keys, 1)
        self.effective_rpm = rpm_per_key * self.num_keys
        self.min_gap = max(60.0 / self.effective_rpm, MIN_REQUEST_GAP)
        self.last_request_time = 0.0

    def wait_if_needed(self):
        """Block until it's safe to make another request."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_gap:
            wait = self.min_gap - elapsed
            print(f"    ⏳ Throttling: waiting {wait:.0f}s (RPM limit)…")
            time.sleep(wait)
        self.last_request_time = time.time()

    def estimated_time(self, num_batches: int) -> float:
        """Estimate total processing time in seconds."""
        return num_batches * self.min_gap


def load_reference_list() -> dict:
    try:
        from secure_companies import load_encrypted_reference
        return load_encrypted_reference()
    except ImportError:
        # Fallback if secure_companies.py is not available
        ref_file = os.path.join(_SCRIPT_DIR, "companies_reference.json")
        if not os.path.exists(ref_file):
            print(f"⚠️  Reference file not found: {ref_file}")
            return {"companies": []}
        with open(ref_file) as f:
            return json.load(f)

# ── Prompt (single-file — used as fallback) ──────────────────────────────────
def build_prompt_single(ref: dict) -> str:
    lines = []
    for e in ref.get("companies", []):
        addrs = "; ".join(e.get("addresses", [])) or "No address on file"
        lines.append(f"  - {e.get('name','?')}  |  {addrs}")
    block = "\n".join(lines) or "  (none)"

    return f"""You are an expert at reading scanned physical mail.

KNOWN RECIPIENT COMPANIES:
{block}

Examine the attached scanned document.
- Letterheads / return addresses  → SENDER
- Mailing addresses matching list → RECIPIENT

Return ONLY valid JSON, no markdown, no explanation:
{{
  "company": "<recipient name>",
  "sender": "<sender name>",
  "is_known_company": true or false
}}

Rules:
- is_known_company = true only if recipient matches the list above. Allow for slight typos or spelling variations if the address is very similar.
- ALWAYS map the recipient to the EXACT company name from the KNOWN RECIPIENT COMPANIES list if it's a fuzzy match.
- Use "UNKNOWN" when you cannot determine a field.
- Keep names short: "IRS" not "Internal Revenue Service of the United States".
"""

# ── Prompt (batch — multiple files in one call) ──────────────────────────────
def build_prompt_batch(ref: dict, filenames: List[str]) -> str:
    lines = []
    for e in ref.get("companies", []):
        addrs = "; ".join(e.get("addresses", [])) or "No address on file"
        lines.append(f"  - {e.get('name','?')}  |  {addrs}")
    block = "\n".join(lines) or "  (none)"

    file_list = "\n".join(f"  Image {i+1}: \"{fn}\"" for i, fn in enumerate(filenames))

    return f"""You are an expert at reading scanned physical mail.
I am sending you {len(filenames)} scanned documents as images.

KNOWN RECIPIENT COMPANIES:
{block}

The images correspond to these files (in order):
{file_list}

IMPORTANT — FILENAME HINT:
The original filename often contains the recipient company name. Use it as a
STRONG HINT when identifying the recipient. For example, if the file is named
"acme corp05142026212549.pdf", the recipient is very likely
"Acme Corp". Always cross-check the filename hint against the
mailing address in the document and the KNOWN RECIPIENT COMPANIES list above.
If the filename hint matches a known company (even with a slight typo), prefer that match.

For EACH document:
- Letterheads / return addresses  → SENDER
- Mailing addresses matching list → RECIPIENT
- Original filename               → STRONG HINT for recipient identity

Return ONLY a valid JSON array with one object per document, no markdown, no explanation:
[
  {{
    "file_index": 1,
    "company": "<recipient name>",
    "sender": "<sender name>",
    "is_known_company": true or false
  }},
  ...
]

Rules:
- file_index starts at 1 and matches the image order above.
- is_known_company = true only if recipient matches the list above. Allow for slight typos or spelling variations if the address is very similar.
- ALWAYS map the recipient to the EXACT company name from the KNOWN RECIPIENT COMPANIES list if it's a fuzzy match.
- The filename is a STRONG HINT — if it clearly contains a company name from
  the known list, use that as the recipient. If there are minor spelling differences between the document/filename and the known list, but the address matches closely, STILL use the known company name from the list.
- Use "UNKNOWN" when you cannot determine a field.
- Keep names short: "IRS" not "Internal Revenue Service of the United States".
- You MUST return exactly {len(filenames)} objects in the array.
"""

# ── PDF → PIL Image (first 2 pages only) ─────────────────────────────────────
MAX_PAGES = 2   # company info is in the first 2–3 pages — no need for more

def pdf_to_image(pdf_path: str) -> Image.Image:
    """Convert the first MAX_PAGES pages of a PDF into a single stitched image.
    Optimized: lower DPI + dimension cap to reduce token usage."""
    doc = fitz.open(pdf_path)
    pages_to_read = min(len(doc), MAX_PAGES)
    page_images = []
    scale = IMAGE_DPI / 72

    for pg_num in range(pages_to_read):
        page = doc.load_page(pg_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        page_images.append(img)

    doc.close()

    if len(page_images) == 1:
        result = page_images[0]
    else:
        # Stitch pages vertically into one image
        total_width = max(im.width for im in page_images)
        total_height = sum(im.height for im in page_images)
        result = Image.new("RGB", (total_width, total_height), (255, 255, 255))
        y_offset = 0
        for im in page_images:
            result.paste(im, (0, y_offset))
            y_offset += im.height

    # Cap dimensions to reduce token usage
    if result.width > MAX_IMAGE_DIM or result.height > MAX_IMAGE_DIM:
        ratio = min(MAX_IMAGE_DIM / result.width, MAX_IMAGE_DIM / result.height)
        new_size = (int(result.width * ratio), int(result.height * ratio))
        result = result.resize(new_size, Image.LANCZOS)

    return result

# ── Batching helper ──────────────────────────────────────────────────────────
def chunk_files(files: list, size: int):
    """Yield successive chunks of `size` from `files`."""
    for i in range(0, len(files), size):
        yield files[i:i + size]

# ── Parse batch response ─────────────────────────────────────────────────────
def parse_batch_response(raw_text: str, expected_count: int) -> List[dict]:
    """Parse Gemini's batch JSON array response into a list of dicts."""
    raw = raw_text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)

    # If we got a single dict instead of a list, wrap it
    if isinstance(parsed, dict):
        parsed = [parsed]

    # Validate we got the right number
    if len(parsed) != expected_count:
        print(f"    ⚠️  Expected {expected_count} results, got {len(parsed)}")

    return parsed

# ── Gemini call — batch mode ─────────────────────────────────────────────────
RATE_LIMIT_RETRIES = 2   # retries on the SAME key before switching
RATE_LIMIT_WAIT    = 30  # seconds to wait on a 429 before retrying same key

def analyze_batch_with_gemini(
    images: List[Image.Image],
    prompt: str,
    key_manager: APIKeyManager,
) -> Optional[List[dict]]:
    """
    Send a batch of images in a single API call.
    - On 429/rate-limit: wait & retry on the SAME key up to RATE_LIMIT_RETRIES times
    - Only switch keys after repeated failures on the same key
    - Returns a list of result dicts, or None if all keys exhausted.
    """
    keys_attempted = 0

    while True:
        api_key = key_manager.get_next_key()
        if api_key is None:
            print("    🛑 All API keys exhausted — cannot continue.")
            return None

        key_label = f"…{api_key[-4:]}"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Try this key multiple times with backoff
        for retry in range(RATE_LIMIT_RETRIES + 1):
            try:
                content = [prompt] + images
                resp = model.generate_content(content)
                results = parse_batch_response(resp.text, len(images))
                return results

            except json.JSONDecodeError as e:
                print(f"    ⚠️  JSON parse error: {e}")
                print(f"    Raw response: {resp.text[:300]!r}")
                return [
                    {"company": "PARSE_ERROR", "sender": "PARSE_ERROR", "is_known_company": False}
                    for _ in images
                ]

            except Exception as e:
                err = str(e)
                is_quota = ("429" in err or "quota" in err.lower()
                            or "resource_exhausted" in err.lower())

                # "exceeded your current quota" = daily limit → switch key immediately
                is_daily_exhaustion = "exceeded" in err.lower()

                if is_quota and is_daily_exhaustion:
                    print(f"    ❌ Daily quota exhausted on key {key_label}")
                    key_manager.mark_exhausted(api_key)
                    break  # skip retries, go straight to next key

                elif is_quota:
                    # Temporary rate limit (RPM) → wait and retry same key
                    print(f"    ⚠️  Rate limit on key {key_label}: {err[:120]}")
                    if retry < RATE_LIMIT_RETRIES:
                        wait = RATE_LIMIT_WAIT * (retry + 1)
                        print(f"    ⏳ Waiting {wait}s then retrying same key…")
                        time.sleep(wait)
                        continue
                    else:
                        key_manager.mark_exhausted(api_key)
                        break  # move to next key

                else:
                    # Check for invalid/expired key → skip immediately
                    is_invalid_key = ("api_key_invalid" in err.lower()
                                      or "expired" in err.lower()
                                      or ("invalid" in err.lower() and "key" in err.lower()))

                    if is_invalid_key:
                        print(f"    ❌ Invalid/expired key {key_label} — skipping")
                        key_manager.mark_exhausted(api_key)
                        break  # move to next key

                    print(f"    ⚠️  Gemini error on key {key_label}: {err[:200]}")
                    if retry < RATE_LIMIT_RETRIES:
                        wait = 10 * (retry + 1)
                        print(f"    ⏳ Retrying in {wait}s…")
                        time.sleep(wait)
                        continue
                    return [
                        {"company": "ERROR", "sender": "ERROR", "is_known_company": False}
                        for _ in images
                    ]

        # Broke out of retry loop — key exhausted, try next key
        keys_attempted += 1
        if key_manager.available_count > 0:
            print(f"    🔄 Switching to next API key ({key_manager.available_count} remaining)…")
            continue
        else:
            print("    🛑 All API keys exhausted!")
            return None

# ── Rename ────────────────────────────────────────────────────────────────────
def sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", name).strip()

# Session-level tracker: counts how many times each (company, sender) pair
# has been used, so duplicates get " (1)", " (2)", … suffixes automatically.
class NameTracker:
    """Tracks used filenames within a session to append (1), (2), … for duplicates."""
    def __init__(self):
        self._counts = {}   # key: (company_lower, sender_lower) → count of times used

    def get_suffix(self, company: str, sender: str) -> str:
        """Return '' for the first occurrence, ' (1)' for the second, etc."""
        key = (company.lower(), sender.lower())
        count = self._counts.get(key, 0)
        self._counts[key] = count + 1
        if count == 0:
            return ""
        return f" ({count})"

def rename_pdf(path: str, company: str, sender: str, dry_run=False,
               name_tracker: 'NameTracker | None' = None) -> str:
    sc, ss   = sanitize(company), sanitize(sender)

    # Determine duplicate suffix from session tracker
    suffix = ""
    if name_tracker is not None:
        suffix = name_tracker.get_suffix(sc, ss)

    new_name = f"{sc} - From {ss}{suffix}.pdf"
    directory = os.path.dirname(path)
    new_path  = os.path.join(directory, new_name)

    # Extra safety: if file still exists on disk (e.g. from a previous run),
    # keep incrementing
    ctr = (int(suffix.strip(" ()")) + 1) if suffix else 1
    while os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(path):
        new_name = f"{sc} - From {ss} ({ctr}).pdf"
        new_path = os.path.join(directory, new_name)
        ctr += 1

    old_name = os.path.basename(path)
    if dry_run:
        print(f"    🔍 {old_name} → {new_name}")
    else:
        os.rename(path, new_path)
        print(f"    ✅ {old_name} → {new_name}")
    return new_name

# ── Summary ───────────────────────────────────────────────────────────────────
def print_summary(results: list, total_api_calls: int, total_keys_used: int):
    total   = len(results)
    matched = sum(1 for r in results if r["is_known_company"])
    errors  = sum(1 for r in results if r.get("error"))

    print("\n" + "="*70)
    print("  AI PDF RENAMER — SUMMARY")
    print("="*70)
    print(f"  Total: {total}  |  Matched: {matched}  |  Flagged: {total-matched-errors}  |  Errors: {errors}")
    print(f"  API Calls: {total_api_calls}  |  Keys Used: {total_keys_used}")
    print(f"  Efficiency: {total} files processed in {total_api_calls} request(s)")
    print("-"*70)

    for r in [x for x in results if x["is_known_company"] and not x.get("error")]:
        print(f"  ✅ {r['original_file']}\n     → {r['new_filename']}\n")

    for r in [x for x in results if not x["is_known_company"] and not x.get("error")]:
        print(f"  ⚠️  {r['original_file']}\n     → {r['new_filename']}")
        print(f"     company=\"{r['company']}\"  sender=\"{r['sender']}\"\n")

    for r in [x for x in results if x.get("error")]:
        print(f"  ❌ {r['original_file']}: {r['error']}\n")

    print("="*70)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AI PDF Renamer with Batching + Key Rotation")
    parser.add_argument("folder", nargs="?", default=None,
                        help="Folder to scan (default: ~/Desktop)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview renames without changing files")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Files per API call (default: {DEFAULT_BATCH_SIZE})")
    args = parser.parse_args()

    scan_folder = args.folder or os.path.expanduser("~/Desktop")
    if not os.path.isdir(scan_folder):
        print(f"❌ Folder not found: {scan_folder}"); sys.exit(1)

    # ── Initialize API key manager ──
    key_manager = APIKeyManager()
    if key_manager.count == 0:
        print("❌ No Gemini API keys found.")
        print("   Set GEMINI_API_KEYS=key1,key2,key3 in .env (comma-separated)")
        print("   Or set GEMINI_API_KEY=single-key")
        print("   Get FREE keys: https://aistudio.google.com/apikey")
        sys.exit(1)

    ref = load_reference_list()

    print("="*70)
    print("  AI PDF RENAMER — Scalable Processing")
    print("="*70)
    print(f"  📋 Companies loaded : {len(ref.get('companies',[]))}")
    print(f"  🤖 Model            : {GEMINI_MODEL}")
    print(f"  🔑 API Keys         : {key_manager.count}")
    print(f"  📦 Batch Size       : {args.batch_size} files/request")
    print("="*70 + "\n")

    # ── Discover PDFs ──
    all_pdfs = sorted(f for f in os.listdir(scan_folder)
                      if f.lower().endswith(".pdf") and "veritas" in f.lower() and not f.startswith("."))
    if not all_pdfs:
        print(f"📂 No PDFs found in: {scan_folder}"); sys.exit(0)

    # Skip files that are already renamed
    skipped = [f for f in all_pdfs if is_already_renamed(f)]
    pdfs = [f for f in all_pdfs if not is_already_renamed(f)]

    if not pdfs:
        print(f"📂 All {len(all_pdfs)} PDF(s) are already renamed — nothing to do.")
        sys.exit(0)

    # ── Smart Execution Plan ──
    num_batches = (len(pdfs) + args.batch_size - 1) // args.batch_size
    throttler = SmartThrottler(RPM_PER_KEY, key_manager.available_count)
    est_time = throttler.estimated_time(num_batches)

    print(f"\n{'─'*50}")
    print(f"  📊 EXECUTION PLAN")
    print(f"{'─'*50}")
    print(f"  📂 Folder           : {scan_folder}")
    print(f"  📄 Total PDFs found : {len(all_pdfs)}")
    if skipped:
        print(f"  ✅ Already renamed  : {len(skipped)} (skipped)")
    print(f"  📝 To process       : {len(pdfs)}")
    print(f"  📦 Batch size       : {args.batch_size} files/request")
    print(f"  📦 Total batches    : {num_batches}")
    print(f"  🔑 API Keys         : {key_manager.count}")
    print(f"  ⏱️  Est. time        : {est_time/60:.1f} min ({est_time:.0f}s)")
    print(f"{'─'*50}\n")

    if args.dry_run:
        print("🔍 DRY RUN — no files will be changed.\n")

    start_time = time.time()

    # ── Process batches ──
    results = []
    total_api_calls = 0
    keys_used = set()
    name_tracker = NameTracker()  # tracks duplicate company+sender across all batches

    for batch_num, batch_files in enumerate(chunk_files(pdfs, args.batch_size), 1):
        elapsed = time.time() - start_time
        if batch_num > 1:
            avg_per_batch = elapsed / (batch_num - 1)
            remaining = avg_per_batch * (num_batches - batch_num + 1)
            eta_str = f"  ~{remaining/60:.1f} min remaining"
        else:
            eta_str = ""
        print(f"{'─'*50}")
        print(f"  BATCH {batch_num}/{num_batches}  ({len(batch_files)} file(s)){eta_str}")
        print(f"{'─'*50}")

        # Convert all PDFs in this batch to images
        images = []
        valid_files = []  # track files that converted successfully
        batch_results_init = []

        for fn in batch_files:
            fp = os.path.join(scan_folder, fn)
            r = {"original_file": fn, "new_filename": None,
                 "company": None, "sender": None,
                 "is_known_company": False, "error": None}
            try:
                print(f"  📸 {fn}")
                img = pdf_to_image(fp)
                images.append(img)
                valid_files.append(fn)
            except Exception as e:
                r["error"] = f"Image conversion failed: {e}"
                print(f"    ❌ {e}")
            batch_results_init.append(r)

        if not images:
            print("  ⚠️  No valid images in batch — skipping API call")
            results.extend(batch_results_init)
            continue

        # Build batch prompt and call Gemini
        print(f"\n  🤖 Sending {len(images)} image(s) to Gemini… [{batch_num}/{num_batches}]")
        prompt = build_prompt_batch(ref, valid_files)
        current_key = key_manager.get_next_key()
        if current_key:
            keys_used.add(current_key)
            # Put it back — analyze_batch_with_gemini will pick it up
            key_manager.current_index = (key_manager.current_index - 1) % key_manager.count

        # Enforce RPM limit before calling API
        throttler.wait_if_needed()
        ai_results = analyze_batch_with_gemini(images, prompt, key_manager)
        total_api_calls += 1

        if ai_results is None:
            # All keys exhausted
            for r in batch_results_init:
                if r["error"] is None:
                    r["error"] = "All API keys exhausted"
            results.extend(batch_results_init)
            print("\n  🛑 Stopping — all API keys exhausted.")
            break

        # Map AI results back to files
        valid_idx = 0
        for r in batch_results_init:
            if r["error"] is not None:
                continue  # skip files that failed image conversion
            if valid_idx < len(ai_results):
                data = ai_results[valid_idx]
                r.update(
                    company=data.get("company", "UNKNOWN"),
                    sender=data.get("sender", "UNKNOWN"),
                    is_known_company=data.get("is_known_company", False),
                )
                fp = os.path.join(scan_folder, r["original_file"])
                try:
                    r["new_filename"] = rename_pdf(fp, r["company"], r["sender"], args.dry_run, name_tracker)
                except Exception as e:
                    r["error"] = f"Rename failed: {e}"
            else:
                r["error"] = "No AI result returned for this file"
            valid_idx += 1

        results.extend(batch_results_init)

        # Smart throttle is handled at the top of the next iteration

    print_summary(results, total_api_calls, len(keys_used) if keys_used else 1)

if __name__ == "__main__":
    main()