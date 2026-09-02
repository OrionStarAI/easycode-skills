#!/usr/bin/env python3
"""
Generate cover images for WeChat Official Account articles using EasyRouter.io (gpt-image-2).

API key is required. Provide it via:
  --api-key CLI arg, OR
  EASYROUTER_API_KEY environment variable

Usage:
  # Basic usage
  python generate_cover.py --title "Article Title" --api-key sk-xxx -o cover.jpg

  # Custom AI prompt
  python generate_cover.py --title "Title" --prompt "Cyberpunk city night scene" --api-key sk-xxx -o cover.jpg

  # Image-to-image cover
  python generate_cover.py --title "Title" --image /path/to/ref.jpg --api-key sk-xxx -o cover.jpg

  # Allow fallback to Picsum on AI failure
  python generate_cover.py --title "Title" --allow-fallback --api-key sk-xxx -o cover.jpg
"""

import argparse
import base64
import os
import sys
import time
from datetime import datetime
from typing import Optional

import requests

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_BASE_URL = "https://easyrouter.io/v1"
DEFAULT_MODEL = "gpt-image-2"
OUTPUT_DIR = "outputs"
DEFAULT_SIZE = "1536x1024"  # landscape for WeChat cover

# =============================================================================
# API Key
# =============================================================================

def get_api_key(cli_key: Optional[str] = None) -> Optional[str]:
    """Get API key from CLI arg or EASYROUTER_API_KEY env var. Returns None if not found."""
    api_key = cli_key or os.environ.get("EASYROUTER_API_KEY")
    if not api_key:
        return None
    return api_key


# =============================================================================
# Helpers
# =============================================================================

def image_to_b64(image_path: str) -> tuple[str, str]:
    """Convert a local image file to (base64_string, mime_type)."""
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, mime_type


def fetch_picsum(width: int, height: int, output_path: str) -> Optional[str]:
    """Fetch a random image from Picsum Photos as fallback."""
    url = f"https://picsum.photos/{width}/{height}"
    print(f"[Fallback] Fetching Picsum image: {url}")
    try:
        resp = requests.get(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(resp.content)
        abs_path = os.path.abspath(output_path)
        print(f"IMAGE_RESULT: {abs_path}")
        return abs_path
    except Exception as e:
        print(f"[Fallback] Picsum failed: {e}")
        return None


def extract_image_data(result: dict) -> Optional[bytes]:
    """Extract image bytes from API response."""
    data_list = result.get("data") or []
    if not data_list:
        image_data_url = result.get("image_url") or result.get("url")
        if image_data_url:
            if image_data_url.startswith("data:image"):
                import re
                match = re.match(r"data:image/[^;]+;base64,(.+)", image_data_url)
                if match:
                    return base64.b64decode(match.group(1))
            elif image_data_url.startswith("http"):
                resp = requests.get(image_data_url, timeout=60)
                resp.raise_for_status()
                return resp.content
        return None

    item = data_list[0]
    b64 = item.get("b64_json")
    if b64:
        return base64.b64decode(b64)
    url = item.get("url")
    if url:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content
    return None


def build_cover_prompt(title: str, custom_prompt: Optional[str] = None) -> str:
    """Build a cover image prompt from article title."""
    if custom_prompt:
        return custom_prompt
    # Auto-generate: clean editorial style, no text
    return (
        f"editorial magazine cover photography, clean composition, "
        f"no text no watermark no letters, high quality, "
        f"visually striking image representing the theme: {title}"
    )


# =============================================================================
# Core Generation
# =============================================================================

def generate_cover(
    title: str,
    output_path: str,
    api_key: str,
    custom_prompt: Optional[str] = None,
    image_input: Optional[str] = None,
    size: str = DEFAULT_SIZE,
    quality: str = "auto",
    style: Optional[str] = None,
    allow_fallback: bool = False,
    no_ai: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
) -> Optional[str]:
    """Generate a cover image. Returns absolute path or None."""
    # No-AI mode: directly use Picsum
    if no_ai:
        w, h = _parse_size(size, default=(1280, 720))
        return fetch_picsum(w, h, output_path)

    prompt = build_cover_prompt(title, custom_prompt)
    is_edit = bool(image_input)
    mode = "image-edit (img2img)" if is_edit else "text-to-image"
    print(f"Mode: {mode}")
    print(f"Model: {model}")
    print(f"Prompt: '{prompt}'")
    if style:
        print(f"Style: {style}")

    retry_delays = [5, 10, 20]
    for attempt in range(1, max_retries + 1):
        result = _generate_once(
            prompt, output_path, api_key, image_input, size, quality, style,
            base_url, model,
        )
        if result:
            if attempt > 1:
                print(f"  ✅ Succeeded on attempt {attempt}")
            return result
        if attempt < max_retries:
            delay = retry_delays[attempt - 1]
            print(f"  ⚠️  Attempt {attempt}/{max_retries} failed, retrying in {delay}s...")
            time.sleep(delay)

    print(f"  ❌ AI generation failed after {max_retries} attempts")

    # Fallback to Picsum if allowed
    if allow_fallback:
        print("  🔄 Falling back to Picsum random image...")
        w, h = _parse_size(size, default=(1280, 720))
        return fetch_picsum(w, h, output_path)

    return None


def _parse_size(size: str, default: tuple = (1280, 720)) -> tuple[int, int]:
    """Parse 'WxH' or 'W*H' string to (width, height)."""
    sep = "x" if "x" in size else "*"
    parts = size.split(sep)
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    return default


def _generate_once(
    prompt: str,
    output_path: str,
    api_key: str,
    image_input: Optional[str],
    size: str,
    quality: str,
    style: Optional[str],
    base_url: str,
    model: str,
) -> Optional[str]:
    """Single attempt."""
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        if image_input:
            # Edit mode
            endpoint = f"{base_url}/images/edits"
            print(f"Calling API: POST {endpoint}")

            if image_input.startswith("http://") or image_input.startswith("https://"):
                img_resp = requests.get(image_input, timeout=60)
                img_resp.raise_for_status()
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(img_resp.content)
                    tmp_path = tmp.name
                try:
                    b64, mime = image_to_b64(tmp_path)
                finally:
                    os.unlink(tmp_path)
            elif image_input.startswith("data:"):
                import re
                match = re.match(r"data:image/([^;]+);base64,(.+)", image_input)
                if not match:
                    print("Error: Invalid data URI for reference image")
                    return None
                b64 = match.group(2)
                mime = f"image/{match.group(1)}"
            else:
                abs_path = os.path.abspath(image_input)
                if not os.path.exists(abs_path):
                    print(f"Error: Image file not found: {abs_path}")
                    return None
                print(f"  Loading reference image: {abs_path}")
                b64, mime = image_to_b64(abs_path)

            img_bytes = base64.b64decode(b64)
            ext = mime.split("/")[-1]
            files = {"image": (f"input.{ext}", img_bytes, mime)}
            data = {
                "model": model,
                "prompt": prompt,
                "n": "1",
                "size": size,
            }
            if quality and quality != "auto":
                data["quality"] = quality
            if style:
                data["style"] = style

            response = requests.post(endpoint, headers=headers, files=files, data=data, timeout=300)
        else:
            # Text-to-image
            endpoint = f"{base_url}/images/generations"
            print(f"Calling API: POST {endpoint}")

            payload = {
                "model": model,
                "prompt": prompt,
                "n": 1,
                "size": size,
            }
            if quality and quality != "auto":
                payload["quality"] = quality
            if style:
                payload["style"] = style

            headers["Content-Type"] = "application/json"
            response = requests.post(endpoint, headers=headers, json=payload, timeout=300)

        if response.status_code != 200:
            try:
                err = response.json()
                backend_msg = err.get("error", {}).get("message", "") or str(err)
            except Exception:
                backend_msg = response.text[:300]

            if response.status_code == 429:
                print("⚠️  封面生成失败：账户额度不足或请求过于频繁。")
            elif response.status_code in (401, 403):
                print("❌ 认证失败：API Key 无效或已过期。")
            elif response.status_code == 500:
                print("⚠️  封面生成失败：服务暂时不稳定。")
            else:
                print(f"❌ 请求失败（{response.status_code}）：{backend_msg}")
            return None

        result = response.json()
        img_data = extract_image_data(result)
        if not img_data:
            print(f"Error: No image data in response. Response: {str(result)[:300]}")
            return None

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_data)

        abs_path = os.path.abspath(output_path)
        print(f"IMAGE_RESULT: {abs_path}")
        return abs_path

    except Exception as e:
        print(f"Error generating cover: {e}")
        return None


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate WeChat cover images using EasyRouter.io (gpt-image-2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python generate_cover.py --title "Article Title" --api-key sk-xxx -o cover.jpg

  # Custom prompt
  python generate_cover.py --title "Title" --prompt "Cyberpunk city" --api-key sk-xxx

  # Image-to-image
  python generate_cover.py --title "Title" --image ref.jpg --api-key sk-xxx -o cover.jpg

  # Fallback to Picsum on failure
  python generate_cover.py --title "Title" --allow-fallback --api-key sk-xxx -o cover.jpg

  # No AI, use Picsum directly
  python generate_cover.py --title "Title" --no-ai -o cover.jpg
        """,
    )
    parser.add_argument("--title", required=True, help="Article title (used to generate prompt if --prompt not given)")
    parser.add_argument("--prompt", help="Custom AI prompt (overrides auto-generated)")
    parser.add_argument(
        "--api-key",
        help="EasyRouter API key (or set EASYROUTER_API_KEY env var)",
    )
    parser.add_argument(
        "--image", "-i",
        help="Reference image for img2img mode (local path or URL)",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(os.path.dirname(__file__), "..", OUTPUT_DIR, "cover_pending.png"),
        help="Output file path",
    )
    parser.add_argument(
        "--size", "-s",
        default=DEFAULT_SIZE,
        help=f"Image size (default: {DEFAULT_SIZE} for landscape cover)",
    )
    parser.add_argument(
        "--quality", "-q",
        default="auto",
        choices=["low", "medium", "high", "auto"],
        help="Image quality (default: auto)",
    )
    parser.add_argument(
        "--style",
        default=None,
        help="Image style preset (e.g. vivid, natural, or custom). Passed to API as-is.",
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Fall back to Picsum random image if AI generation fails",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip AI, use Picsum random cover directly",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name (default: {DEFAULT_MODEL})",
    )

    args = parser.parse_args()

    api_key = get_api_key(args.api_key)

    if not api_key and not args.no_ai:
        print("Error: EasyRouter API key is required for AI generation.")
        print("Provide it via --api-key or set EASYROUTER_API_KEY environment variable.")
        print("Get your key at https://easyrouter.io/")
        print("Tip: Use --no-ai to skip AI and use a Picsum random cover instead.")
        sys.exit(1)

    # Auto-generate output path with timestamp if not overridden
    output_path = args.output
    if "pending" in output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            os.path.dirname(output_path), f"cover_{timestamp}.png"
        )

    result = generate_cover(
        title=args.title,
        output_path=output_path,
        api_key=api_key or "",
        custom_prompt=args.prompt,
        image_input=args.image,
        size=args.size,
        quality=args.quality,
        style=args.style,
        allow_fallback=args.allow_fallback,
        no_ai=args.no_ai,
        base_url=args.base_url,
        model=args.model,
    )

    if not result:
        sys.exit(2)


if __name__ == "__main__":
    main()
