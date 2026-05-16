#!/usr/bin/env python3
"""
secure_companies.py — Encrypt / Decrypt companies_reference.json

Encrypts the plaintext JSON into companies_reference.enc using a key
stored in .env (COMPANIES_KEY). The encrypted file is safe to share;
the plaintext JSON should be deleted or kept in .gitignore.

USAGE:
  python3 secure_companies.py encrypt          # JSON → .enc (generates key if needed)
  python3 secure_companies.py decrypt          # .enc → JSON (for editing)
  python3 secure_companies.py rotate-key       # Re-encrypt with a brand-new key
  python3 secure_companies.py show             # Print decrypted data to terminal (temp view)

REQUIREMENTS:
  pip install cryptography python-dotenv
"""

import os, sys, json, argparse

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("❌ Run: pip install cryptography")
    sys.exit(1)

try:
    from dotenv import load_dotenv, set_key
except ImportError:
    print("❌ Run: pip install python-dotenv")
    sys.exit(1)

# ── Paths ────────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
JSON_FILE     = os.path.join(_SCRIPT_DIR, "companies_reference.json")
ENC_FILE      = os.path.join(_SCRIPT_DIR, "companies_reference.enc")
ENV_FILE      = os.path.join(_SCRIPT_DIR, ".env")
KEY_ENV_NAME  = "COMPANIES_KEY"


def _load_key() -> bytes:
    """Load encryption key from .env"""
    load_dotenv(ENV_FILE)
    key = os.getenv(KEY_ENV_NAME, "").strip()
    if not key:
        return b""
    return key.encode()


def _save_key_to_env(key: bytes):
    """Write (or update) the encryption key in .env"""
    # Ensure .env exists
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w") as f:
            f.write("")

    set_key(ENV_FILE, KEY_ENV_NAME, key.decode())
    print(f"  🔑 Key saved to .env as {KEY_ENV_NAME}")


def _generate_key() -> bytes:
    """Generate a new Fernet key."""
    return Fernet.generate_key()


# ── Public API (used by other scripts) ───────────────────────────────────────
def load_encrypted_reference() -> dict:
    """
    Load and decrypt companies_reference.enc → dict.

    Falls back to plaintext JSON if .enc doesn't exist yet
    (for backward compatibility during migration).
    """
    load_dotenv(ENV_FILE)

    # Try encrypted file first
    if os.path.exists(ENC_FILE):
        key = _load_key()
        if not key:
            print("⚠️  COMPANIES_KEY not set in .env — cannot decrypt.")
            print("   Run: python3 secure_companies.py encrypt")
            return {"companies": []}

        try:
            f = Fernet(key)
            with open(ENC_FILE, "rb") as ef:
                decrypted = f.decrypt(ef.read())
            return json.loads(decrypted.decode())
        except Exception as e:
            print(f"⚠️  Decryption failed: {e}")
            return {"companies": []}

    # Fallback: plaintext JSON (backward compat)
    if os.path.exists(JSON_FILE):
        print("⚠️  Using plaintext companies_reference.json (not encrypted yet)")
        print("   Run: python3 secure_companies.py encrypt")
        with open(JSON_FILE) as jf:
            return json.load(jf)

    print("⚠️  No company reference file found.")
    return {"companies": []}


# ── CLI Commands ─────────────────────────────────────────────────────────────
def cmd_encrypt():
    """Encrypt companies_reference.json → companies_reference.enc"""
    if not os.path.exists(JSON_FILE):
        print(f"❌ Plaintext file not found: {JSON_FILE}")
        print("   Nothing to encrypt.")
        sys.exit(1)

    # Read the plaintext JSON
    with open(JSON_FILE) as f:
        data = f.read()

    # Validate JSON
    try:
        parsed = json.loads(data)
        company_count = len(parsed.get("companies", []))
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        sys.exit(1)

    # Generate or reuse key
    existing_key = _load_key()
    if existing_key:
        print("  🔑 Using existing key from .env")
        key = existing_key
    else:
        key = _generate_key()
        _save_key_to_env(key)

    # Encrypt
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())

    with open(ENC_FILE, "wb") as ef:
        ef.write(encrypted)

    print(f"\n  ✅ Encrypted {company_count} companies → {os.path.basename(ENC_FILE)}")
    print(f"  📦 Encrypted file size: {len(encrypted):,} bytes")
    print(f"\n  ⚠️  You can now DELETE the plaintext file for maximum security:")
    print(f"     rm {JSON_FILE}")
    print(f"\n  💡 To edit companies later, run:")
    print(f"     python3 secure_companies.py decrypt   (creates JSON)")
    print(f"     # ... edit the JSON ...")
    print(f"     python3 secure_companies.py encrypt   (re-encrypts)")


def cmd_decrypt():
    """Decrypt companies_reference.enc → companies_reference.json"""
    if not os.path.exists(ENC_FILE):
        print(f"❌ Encrypted file not found: {ENC_FILE}")
        sys.exit(1)

    key = _load_key()
    if not key:
        print(f"❌ {KEY_ENV_NAME} not found in .env")
        sys.exit(1)

    try:
        fernet = Fernet(key)
        with open(ENC_FILE, "rb") as ef:
            decrypted = fernet.decrypt(ef.read())
    except Exception as e:
        print(f"❌ Decryption failed: {e}")
        sys.exit(1)

    # Verify JSON validity
    parsed = json.loads(decrypted.decode())
    company_count = len(parsed.get("companies", []))

    with open(JSON_FILE, "w") as jf:
        jf.write(decrypted.decode())

    print(f"  ✅ Decrypted {company_count} companies → {os.path.basename(JSON_FILE)}")
    print(f"\n  ⚠️  Remember to re-encrypt after editing:")
    print(f"     python3 secure_companies.py encrypt")


def cmd_rotate_key():
    """Re-encrypt with a brand-new key (old key is replaced)."""
    if not os.path.exists(ENC_FILE):
        print("❌ No encrypted file found. Run 'encrypt' first.")
        sys.exit(1)

    # Decrypt with old key
    old_key = _load_key()
    if not old_key:
        print(f"❌ {KEY_ENV_NAME} not found in .env")
        sys.exit(1)

    fernet_old = Fernet(old_key)
    with open(ENC_FILE, "rb") as ef:
        plaintext = fernet_old.decrypt(ef.read())

    # Generate new key
    new_key = _generate_key()
    fernet_new = Fernet(new_key)
    new_encrypted = fernet_new.encrypt(plaintext)

    # Save
    with open(ENC_FILE, "wb") as ef:
        ef.write(new_encrypted)
    _save_key_to_env(new_key)

    print("  ✅ Key rotated — re-encrypted with new key")
    print("  🔑 New key saved to .env")


def cmd_show():
    """Print decrypted companies to terminal (for quick viewing)."""
    data = load_encrypted_reference()
    companies = data.get("companies", [])
    if not companies:
        print("  (no companies found)")
        return

    print(f"\n  📋 {len(companies)} Companies:\n")
    for i, c in enumerate(companies, 1):
        addrs = "; ".join(c.get("addresses", []))
        print(f"  {i:3}. {c.get('name', '?')}")
        if addrs:
            print(f"       📍 {addrs}")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Encrypt/decrypt companies_reference.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  encrypt      Encrypt companies_reference.json → .enc file
  decrypt      Decrypt .enc → companies_reference.json (for editing)
  rotate-key   Re-encrypt with a new key
  show         Print decrypted data to terminal
        """
    )
    parser.add_argument("command", choices=["encrypt", "decrypt", "rotate-key", "show"],
                        help="Action to perform")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  🔒 SECURE COMPANIES — Encryption Manager")
    print("=" * 60 + "\n")

    if args.command == "encrypt":
        cmd_encrypt()
    elif args.command == "decrypt":
        cmd_decrypt()
    elif args.command == "rotate-key":
        cmd_rotate_key()
    elif args.command == "show":
        cmd_show()

    print()


if __name__ == "__main__":
    main()
