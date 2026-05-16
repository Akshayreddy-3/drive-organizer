#!/usr/bin/env python3
import os
import re
import json
import argparse
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def load_companies():
    try:
        from secure_companies import load_encrypted_reference
        data = load_encrypted_reference()
        return data.get("companies", [])
    except ImportError:
        # Fallback if secure_companies.py is not available
        ref_file = os.path.join(_SCRIPT_DIR, "companies_reference.json")
        if not os.path.exists(ref_file):
            print(f"⚠️ Reference file not found: {ref_file}")
            return []
        with open(ref_file) as f:
            data = json.load(f)
            return data.get("companies", [])

def normalize(name):
    """Normalize company name for fuzzy matching"""
    name = name.lower()
    name = re.sub(r'[^a-z0-9]', '', name)
    # optionally remove 'inc' from the end for looser matching
    if name.endswith('inc'):
        name = name[:-3]
    return name

def sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", name).strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=os.path.expanduser("~/Desktop"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scan_folder = args.folder
    if not os.path.isdir(scan_folder):
        print(f"❌ Folder not found: {scan_folder}")
        sys.exit(1)

    companies = load_companies()
    
    # Create a lookup mapping normalized string -> actual company name
    comp_map = {normalize(c["name"]): c["name"] for c in companies}
    
    pdfs = sorted(f for f in os.listdir(scan_folder) if f.lower().endswith(".pdf") and not f.startswith("."))
    
    print("======================================================================")
    print("  OFFLINE PDF RENAMER (Filename Matching)")
    print("======================================================================")
    print(f"📂 {len(pdfs)} PDF(s) found in {scan_folder}\n")

    matched = 0
    
    # Regex to capture everything before a 14-digit timestamp
    pattern = re.compile(r'^(.*?)(\d{14})\.pdf$', re.IGNORECASE)

    for filename in pdfs:
        filepath = os.path.join(scan_folder, filename)
        
        # 1. Try to extract name using the 14-digit timestamp pattern
        match = pattern.match(filename)
        if match:
            raw_name = match.group(1)
        else:
            # Fallback: just use the whole filename minus the extension
            raw_name = filename[:-4]
        
        norm_name = normalize(raw_name)
        
        # 2. Try to find a match in our known companies
        matched_company = comp_map.get(norm_name)
        
        if matched_company:
            sc = sanitize(matched_company)
            # Default sender since we aren't using AI
            new_name = f"{sc} - From UNKNOWN.pdf"
            new_path = os.path.join(scan_folder, new_name)
            
            # Handle duplicates
            ctr = 1
            while os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(filepath):
                new_name = f"{sc} - From UNKNOWN ({ctr}).pdf"
                new_path = os.path.join(scan_folder, new_name)
                ctr += 1
            
            if args.dry_run:
                print(f"✅ {filename}\n   → {new_name}\n")
            else:
                os.rename(filepath, new_path)
                print(f"✅ Renamed: {new_name}")
                
            matched += 1
        else:
            print(f"⚠️ No match for: {filename} (Extracted: '{raw_name}')\n")

    print(f"\n✅ Done. Successfully renamed {matched} out of {len(pdfs)} files.")

if __name__ == "__main__":
    main()
