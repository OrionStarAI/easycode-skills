#!/usr/bin/env python3
"""Secure local EasyRouter API key storage for sanwan-whiteboard-ppt.

Constrained path:
  ~/.config/sanwan-whiteboard-ppt/easyrouter_api_key

Usage:
  python manage_api_key.py status
  python manage_api_key.py save --key sk-xxx
  printf '%s' "$KEY" | python manage_api_key.py save
  python manage_api_key.py clear
  python manage_api_key.py path
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "sanwan-whiteboard-ppt"
KEY_FILE = CONFIG_DIR / "easyrouter_api_key"


def key_path() -> Path:
    return KEY_FILE


def mask_key(key: str) -> str:
    key = key.strip()
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:4]}…{key[-4:]}"


def ensure_secure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass


def read_key() -> str | None:
    if not KEY_FILE.is_file():
        return None
    try:
        raw = KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return raw or None


def save_key(key: str) -> Path:
    key = (key or "").strip()
    if not key:
        raise SystemExit("Error: empty API key")
    ensure_secure_dir()
    KEY_FILE.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    return KEY_FILE


def clear_key() -> bool:
    if KEY_FILE.is_file():
        KEY_FILE.unlink()
        return True
    return False


def cmd_status(_: argparse.Namespace) -> int:
    # stdout is path only — never print the secret
    print(str(KEY_FILE))
    key = read_key()
    if key:
        print(f"present masked={mask_key(key)}", file=sys.stderr)
        return 0
    print("absent", file=sys.stderr)
    return 1


def cmd_path(_: argparse.Namespace) -> int:
    print(str(KEY_FILE))
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    key = args.key
    if not key:
        if sys.stdin.isatty():
            print(
                "Error: pass --key or pipe the key via stdin "
                "(prefer stdin to avoid shell history).",
                file=sys.stderr,
            )
            return 2
        key = sys.stdin.read()
    path = save_key(key)
    print(f"saved path={path} masked={mask_key(key.strip())}")
    return 0


def cmd_clear(_: argparse.Namespace) -> int:
    if clear_key():
        print(f"cleared {KEY_FILE}")
    else:
        print(f"nothing to clear ({KEY_FILE} missing)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage local EasyRouter API key for sanwan-whiteboard-ppt"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Exit 0 if key exists; print path only")
    p_status.set_defaults(func=cmd_status)

    p_path = sub.add_parser("path", help="Print constrained key file path")
    p_path.set_defaults(func=cmd_path)

    p_save = sub.add_parser("save", help="Save key to constrained local path (0600)")
    p_save.add_argument("--key", help="API key (prefer stdin instead)")
    p_save.set_defaults(func=cmd_save)

    p_clear = sub.add_parser("clear", help="Delete locally stored key")
    p_clear.set_defaults(func=cmd_clear)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
