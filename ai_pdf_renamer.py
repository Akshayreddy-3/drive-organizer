#!/usr/bin/env python3
"""
ai_pdf_renamer.py - Scanned PDF Renamer (local-first, optional Gemini fallback)

  🔒 LOCAL BY DEFAULT: nothing leaves this computer
    OCR       — on-device (Apple Vision on Mac, RapidOCR on Windows), pages rendered at 300 DPI
    Recipient — matched in code against your company list (filename prefix + letter text)
    Sender    — small local model via Ollama; kept only if its quote is really in the letter

  No sender found → "Company - From UNKNOWN.pdf". No confirmed company → file left
  untouched and listed. --gemini-fallback sends ONLY those files (and the UNKNOWN-sender
  ones) to Google Gemini (page images + your company list) — use a paid-tier key.

REQUIREMENTS:
  pip install -r requirements.txt   (ocrmac on Mac; rapidocr + onnxruntime on Windows)
  Ollama app (https://ollama.com), then: ollama pull qwen3:4b
    — or no Ollama here: set OLLAMA_URL in .env to your own server (see SERVER_SETUP.md)
  For --gemini-fallback only: pip install google-genai, and in .env
    GEMINI_API_KEYS=key1,key2,key3  or  GEMINI_API_KEY=single-key

USAGE:
  python3 ai_pdf_renamer.py                           # Scans ~/Desktop & renames directly
  python3 ai_pdf_renamer.py --dry-run                 # Preview & save results to cache
  python3 ai_pdf_renamer.py --apply                   # Apply cached renames (no analysis)
  python3 ai_pdf_renamer.py /path/to/folder
  python3 ai_pdf_renamer.py --gemini-fallback         # Send unresolved files to Gemini
"""

import os, sys, json, re, argparse, time, io, warnings, logging, urllib.request, shutil, subprocess
from typing import Optional, List
warnings.filterwarnings("ignore")

# Cross-platform helpers (Desktop path + emoji encoding)
try:
    from utils.platform import get_desktop_path, setup_encoding
    setup_encoding()
except ImportError:
    # Fallback if utils package isn't available
    from pathlib import Path
    def get_desktop_path(): return Path.home() / "Desktop"
    def setup_encoding(): pass

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
    logging.getLogger("google_genai").setLevel(logging.ERROR)
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)
    logging.getLogger("google.genai").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")
    from google import genai
    from google.genai import types
except ImportError:
    genai = None   # only needed for --gemini-fallback

try:
    import fitz
except ImportError:
    print("❌ Run: pip install PyMuPDF"); sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("❌ Run: pip install Pillow"); sys.exit(1)

if sys.platform == "darwin":
    try:
        from ocrmac import ocrmac
    except ImportError:
        print("❌ Run: pip install ocrmac   (macOS only)"); sys.exit(1)
else:                                   # Windows / Linux: RapidOCR, also fully on-device
    ocrmac = None
    try:
        import numpy
        from rapidocr import RapidOCR
    except ImportError:
        print("❌ Run: pip install rapidocr onnxruntime"); sys.exit(1)

try:
    from rapidfuzz import fuzz, process
except ImportError:
    print("❌ Run: pip install rapidfuzz"); sys.exit(1)

from offline_renamer import normalize   # lowercase, alphanumerics only, trailing "inc" dropped

# ── Config ───────────────────────────────────────────────────────────────────
_SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
LOCAL_MODEL    = "qwen3:4b"                # Ollama model for the sender (runs on this Mac)
OLLAMA_URL     = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")   # set in .env to use a remote server
GEMINI_MODEL   = "gemini-3.8-flash"        # used only with --gemini-fallback
DEFAULT_BATCH_SIZE = 1                # Gemini fallback: one file per request, so answers can't shift between files
IMAGE_DPI      = 300                  # standard OCR resolution; letter page → 2550×3300 px
RPM_PER_KEY    = 10                   # Gemini free tier: 10 requests/min/key
MIN_REQUEST_GAP = 2                   # floor gap; throttler auto-adjusts for key count
CACHE_FILE     = os.path.join(_SCRIPT_DIR, ".ai_rename_cache.json")

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
def build_prompt_batch(ref: dict, filenames: List[str], page_counts: List[int]) -> str:
    lines = []
    for e in ref.get("companies", []):
        addrs = "; ".join(e.get("addresses", [])) or "No address on file"
        lines.append(f"  - {e.get('name','?')}  |  {addrs}")
    block = "\n".join(lines) or "  (none)"

    file_lines, first = [], 1
    for i, (fn, pages) in enumerate(zip(filenames, page_counts)):
        imgs = f"image {first}" if pages == 1 else f"images {first}-{first + pages - 1}"
        file_lines.append(f"  File {i+1}: \"{fn}\"  ({imgs})")
        first += pages
    file_list = "\n".join(file_lines)

    return f"""You are an expert at reading scanned physical mail.
I am sending you {len(filenames)} scanned documents; each page is a separate image.

KNOWN RECIPIENT COMPANIES:
{block}

The images belong to these files (in order):
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
- file_index starts at 1 and matches the file order above (not the image number).
- is_known_company = true only if recipient matches the list above. Allow for slight typos or spelling variations if the address is very similar.
- ALWAYS map the recipient to the EXACT company name from the KNOWN RECIPIENT COMPANIES list if it's a fuzzy match.
- The filename is a STRONG HINT — if it clearly contains a company name from
  the known list, use that as the recipient. If there are minor spelling differences between the document/filename and the known list, but the address matches closely, STILL use the known company name from the list.
- Use "UNKNOWN" when you cannot determine a field.
- Keep names short: "IRS" not "Internal Revenue Service of the United States".
- You MUST return exactly {len(filenames)} objects in the array.
"""

# ── PDF → PIL Images (first 2 pages only) ────────────────────────────────────
MAX_PAGES = 2   # company info is in the first 2–3 pages — no need for more

def pdf_to_images(pdf_path: str) -> List[Image.Image]:
    """Render the first MAX_PAGES pages separately at IMAGE_DPI — no stitching or
    downscaling, so small print stays readable (no guessing from blurry pixels)."""
    doc = fitz.open(pdf_path)
    scale = IMAGE_DPI / 72
    page_images = []
    for pg_num in range(min(len(doc), MAX_PAGES)):
        pix = doc.load_page(pg_num).get_pixmap(matrix=fitz.Matrix(scale, scale))
        page_images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    doc.close()
    return page_images

# ── Local analysis (on this Mac) ─────────────────────────────────────────────
TIMESTAMP_RE   = re.compile(r"^(.*?)(\d{14})\.pdf$", re.IGNORECASE)  # same as offline_renamer.py
MIN_HINT_LEN   = 3     # typed filename prefixes are short ("acme"); 1–2 letters say too little
HINT_CUTOFF    = 85    # filename typo vs a full company name (fuzz.ratio)
MIN_NAME_LEN   = 5     # shorter names match too easily inside other words
TEXT_CUTOFF    = 90    # company name inside the letter text (fuzz.partial_ratio)
ADDRESS_WINDOW = 6     # an address's numbers must sit within this many consecutive OCR lines
QUOTE_CUTOFF   = 90    # sender quote inside the letter text (fuzz.partial_ratio)
MAX_OCR_CHARS  = 12000 # ~3,400 tokens: a whole letter still fits the 4,096-token context
SENDER_LINES   = 30    # the model sees only the top lines, where the sender's name is printed

_rapid_engine = None   # RapidOCR loads its models once, on first use

def ocr_page(img) -> List[str]:
    """Text lines of one page image, top-to-bottom, read on this computer:
    Apple Vision on a Mac, RapidOCR (models bundled in the package) elsewhere."""
    if ocrmac is not None:
        return [text for text, _conf, _bbox in
                ocrmac.OCR(img, recognition_level="accurate", language_preference=["en-US"]).recognize()]
    global _rapid_engine
    if _rapid_engine is None:
        _rapid_engine = RapidOCR(params={"Global.log_level": "warning"})   # no startup chatter
    return list(_rapid_engine(numpy.array(img)).txts or ())

def ocr_pdf(pdf_path: str) -> str:
    """On-device OCR of the first pages; lines come back top-to-bottom."""
    lines = []
    for img in pdf_to_images(pdf_path):
        lines.extend(ocr_page(img))
    return "\n".join(lines)

def name_index(companies: list) -> dict:
    """normalized name → company name; None when two different companies normalize alike."""
    names = {}
    for c in companies:
        n = normalize(c.get("name", ""))
        if n:
            names[n] = c["name"] if names.get(n, c["name"]) == c["name"] else None
    return names

def match_hint(filename: str, names: dict):
    """(company, how) from the scanner filename, e.g. 'acme05142026212549.pdf'."""
    m = TIMESTAMP_RE.match(filename)
    hint = normalize(m.group(1) if m else os.path.splitext(filename)[0])
    if len(hint) < MIN_HINT_LEN:
        return None, None
    if hint in names:
        return names[hint], "hint-exact"
    owners = [n for n in names if n.startswith(hint)]
    if len(owners) == 1:                                  # operators type a short prefix
        return names[owners[0]], "hint-prefix"
    close = process.extract(hint, names.keys(), scorer=fuzz.ratio, score_cutoff=HINT_CUTOFF, limit=2)
    if not owners and len(close) == 1:                    # unambiguous typo of a full name
        return names[close[0][0]], "hint-fuzzy"
    return None, None

def match_name_in_text(text: str, names: dict):
    norm_text = normalize(text)
    found = [n for n in names
             if len(n) >= MIN_NAME_LEN and fuzz.partial_ratio(n, norm_text) >= TEXT_CUTOFF]
    found = [n for n in found if not any(n != o and n in o for o in found)]  # "acmecorp" ⊂ "acmecorporation"
    return (names[found[0]], "name-in-text") if len(found) == 1 else (None, None)

def match_address_in_text(text: str, companies: list):
    """An address counts only if it belongs to exactly one company and all its numbers
    (street no., suite, ZIP) appear together in one block of lines — robust to 'Street'/'St'
    and OCR letter errors, but not fooled by numbers scattered across the letter."""
    owners = {}
    for c in companies:
        for addr in c.get("addresses", []):
            nums = frozenset(re.findall(r"\d+", addr))
            if any(len(n) == 5 for n in nums):            # needs a ZIP to be specific enough
                owners.setdefault(nums, set()).add(c["name"])
    line_nums = [set(re.findall(r"\d+", line)) for line in text.splitlines()]
    windows = [set().union(*line_nums[i:i + ADDRESS_WINDOW]) for i in range(max(len(line_nums), 1))]
    hits = {next(iter(o)) for nums, o in owners.items()
            if len(o) == 1 and any(nums <= w for w in windows)}
    return (hits.pop(), "address") if len(hits) == 1 else (None, None)

def match_company(filename: str, text: str, companies: list):
    """Recipient from the known list only, never guessed. Returns (company, how);
    company is None when there's no evidence or the filename and letter disagree."""
    names = name_index(companies)
    hint, hint_how = match_hint(filename, names)
    found, text_how = match_name_in_text(text, names)
    if not found:
        found, text_how = match_address_in_text(text, companies)
    if hint and found and hint != found:
        return None, "conflict"
    if hint and found:
        return hint, f"{hint_how}+{text_how}"
    return (hint, hint_how) if hint else (found, text_how)

SENDER_SCHEMA = {
    "type": "object",
    "properties": {"sender_as_printed": {"type": "string"}, "sender": {"type": "string"}},
    "required": ["sender_as_printed", "sender"],
}

SENDER_PROMPT = """You are reading OCR text from a scanned piece of physical mail.
Identify the SENDER: the organization or person the mail is FROM (letterhead, return address,
or signature block). The mailing address block (the recipient) is NOT the sender.

This mail is addressed TO "{recipient}". That company is the RECIPIENT and is never the
sender, even if its name appears at the top of the page or in an account header.
The sender is a different organization or person.

Return JSON with:
- "sender_as_printed": the sender's name copied EXACTLY as it appears in the text (no corrections)
- "sender": a short common name, e.g. "IRS" not "Internal Revenue Service of the United States"
Use "UNKNOWN" for both if the sender is not clearly stated in the text.

OCR TEXT:
"""

def same_org(a: str, b: str) -> bool:
    """True when two names look like the same organization (tolerates OCR noise like 'DES ACME INC')."""
    a, b = normalize(a), normalize(b)
    if min(len(a), len(b)) < MIN_NAME_LEN:
        return a == b
    return fuzz.partial_ratio(a, b) >= TEXT_CUTOFF

def grounded_sender(data: dict, text: str, recipient: str) -> str:
    """Keep the model's sender only if its verbatim quote really appears in the letter
    and it isn't the recipient itself."""
    sender = (data.get("sender") or "").strip()
    quote_raw = (data.get("sender_as_printed") or "").strip()
    quote = normalize(quote_raw)
    if not sender or sender.lower() in ("unknown", "n/a", "none") or not quote:
        return "UNKNOWN"
    if same_org(sender, recipient) or same_org(quote_raw, recipient):
        return "UNKNOWN"
    if len(quote) >= 6:
        found = fuzz.partial_ratio(quote, normalize(text)) >= QUOTE_CUTOFF
    else:                                                  # short quotes: whole-word match only
        found = re.search(rf"\b{re.escape(quote_raw)}\b", text, re.IGNORECASE) is not None
    return sender if found else "UNKNOWN"

def hide_recipient(text: str, recipient: str) -> str:
    """Replace every OCR line naming the recipient; a small model otherwise picks it as the sender."""
    return "\n".join("[RECIPIENT]" if same_org(line, recipient) else line for line in text.splitlines())

def extract_sender(text: str, recipient: str, model: str = LOCAL_MODEL) -> str:
    """Ask the local Ollama model for the sender with the recipient's lines hidden:
    first the top of the letter (letterhead/return address), then the whole letter."""
    hidden = hide_recipient(text, recipient)
    top = "\n".join(hidden.splitlines()[:SENDER_LINES])
    for visible in ([top] if top == hidden else [top, hidden]):
        body = {
            "model": model, "stream": False, "think": False, "format": SENDER_SCHEMA,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 200},   # short answer, no runaway
            "messages": [{"role": "user",
                          "content": SENDER_PROMPT.format(recipient=recipient) + visible[:MAX_OCR_CHARS]}],
        }
        req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:   # slow CPU-only servers need minutes for a full letter
            data = json.loads(json.loads(resp.read())["message"]["content"])
        sender = grounded_sender(data, text, recipient)
        if sender != "UNKNOWN":
            return sender
    return "UNKNOWN"

def ollama_models() -> Optional[set]:
    """Names of downloaded models, or None if the Ollama server isn't reachable."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as resp:
            return {m["name"] for m in json.loads(resp.read()).get("models", [])}
    except Exception:
        return None

def check_ollama(model: str):
    """Start the local Ollama server in the background if needed (no app window),
    then exit with setup steps unless it's running with the model."""
    names = ollama_models()
    local = re.match(r"https?://(localhost|127\.0\.0\.1)(:|/|$)", OLLAMA_URL) is not None
    exe = shutil.which("ollama")
    if names is None and local and exe:
        print("⏳ Starting Ollama in the background...")
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)   # keeps running after this script ends
        for _ in range(30):
            time.sleep(1)
            names = ollama_models()
            if names is not None:
                break
    if names is None and not local:
        print(f"❌ Can't reach the Ollama server at {OLLAMA_URL}. Is the server on, and is Tailscale connected?")
        sys.exit(1)
    if names is None:
        print("❌ Ollama isn't running. Open the Ollama app (install from https://ollama.com).")
        sys.exit(1)
    if model not in names and f"{model}:latest" not in names:
        print(f"❌ Local model '{model}' isn't downloaded. Run: ollama pull {model}")
        sys.exit(1)

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
RATE_LIMIT_WAIT    = 15  # seconds to wait on a 429 before retrying same key

FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]

def analyze_batch_with_gemini(
    parts: list,
    num_files: int,
    prompt: str,
    key_manager: APIKeyManager,
    model: str = GEMINI_MODEL,
) -> Optional[List[dict]]:
    """
    Send a batch of files (one JPEG part per page) in a single API call.
    - On 429/rate-limit: wait & retry on the SAME key up to RATE_LIMIT_RETRIES times
    - On 503/unavailable: retry with backoff or fallback model
    - On 404/not found: switch to fallback model immediately
    - Only switch keys after repeated failures on the same key
    - Returns a list of result dicts, or None if all keys exhausted.
    """
    keys_attempted = 0
    candidate_models = [model] + [m for m in FALLBACK_MODELS if m != model]

    while True:
        api_key = key_manager.get_next_key()
        if api_key is None:
            print("    🛑 All API keys exhausted — cannot continue.")
            return None

        key_label = f"…{api_key[-4:]}"
        client = genai.Client(api_key=api_key)
        key_exhausted = False

        for current_model in candidate_models:
            if key_exhausted:
                break

            # Try this model with backoff
            for retry in range(RATE_LIMIT_RETRIES + 1):
                try:
                    content = [prompt] + parts
                    resp = client.models.generate_content(
                        model=current_model,
                        contents=content,
                    )
                    results = parse_batch_response(resp.text, num_files)
                    return results

                except json.JSONDecodeError as e:
                    print(f"    ⚠️  JSON parse error: {e}")
                    raw_text = resp.text[:300] if resp else "(no response)"
                    print(f"    Raw response: {raw_text!r}")
                    return [
                        {"company": "PARSE_ERROR", "sender": "PARSE_ERROR", "is_known_company": False}
                        for _ in range(num_files)
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
                        key_exhausted = True
                        break  # skip to next key

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
                            key_exhausted = True
                            break  # move to next key

                    is_unavailable = "503" in err or "unavailable" in err.lower()
                    if is_unavailable:
                        print(f"    ⚠️  Model {current_model} unavailable (503/high demand).")
                        if retry < RATE_LIMIT_RETRIES and current_model == candidate_models[-1]:
                            wait = 5 * (retry + 1)
                            print(f"    ⏳ Retrying in {wait}s…")
                            time.sleep(wait)
                            continue
                        elif current_model != candidate_models[-1]:
                            print(f"    🔄 Trying fallback model…")
                            break  # break inner retry loop to try next model in candidate_models

                    # Check for retired or not found model (404)
                    is_not_found = ("404" in err or "not found" in err.lower()
                                    or "no longer available" in err.lower())
                    if is_not_found:
                        print(f"    ⚠️  Model {current_model} not found or retired. Trying next model…")
                        break  # switch immediately to next candidate model

                    # Check for invalid/expired key → skip immediately
                    is_invalid_key = ("api_key_invalid" in err.lower()
                                      or "expired" in err.lower()
                                      or ("invalid" in err.lower() and "key" in err.lower()))

                    if is_invalid_key:
                        print(f"    ❌ Invalid/expired key {key_label} — skipping")
                        key_manager.mark_exhausted(api_key)
                        key_exhausted = True
                        break  # move to next key

                    print(f"    ⚠️  Gemini error on key {key_label} ({current_model}): {err[:200]}")
                    if retry < RATE_LIMIT_RETRIES:
                        wait = 5 * (retry + 1)
                        print(f"    ⏳ Retrying in {wait}s…")
                        time.sleep(wait)
                        continue
                    # Retries exhausted on this model, continue to next candidate_model

        # Broke out of retry loop — key exhausted or failed, try next key
        keys_attempted += 1
        if keys_attempted >= key_manager.count:
            # every key has had a turn; a persistent non-quota error would otherwise retry forever
            print("    🛑 Every API key failed for this request — giving up.")
            return None
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
    sc, ss   = sanitize(company), sanitize(sender).rstrip(".")   # "Inc." + ".pdf" ≠ "Inc..pdf"

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
    matched = sum(1 for r in results if r["is_known_company"] and not r.get("error"))
    errors  = sum(1 for r in results if r.get("error"))

    print("\n" + "="*70)
    print("  AI PDF RENAMER — SUMMARY")
    print("="*70)
    print(f"  Total: {total}  |  Matched: {matched}  |  Flagged: {total-matched-errors}  |  Not renamed: {errors}")
    if total_api_calls:
        print(f"  Gemini API Calls: {total_api_calls}  |  Keys Used: {total_keys_used}")
    print("-"*70)

    for r in [x for x in results if x["is_known_company"] and not x.get("error")]:
        print(f"  ✅ {r['original_file']}\n     → {r['new_filename']}\n")

    for r in [x for x in results if not x["is_known_company"] and not x.get("error")]:
        print(f"  ⚠️  {r['original_file']}\n     → {r['new_filename']}")
        print(f"     company=\"{r['company']}\"  sender=\"{r['sender']}\"\n")

    for r in [x for x in results if x.get("error")]:
        print(f"  ❌ {r['original_file']}: {r['error']}\n")

    print("="*70)

# ── Cache Management ──────────────────────────────────────────────────────────
def save_rename_cache(folder: str, results: list):
    """Save dry-run analysis results to disk for fast application."""
    valid_results = [r for r in results if not r.get("error") and r.get("company")]
    if not valid_results:
        return

    cache_data = {
        "timestamp": time.time(),
        "folder": os.path.abspath(folder),
        "results": results
    }
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
        print("\n" + "─"*70)
        print("  💾 DRY-RUN RESULTS CACHED!")
        print("  Run the following command to apply renames WITHOUT calling AI again:")
        print("    python3 ai_pdf_renamer.py --apply")
        print("─"*70 + "\n")
    except Exception as e:
        print(f"⚠️  Failed to save cache: {e}")

def apply_cached_renames(scan_folder: str):
    """Apply renames using previously saved dry-run cache without calling Gemini."""
    if not os.path.exists(CACHE_FILE):
        print(f"❌ No dry-run cache found at: {CACHE_FILE}")
        print("   Please run a dry run first:")
        print("     python3 ai_pdf_renamer.py --dry-run")
        sys.exit(1)

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading cache file: {e}")
        sys.exit(1)

    cached_folder = cache_data.get("folder", "")
    current_scan = os.path.abspath(scan_folder)
    if cached_folder and cached_folder != current_scan:
        print(f"⚠️  Note: Cache was generated for folder: {cached_folder}")
        print(f"   Target folder: {current_scan}")

    cache_time = cache_data.get("timestamp", 0)
    age_hours = (time.time() - cache_time) / 3600
    if age_hours > 24:
        print(f"⚠️  Warning: Cache is {age_hours:.1f} hours old. Consider running --dry-run again if files changed.\n")

    cached_results = cache_data.get("results", [])
    if not cached_results:
        print("❌ Cache contains no results to apply.")
        sys.exit(0)

    print("="*70)
    print("  AI PDF RENAMER — Applying Cached Results (0 API Calls)")
    print("="*70)
    print(f"  📂 Target Folder  : {scan_folder}")
    print(f"  📝 Cached items   : {len(cached_results)}")
    print("="*70 + "\n")

    name_tracker = NameTracker()
    results = []
    applied_count = 0

    for item in cached_results:
        orig = item.get("original_file")
        company = item.get("company")
        sender = item.get("sender")
        is_known = item.get("is_known_company", False)
        fp = os.path.join(scan_folder, orig)

        r = {
            "original_file": orig,
            "new_filename": None,
            "company": company,
            "sender": sender,
            "is_known_company": is_known,
            "error": None
        }

        if not os.path.exists(fp):
            r["error"] = "File not found on disk (already renamed or moved)"
            results.append(r)
            continue

        if not company or not sender or item.get("error"):
            r["error"] = item.get("error") or "Missing company or sender in cache"
            results.append(r)
            continue

        try:
            r["new_filename"] = rename_pdf(fp, company, sender, dry_run=False, name_tracker=name_tracker)
            applied_count += 1
        except Exception as e:
            r["error"] = f"Rename failed: {e}"

        results.append(r)

    print_summary(results, total_api_calls=0, total_keys_used=0)

    # Clean up cache on successful application
    if applied_count > 0:
        try:
            os.remove(CACHE_FILE)
            print("🗑️  Cleaned up cache file.")
        except Exception:
            pass

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PDF Renamer — local-first, optional Gemini fallback")
    parser.add_argument("folder", nargs="?", default=None,
                        help="Folder to scan (default: ~/Desktop)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview renames without changing files (saves to cache)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply previously cached dry-run renames (no analysis)")
    parser.add_argument("--gemini-fallback", action="store_true",
                        help="Send files the local pass can't resolve to Google Gemini "
                             "(uploads their page images + your company list)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Files per Gemini fallback request (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--model", default=GEMINI_MODEL,
                        help=f"Gemini model for --gemini-fallback (default: {GEMINI_MODEL})")
    args = parser.parse_args()

    scan_folder = args.folder or str(get_desktop_path())
    if not os.path.isdir(scan_folder):
        print(f"❌ Folder not found: {scan_folder}"); sys.exit(1)

    # If --apply was requested, apply cached renames directly without API keys
    if args.apply:
        apply_cached_renames(scan_folder)
        return

    ref = load_reference_list()
    companies = ref.get("companies", [])

    # Local analysis always needs Ollama — never fall back to Gemini silently
    check_ollama(LOCAL_MODEL)

    # ── Initialize API key manager (only for --gemini-fallback) ──
    key_manager = None
    if args.gemini_fallback:
        if genai is None:
            print("❌ --gemini-fallback needs: pip install google-genai"); sys.exit(1)
        key_manager = APIKeyManager()
        if key_manager.count == 0:
            print("❌ No Gemini API keys found.")
            print("   Set GEMINI_API_KEYS=key1,key2,key3 in .env (comma-separated)")
            print("   Or set GEMINI_API_KEY=single-key")
            print("   Use a billing-enabled key: free-tier content may be used to train Google's models.")
            sys.exit(1)

    print("="*70)
    print("  PDF RENAMER — Local Processing")
    print("="*70)
    print(f"  📋 Companies loaded : {len(companies)}")
    print(f"  🔒 Local model      : {LOCAL_MODEL} (on this computer)")
    if key_manager:
        print(f"  ☁️  Gemini fallback  : {args.model}, {key_manager.count} key(s), {args.batch_size} file(s)/request")
    else:
        print("  ☁️  Gemini fallback  : off (nothing leaves this computer)")
    print("="*70 + "\n")

    # ── Discover PDFs ──
    all_pdfs = sorted(f for f in os.listdir(scan_folder)
                      if f.lower().endswith(".pdf") and not f.startswith("."))
    if not all_pdfs:
        print(f"📂 No PDFs found in: {scan_folder}"); sys.exit(0)

    # Skip files that are already renamed
    skipped = [f for f in all_pdfs if is_already_renamed(f)]
    pdfs = [f for f in all_pdfs if not is_already_renamed(f)]

    if not pdfs:
        print(f"📂 All {len(all_pdfs)} PDF(s) are already renamed — nothing to do.")
        sys.exit(0)

    # ── Execution Plan ──
    print(f"\n{'─'*50}")
    print(f"  📊 EXECUTION PLAN")
    print(f"{'─'*50}")
    print(f"  📂 Folder           : {scan_folder}")
    print(f"  📄 Total PDFs found : {len(all_pdfs)}")
    if skipped:
        print(f"  ✅ Already renamed  : {len(skipped)} (skipped)")
    print(f"  📝 To process       : {len(pdfs)}")
    print(f"{'─'*50}\n")

    if args.dry_run:
        print("🔍 DRY RUN — no files will be changed.\n")

    start_time = time.time()

    # ── Local pass (on this Mac) ──
    results = []
    unresolved = []                 # left untouched unless --gemini-fallback resolves them
    name_tracker = NameTracker()  # tracks duplicate company+sender across all files

    for i, fn in enumerate(pdfs, 1):
        eta_str = ""
        if i > 1:
            remaining = (time.time() - start_time) / (i - 1) * (len(pdfs) - i + 1)
            eta_str = f"  ~{remaining/60:.1f} min remaining"
        print(f"  [{i}/{len(pdfs)}] 📄 {fn}{eta_str}")

        fp = os.path.join(scan_folder, fn)
        r = {"original_file": fn, "new_filename": None,
             "company": None, "sender": None,
             "is_known_company": False, "error": None}
        try:
            text = ocr_pdf(fp)
            company, how = match_company(fn, text, companies)
            sender = extract_sender(text, company) if company else "UNKNOWN"
            r.update(company=company, sender=sender, is_known_company=company is not None)
            if how == "conflict":
                r["error"] = "filename and letter point to different companies"
            elif not company:
                r["error"] = "recipient not found in your company list"
            elif sender == "UNKNOWN" and args.gemini_fallback:
                r["error"] = "sender not found in the letter"
            elif sender == "UNKNOWN":
                print("    ℹ️  Sender not found in the letter — naming it 'From UNKNOWN'")
        except Exception as e:
            r["error"] = f"Local analysis failed: {e}"

        if r["error"] is None:
            try:
                r["new_filename"] = rename_pdf(fp, company, sender, args.dry_run, name_tracker)
            except Exception as e:
                r["error"] = f"Rename failed: {e}"
            results.append(r)
        else:
            print(f"    ⚠️  Unresolved: {r['error']}")
            r["error"] = f"Unresolved — {r['error']}"
            unresolved.append(r)

    # ── Gemini fallback (only with --gemini-fallback) ──
    total_api_calls = 0
    keys_used = set()
    if unresolved and key_manager:
        print(f"\n  ☁️  Sending {len(unresolved)} unresolved file(s) to Google Gemini "
              f"(page images + your company list)…")
        throttler = SmartThrottler(RPM_PER_KEY, key_manager.available_count)
        num_batches = (len(unresolved) + args.batch_size - 1) // args.batch_size

        for batch_num, batch in enumerate(chunk_files(unresolved, args.batch_size), 1):
            print(f"{'─'*50}")
            print(f"  GEMINI BATCH {batch_num}/{num_batches}  ({len(batch)} file(s))")
            print(f"{'─'*50}")

            # One JPEG part per page, at full resolution
            parts, valid, page_counts = [], [], []
            for r in batch:
                try:
                    print(f"  📸 {r['original_file']}")
                    pages = pdf_to_images(os.path.join(scan_folder, r["original_file"]))
                    for img in pages:
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=90)
                        parts.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"))
                    valid.append(r)
                    page_counts.append(len(pages))
                except Exception as e:
                    r["error"] = f"Image conversion failed: {e}"
                    print(f"    ❌ {e}")

            if not valid:
                continue

            prompt = build_prompt_batch(ref, [r["original_file"] for r in valid], page_counts)
            # Track which keys are in use (for summary stats)
            for k in key_manager.keys:
                if k not in key_manager.exhausted_keys:
                    keys_used.add(k)
                    break

            # Enforce RPM limit before calling API
            throttler.wait_if_needed()
            ai_results = analyze_batch_with_gemini(parts, len(valid), prompt, key_manager, model=args.model)
            total_api_calls += 1

            if ai_results is None:
                print("\n  🛑 Stopping — all API keys exhausted (remaining files left as is).")
                break

            # Gemini fills in only what the local pass couldn't
            for idx, r in enumerate(valid):
                if idx >= len(ai_results):
                    r["error"] = "No AI result returned for this file"
                    continue
                data = ai_results[idx]
                if not r["is_known_company"]:
                    r.update(company=data.get("company", "UNKNOWN"),
                             sender=data.get("sender", "UNKNOWN"),
                             is_known_company=data.get("is_known_company", False))
                elif r["sender"] == "UNKNOWN":
                    r["sender"] = data.get("sender", "UNKNOWN")
                if ({str(r["company"]).upper(), str(r["sender"]).upper()} & {"UNKNOWN", "PARSE_ERROR"}
                        or same_org(str(r["sender"]), str(r["company"]))):
                    r["error"] = "Unresolved — Gemini couldn't resolve it either"
                    continue
                r["error"] = None
                try:
                    r["new_filename"] = rename_pdf(os.path.join(scan_folder, r["original_file"]),
                                                   r["company"], r["sender"], args.dry_run, name_tracker)
                except Exception as e:
                    r["error"] = f"Rename failed: {e}"

    if unresolved and not key_manager:
        print(f"\n  💡 {len(unresolved)} file(s) left as is. Rename them by hand, or re-run with "
              f"--gemini-fallback to send just those to Gemini.")
    results.extend(unresolved)

    print_summary(results, total_api_calls, len(keys_used))

    if args.dry_run:
        save_rename_cache(scan_folder, results)

if __name__ == "__main__":
    main()