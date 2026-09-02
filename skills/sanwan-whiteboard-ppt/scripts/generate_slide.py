#!/usr/bin/env python3
"""Generate one 16:9 sanwan-style whiteboard slide via EasyRouter.io.

Keeps model + STYLE fixed. Resolves API key from:
  1) --api-key
  2) EASYROUTER_API_KEY env
  3) ~/.config/sanwan-whiteboard-ppt/easyrouter_api_key

Usage:
  python generate_slide.py --prompt-file page_01.txt --out slide_01.png
  python generate_slide.py --prompt-file page_01.txt --out slide_01.png --api-key sk-...
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from manage_api_key import KEY_FILE, mask_key, read_key  # noqa: E402

DEFAULT_BASE_URL = "https://easyrouter.io/v1"
DEFAULT_MODEL = "gemini-3.1-flash-image"
DEFAULT_TIMEOUT = 180

STYLE_PREFIX = """Whiteboard filling the ENTIRE 16:9 frame, all four silver/gray magnetic
frame borders fully visible at image edges, zero background, zero office or room visible.
Clean white whiteboard surface. All text rendered in elegant Chinese hard-pen fountain pen
handwriting calligraphy (硬笔书法) — precise clean strokes, ink variation, flowing and
neat, fine pen line quality, NOT thick marker, NOT digital font. Illustrations are
hand-drawn cartoon style: bold black marker outlines (like Copic multiliner), filled with
vivid colored markers (Copic/Prismacolor style), layered shadows and highlights for depth,
NOT flat vector, NOT watercolor wash — solid marker color with visible stroke direction.
MANDATORY MASCOT on every single page without exception: a super cute chibi Labrador
retriever wearing a red lobster-claw hat, big sparkling eyes, rosy cheeks, fluffy golden
fur, hand-drawn marker style — expression matching the page mood (curious, excited,
thinking, celebrating, etc.). DO NOT omit the Labrador mascot under any circumstances.
Annotation marks in red or black hand-drawn pen (arrows, underlines, ✕, ✓). 16:9 widescreen.
"""


def resolve_api_key(cli_key: Optional[str] = None) -> str:
    if cli_key and cli_key.strip():
        return cli_key.strip()
    env = (os.environ.get("EASYROUTER_API_KEY") or "").strip()
    if env:
        return env
    local = read_key()
    if local:
        return local
    print("Error: EasyRouter API key is not set.", file=sys.stderr)
    print(
        "Provide via --api-key, env EASYROUTER_API_KEY, or save locally with:",
        file=sys.stderr,
    )
    print(
        f"  python scripts/manage_api_key.py save   # writes {KEY_FILE}",
        file=sys.stderr,
    )
    print("Get a key at https://easyrouter.io/", file=sys.stderr)
    raise SystemExit(2)


def build_prompt(page_body: str) -> str:
    body = page_body.strip()
    return f"{STYLE_PREFIX.strip()}\n\n{body}".strip()


def _looks_like_image_bytes(data: bytes) -> bool:
    if len(data) < 8:
        return False
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if data[:3] == b"\xff\xd8\xff":
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return True
    return False


def _decode_b64_image(raw: str) -> Optional[bytes]:
    s = raw.strip()
    if s.startswith("data:"):
        m = re.match(r"data:image/[^;]+;base64,(.+)", s, re.DOTALL)
        if not m:
            return None
        s = m.group(1)
    s = re.sub(r"\s+", "", s)
    try:
        data = base64.b64decode(s, validate=False)
    except Exception:
        return None
    if _looks_like_image_bytes(data):
        return data
    if len(data) > 1024:
        return data
    return None


def _download_url(url: str, timeout: int = 60) -> Optional[bytes]:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        if _looks_like_image_bytes(resp.content) or len(resp.content) > 1024:
            return resp.content
    except Exception as exc:
        print(f"Warning: failed to download image url: {exc}", file=sys.stderr)
    return None


def _walk_extract_image(obj: Any, depth: int = 0) -> Optional[bytes]:
    if depth > 12:
        return None
    if isinstance(obj, str):
        # Handle markdown image syntax: ![image](data:image/png;base64,...)
        md_img_match = re.match(r'!\[.*?\]\((data:image/[^;]+;base64,[^)]+)\)', obj)
        if md_img_match:
            return _decode_b64_image(md_img_match.group(1))
        if obj.startswith("data:image"):
            return _decode_b64_image(obj)
        if obj.startswith("http://") or obj.startswith("https://"):
            path = urlparse(obj).path.lower()
            if any(path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")) or "image" in obj:
                return _download_url(obj)
        if len(obj) > 200 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", obj or ""):
            return _decode_b64_image(obj)
        return None
    if isinstance(obj, dict):
        for k in (
            "b64_json",
            "image_base64",
            "base64",
            "data",
            "inline_data",
            "inlineData",
        ):
            if k in obj:
                v = obj[k]
                if isinstance(v, dict):
                    if "data" in v and isinstance(v["data"], str):
                        img = _decode_b64_image(v["data"])
                        if img:
                            return img
                elif isinstance(v, str):
                    img = _decode_b64_image(v)
                    if img:
                        return img
        for k in ("url", "image_url", "imageUrl"):
            if k in obj and isinstance(obj[k], str):
                img = (
                    _download_url(obj[k])
                    if obj[k].startswith("http")
                    else _decode_b64_image(obj[k])
                )
                if img:
                    return img
            if k in obj and isinstance(obj[k], dict) and "url" in obj[k]:
                u = obj[k]["url"]
                if isinstance(u, str):
                    img = _download_url(u) if u.startswith("http") else _decode_b64_image(u)
                    if img:
                        return img
        for v in obj.values():
            img = _walk_extract_image(v, depth + 1)
            if img:
                return img
    if isinstance(obj, list):
        for item in obj:
            img = _walk_extract_image(item, depth + 1)
            if img:
                return img
    return None


def extract_image_bytes(result: dict) -> Optional[bytes]:
    return _walk_extract_image(result)


def generate_slide(
    page_body: str,
    out_path: Path,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> Path:
    prompt = build_prompt(page_body)
    endpoint = base_url.rstrip("/") + "/chat/completions"

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "modalities": ["text", "image"],
        "image_config": {"aspect_ratio": "16:9"},
        "extra_body": {
            "image_config": {"aspect_ratio": "16:9"},
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print(f"API: POST {endpoint}", file=sys.stderr)
    print(f"Model: {model}", file=sys.stderr)
    print(f"Key: {mask_key(api_key)}", file=sys.stderr)
    print(f"Out: {out_path}", file=sys.stderr)

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
    except requests.Timeout:
        print(f"Error: request timed out after {timeout}s", file=sys.stderr)
        raise SystemExit(1)
    except requests.RequestException as exc:
        print(f"Error: request failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if resp.status_code != 200:
        try:
            err = resp.json()
            msg = (
                (err.get("error") or {}).get("message")
                if isinstance(err.get("error"), dict)
                else err.get("error") or err
            )
            backend = str(msg)[:500]
        except Exception:
            backend = resp.text[:500]
        if resp.status_code in (401, 403):
            print(
                f"Error: auth failed ({resp.status_code}). Check EasyRouter API key.",
                file=sys.stderr,
            )
        elif resp.status_code == 429:
            print(
                "Error: rate limited / quota exceeded. Retry later or top up credits.",
                file=sys.stderr,
            )
        else:
            print(f"Error: HTTP {resp.status_code}: {backend}", file=sys.stderr)
        raise SystemExit(1)

    try:
        result = resp.json()
    except json.JSONDecodeError:
        print("Error: response is not JSON", file=sys.stderr)
        raise SystemExit(1)

    img = extract_image_bytes(result)
    if not img:
        preview = json.dumps(result, ensure_ascii=False)[:800]
        print("Error: no image data found in response.", file=sys.stderr)
        print(f"Response preview: {preview}", file=sys.stderr)
        raise SystemExit(1)

    out_path = out_path.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img)
    print(str(out_path))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate one sanwan whiteboard 16:9 slide via EasyRouter.io"
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt-file", help="Page body text file (without STYLE prefix)")
    src.add_argument("--prompt", help="Page body text (without STYLE prefix)")
    parser.add_argument("--out", required=True, help="Output PNG path")
    parser.add_argument("--api-key", help="EasyRouter API key (optional if env/local file)")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model (default fixed: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout seconds (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args()

    if args.prompt_file:
        body = Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        body = args.prompt

    api_key = resolve_api_key(args.api_key)
    generate_slide(
        page_body=body,
        out_path=Path(args.out),
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        timeout=args.timeout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
