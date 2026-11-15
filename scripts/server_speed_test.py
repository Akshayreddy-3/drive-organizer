#!/usr/bin/env python3
"""
server_speed_test.py - How many seconds per letter does the Ollama server take?

Uses made-up letters only (no real scans). Reads OLLAMA_URL from .env like the renamer.
    python3 scripts/server_speed_test.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ai_pdf_renamer as r

SHORT = ("Acme Widgets LLC\n12 Main Street, Springfield\n\nBob Corp\nAttn: Accounts\n\n"
         "Dear Bob Corp,\nPlease pay invoice 7 by the end of the month.\n\nSincerely,\nAcme Widgets LLC")
# Sender only at the bottom → the model also reads the whole letter (the slow, worst case)
FILLER = "\n".join(f"Item {i}: services rendered as agreed in the contract, amount due." for i in range(120))
LONG = f"Bob Corp\nAttn: Accounts\n\nDear Bob Corp,\n{FILLER}\n\nSincerely,\nNorthwind Legal Partners"

print(f"Server: {r.OLLAMA_URL}   Model: {r.LOCAL_MODEL}")
r.check_ollama(r.LOCAL_MODEL)
for name, text, expected in [("warm-up (loads model)", SHORT, "Acme Widgets LLC"),
                             ("typical letter", SHORT, "Acme Widgets LLC"),
                             ("long letter, sender at bottom", LONG, "Northwind Legal Partners")]:
    t = time.time()
    sender = r.extract_sender(text, "Bob Corp")
    ok = "✅" if sender == expected else f"⚠️ expected {expected}"
    print(f"{name:32s} {time.time() - t:6.1f}s  → {sender} {ok}")
