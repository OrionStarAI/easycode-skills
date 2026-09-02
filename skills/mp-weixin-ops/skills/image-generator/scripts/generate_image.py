#!/usr/bin/env python3
"""
Generate or edit images using EasyRouter.io (gpt-image-2 model).

API key is required. Provide it via:
  --api-key CLI arg, OR
  EASYROUTER_API_KEY environment variable

Usage:
  # Text-to-image
  python generate_image.py "a futuristic city at sunset" --api-key sk-xxx

  # Image-to-image (edit existing image)
  python generate_image.py "make it raining" --image path/to/image.png --api-key sk-xxx

  # Via env var
  export EASYROUTER_API_KEY=sk-xxx
  python generate_image.py "a cat in space"
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
DEFAULT_SIZE = "1024x1024"
OUTPUT_DIR = "outputs"

# gpt-image-2 supported sizes
SUPPORTED_SIZES = ["1024x1024", "1024x1536", "1536x1024", "auto"]

# Old size aliases → gpt-image-2 sizes
SIZE_ALIASES = {
    "0.5K": "1024x1024",
    "1024x1024": "1024x1024",
    "1024x1792": "1024x1536",
    "1792x1024": "1536x1024",
    "2K": "1536x1024",
    "4K": "1536x1024",
}

# =============================================================================
# API Key
# =============================================================================

def get_api_key(cli_key: Optional[str] = None) -> str:
    """Get API key from CLI arg or EASYROUTER_API_KEY env var."""
    api_key = cli_key or os.environ.get("EASYROUTER_API_KEY")
    if not api_key:
        print("Error: EasyRouter API key is required.")
        print("Provide it via --api-key or set EASYROUTER_API_KEY environment variable.")
        print("Get your key at https://easyrouter.io/")
        sys.exit(1)
    return api_key


# =============================================================================
# Helpers
# =============================================================================

def resolve_size(size: str) -> str:
    """Map CLI --size to a gpt-image-2 supported size."""
    if size in SUPPORTED_SIZES:
        return size
    return SIZE_ALIASES.get(size, "1024x1024")


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


def save_image(img_data: bytes, output_path: str, output_path_override: bool, is_edit: bool) -> str:
    """Save image bytes to file, return absolute path."""
    if not output_path_override:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "edit" if is_edit else "image"
        filename = f"{prefix}_{timestamp}.png"
        output_path = os.path.join(
            os.path.dirname(__file__), "..", OUTPUT_DIR, filename
        )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(img_data)
    return os.path.abspath(output_path)


def extract_image_data(result: dict) -> Optional[bytes]:
    """Extract image bytes from API response."""
    data_list = result.get("data") or []
    if not data_list:
        # Fallback shapes
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


# =============================================================================
# Core Generation
# =============================================================================

def generate_image(
    prompt: str,
    output_path: str,
    api_key: str,
    size: str = DEFAULT_SIZE,
    output_path_override: bool = False,
    image_inputs: Optional[list] = None,
    quality: str = "auto",
    style: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
) -> Optional[str]:
    """Generate or edit an image via EasyRouter.io, with auto retry."""
    retry_delays = [5, 10, 20]
    for attempt in range(1, max_retries + 1):
        result = _generate_once(
            prompt, output_path, api_key, size, output_path_override,
            image_inputs, quality, style, base_url, model,
        )
        if result:
            if attempt > 1:
                print(f"  ✅ Succeeded on attempt {attempt}")
            return result
        if attempt < max_retries:
            delay = retry_delays[attempt - 1]
            print(f"  ⚠️  Attempt {attempt}/{max_retries} failed, retrying in {delay}s...")
            time.sleep(delay)
    print(f"  ❌ Failed after {max_retries} attempts")
    return None


def _generate_once(
    prompt: str,
    output_path: str,
    api_key: str,
    size: str,
    output_path_override: bool,
    image_inputs: Optional[list],
    quality: str,
    style: Optional[str],
    base_url: str,
    model: str,
) -> Optional[str]:
    """Single attempt."""
    is_edit = bool(image_inputs)
    mode = "image-edit (img2img)" if is_edit else "text-to-image"
    print(f"Mode: {mode}")
    print(f"Model: {model}")
    print(f"Prompt: '{prompt}'")
    if image_inputs:
        print(f"Reference images: {image_inputs}")

    api_size = resolve_size(size)
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        if is_edit:
            # Image edit: use /images/edits (multipart form)
            endpoint = f"{base_url}/images/edits"
            print(f"Calling API: POST {endpoint}")

            # Use first reference image for edit
            ref = image_inputs[0]
            if ref.startswith("http://") or ref.startswith("https://"):
                # Download URL image to temp file
                img_resp = requests.get(ref, timeout=60)
                img_resp.raise_for_status()
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(img_resp.content)
                    tmp_path = tmp.name
                try:
                    b64, mime = image_to_b64(tmp_path)
                finally:
                    os.unlink(tmp_path)
            elif ref.startswith("data:"):
                import re
                match = re.match(r"data:image/([^;]+);base64,(.+)", ref)
                if not match:
                    print("Error: Invalid data URI for reference image")
                    return None
                b64 = match.group(2)
                mime = f"image/{match.group(1)}"
            else:
                abs_path = os.path.abspath(ref)
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
                "size": api_size,
            }
            if quality and quality != "auto":
                data["quality"] = quality
            if style:
                data["style"] = style
        else:
            # Text-to-image: use /images/generations (JSON)
            endpoint = f"{base_url}/images/generations"
            print(f"Calling API: POST {endpoint}")

            payload = {
                "model": model,
                "prompt": prompt,
                "n": 1,
                "size": api_size,
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
                print("⚠️  图片生成失败：账户额度不足或请求过于频繁，请稍后重试或充值。")
            elif response.status_code in (401, 403):
                print("❌ 认证失败：API Key 无效或已过期，请检查你的 EasyRouter API Key。")
            elif response.status_code == 500:
                print("⚠️  图片生成失败：服务暂时不稳定，请稍后重试。")
            elif "safety" in backend_msg.lower() or "content" in backend_msg.lower():
                print("⚠️  图片生成失败：该内容被安全过滤拦截，请修改描述后重试。")
            else:
                print(f"❌ 请求失败（{response.status_code}）：{backend_msg}")
            return None

        result = response.json()
        img_data = extract_image_data(result)
        if not img_data:
            print(f"Error: No image data in response. Response: {str(result)[:300]}")
            return None

        abs_path = save_image(img_data, output_path, output_path_override, is_edit)
        print(f"IMAGE_RESULT: {abs_path}")
        return abs_path

    except requests.HTTPError as e:
        try:
            err_detail = e.response.json()
        except Exception:
            err_detail = e.response.text
        print(f"Error: API request failed [{e.response.status_code}]: {err_detail}")
        return None
    except Exception as e:
        print(f"Error generating image: {e}")
        return None


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate or edit images using EasyRouter.io (gpt-image-2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Text-to-image (with --api-key)
  python generate_image.py "a futuristic city at sunset" --api-key sk-xxx

  # Via env var
  export EASYROUTER_API_KEY=sk-xxx
  python generate_image.py "a cat in space"

  # Image-to-image (edit mode)
  python generate_image.py "make it rainy" --image ./photo.png --api-key sk-xxx

  # Custom size and quality
  python generate_image.py "sunset cityscape" --size 1536x1024 --quality high --api-key sk-xxx
        """,
    )
    parser.add_argument("prompt", help="Text prompt or editing instruction")
    parser.add_argument(
        "--api-key",
        help="EasyRouter API key (or set EASYROUTER_API_KEY env var)",
    )
    parser.add_argument(
        "--image", "-i",
        dest="images",
        action="append",
        metavar="IMAGE",
        help="Reference image for edit mode (local path or URL). Can be used multiple times (max 4).",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: auto-generated in outputs/)",
    )
    parser.add_argument(
        "--size", "-s",
        default="1024x1024",
        help="Image size: 1024x1024, 1024x1536, 1536x1024, auto (default: 1024x1024)",
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

    if args.images and len(args.images) > 4:
        print("Error: Maximum 4 reference images allowed.")
        sys.exit(1)

    api_key = get_api_key(args.api_key)

    if args.output:
        output_path = args.output
        has_override = True
    else:
        output_path = os.path.join(
            os.path.dirname(__file__), "..", OUTPUT_DIR, "pending.png"
        )
        has_override = False

    generate_image(
        prompt=args.prompt,
        output_path=output_path,
        api_key=api_key,
        size=args.size,
        output_path_override=has_override,
        image_inputs=args.images,
        quality=args.quality,
        style=args.style,
        base_url=args.base_url,
        model=args.model,
    )


if __name__ == "__main__":
    main()
