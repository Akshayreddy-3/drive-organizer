#!/usr/bin/env python3
"""
scripts/credentials_to_env.py

Convert a Google OAuth `credentials.json` (client secrets) into a `.env` file
that contains GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (and optional URIs).

Usage:
  python scripts/credentials_to_env.py --input ./credentials.json --output .env

Options:
  --dry-run    : print what would be written (values are masked)
  --force      : overwrite output file if it exists

Security:
  The generated `.env` may contain secrets. This repository's `.gitignore`
  excludes `.env` by default. Review the generated file locally and do
  NOT commit it to version control.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Any, List, Optional


def mask_secret(s: Optional[str]) -> str:
    if not s:
        return ""
    if len(s) <= 8:
        return s[:2] + "****"
    return s[:4] + "..." + s[-4:]


def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_oauth_info(data: Dict[str, Any]) -> Dict[str, Any]:
    # credentials.json may have top-level keys 'installed' or 'web'
    if 'installed' in data:
        cfg = data['installed']
    elif 'web' in data:
        cfg = data['web']
    else:
        # assume the file itself is the client config
        cfg = data

    return {
        'client_id': cfg.get('client_id'),
        'client_secret': cfg.get('client_secret'),
        'auth_uri': cfg.get('auth_uri'),
        'token_uri': cfg.get('token_uri'),
        'redirect_uris': cfg.get('redirect_uris', []),
    }


def build_env_lines(oauth: Dict[str, Any], defaults: Dict[str, str]) -> List[str]:
    lines: List[str] = []

    lines.append(f"# Generated from credentials.json")
    lines.append(f"# Review before using or committing")
    lines.append("")

    cid = oauth.get('client_id') or ''
    csecret = oauth.get('client_secret') or ''
    auth_uri = oauth.get('auth_uri') or defaults.get('GOOGLE_AUTH_URI', '')
    token_uri = oauth.get('token_uri') or defaults.get('GOOGLE_TOKEN_URI', '')

    lines.append(f"GOOGLE_CLIENT_ID={cid}")
    lines.append(f"GOOGLE_CLIENT_SECRET={csecret}")
    if auth_uri:
        lines.append(f"GOOGLE_AUTH_URI={auth_uri}")
    if token_uri:
        lines.append(f"GOOGLE_TOKEN_URI={token_uri}")

    # Optional: keep CREDENTIALS_FILE and TOKEN_FILE entries (useful defaults)
    lines.append("")
    lines.append(f"CREDENTIALS_FILE={defaults.get('CREDENTIALS_FILE', './credentials.json')}")
    lines.append(f"TOKEN_FILE={defaults.get('TOKEN_FILE', './token.json')}")
    lines.append(f"SCOPES={defaults.get('SCOPES', 'https://www.googleapis.com/auth/drive')}")
    lines.append(f"VERBOSE_MODE={defaults.get('VERBOSE_MODE', 'True')}")

    return [l + '\n' for l in lines]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Convert credentials.json into a .env file")
    parser.add_argument('--input', '-i', default='credentials.json', help='Path to credentials.json')
    parser.add_argument('--output', '-o', default='.env', help='Output .env path')
    parser.add_argument('--dry-run', action='store_true', help='Show the values that would be written (masked)')
    parser.add_argument('--force', action='store_true', help='Overwrite output file if it exists')

    args = parser.parse_args(argv)

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.exists(input_path):
        print(f"ERROR: input file not found: {input_path}")
        return 2

    try:
        data = load_json(input_path)
    except Exception as e:
        print(f"ERROR: failed to read/parse JSON: {e}")
        return 3

    oauth = extract_oauth_info(data)

    defaults = {
        'CREDENTIALS_FILE': os.path.relpath(input_path),
        'TOKEN_FILE': os.getenv('TOKEN_FILE', './token.json'),
        'SCOPES': os.getenv('SCOPES', 'https://www.googleapis.com/auth/drive'),
        'VERBOSE_MODE': os.getenv('VERBOSE_MODE', 'True'),
        'GOOGLE_AUTH_URI': os.getenv('GOOGLE_AUTH_URI', ''),
        'GOOGLE_TOKEN_URI': os.getenv('GOOGLE_TOKEN_URI', ''),
    }

    env_lines = build_env_lines(oauth, defaults)

    if args.dry_run:
        # Print masked output for safety
        print(f"# Dry-run: would write to {output_path}\n")
        for line in env_lines:
            if line.startswith('GOOGLE_CLIENT_ID='):
                print('GOOGLE_CLIENT_ID=' + mask_secret(oauth.get('client_id')))
            elif line.startswith('GOOGLE_CLIENT_SECRET='):
                print('GOOGLE_CLIENT_SECRET=' + mask_secret(oauth.get('client_secret')))
            else:
                # print other lines as-is (they're not secrets)
                print(line.rstrip('\n'))
        return 0

    if os.path.exists(output_path) and not args.force:
        print(f"ERROR: output file already exists: {output_path}\nUse --force to overwrite")
        return 4

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
    except Exception as e:
        print(f"ERROR: failed to write .env: {e}")
        return 5

    print(f"Wrote .env to: {output_path}")
    print("Review the file and ensure you do not commit it to version control.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
