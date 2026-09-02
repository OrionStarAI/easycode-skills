#!/usr/bin/env python3
"""
EasyClaw Video - Generate videos using EasyClaw Video API.

No extra API key needed — uses your EasyClaw credits.
"""

import argparse
import json
import os
import sys
import time

import requests

# =============================================================================
# Configuration
# =============================================================================

API_URL = "https://api.easyclaw.work/api/v1/videos/generate"
DEFAULT_MODEL = "doubao-seedance-1-5-pro-251215"   # 默认旗舰版，支持音频
PRO_FAST_MODEL = "doubao-seedance-1-0-pro-fast-251015"  # 快速版，不支持 generate_audio
DEFAULT_RESOLUTION = "720p"
DEFAULT_RATIO = "16:9"
DEFAULT_DURATION = 6
TIMEOUT = 600  # 10 minutes max

# 支持 generate_audio / draft / duration=-1 的模型
AUDIO_SUPPORTED_MODELS = {"doubao-seedance-1-5-pro-251215"}

MODEL_CAPABILITIES = {
    # 原有 Seedance（已上线逻辑）
    "doubao-seedance-1-5-pro-251215": {
        "supports_resolution": True,
        "supports_ratio": True,
        "supports_adaptive_ratio": True,
        "supports_duration": True,
        "supports_image_inputs": True,
        "supports_generate_audio": True,
    },
    "doubao-seedance-1-0-pro-fast-251015": {
        "supports_resolution": True,
        "supports_ratio": True,
        "supports_adaptive_ratio": True,
        "supports_duration": True,
        "supports_image_inputs": True,
        "supports_generate_audio": False,
    },
    "doubao-seedance-1-0-pro-250528": {
        "supports_resolution": True,
        "supports_ratio": True,
        "supports_adaptive_ratio": True,
        "supports_duration": True,
        "supports_image_inputs": True,
        "supports_generate_audio": False,
    },
    "doubao-seedance-1-0-lite-t2v-250428": {
        "supports_resolution": True,
        "supports_ratio": True,
        "supports_adaptive_ratio": False,
        "supports_duration": True,
        "supports_image_inputs": False,
        "supports_generate_audio": False,
    },
    "doubao-seedance-1-0-lite-i2v-250428": {
        "supports_resolution": True,
        "supports_ratio": True,
        "supports_adaptive_ratio": False,
        "supports_duration": True,
        "supports_image_inputs": True,
        "supports_generate_audio": False,
    },
    # Veo 系（通过 EasyRouter 路由，Skill 端只使用官方模型名）
    "veo-3.1-fast": {
        "supports_resolution": True,
        "supports_ratio": True,
        "supports_adaptive_ratio": False,
        "supports_duration": True,
        "supports_image_inputs": True,
        "supports_generate_audio": False,
    },
}

SUPPORTED_MODELS = tuple(MODEL_CAPABILITIES.keys())


# =============================================================================
# Helper Functions
# =============================================================================


def normalize_model(model: str | None) -> str:
    """Validate and return the requested model. Exit with error if unsupported."""
    if not model:
        return DEFAULT_MODEL

    model = model.strip()
    if model in MODEL_CAPABILITIES:
        return model

    print(f"Error: Unsupported model '{model}'.")
    print(f"Available models: {', '.join(SUPPORTED_MODELS)}")
    sys.exit(1)

def get_api_key() -> str:
    """Get EasyClaw API key from openclaw.json config."""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")

    if not os.path.exists(config_path):
        print("Error: OpenClaw config not found.")
        print(f"Expected: {config_path}")
        print("Please run: openclaw onboard")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        api_key = (
            config.get("models", {})
            .get("providers", {})
            .get("deepv-easyclaw", {})
            .get("apiKey")
        )
        if not api_key:
            print("Error: deepv-easyclaw apiKey not found in openclaw.json.")
            sys.exit(1)
        return api_key
    except Exception as e:
        print(f"Error reading openclaw.json: {e}")
        sys.exit(1)



def _ensure_pillow() -> bool:
    """确保 Pillow 可用，不可用则自动安装。返回是否成功。安装失败时静默降级，不中断流程。"""
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        pass

    import subprocess
    print("Pillow 未安装，正在自动安装（用于大图压缩）...")
    for pip_args in [
        [sys.executable, "-m", "pip", "install", "Pillow", "--user", "-q"],
        [sys.executable, "-m", "pip", "install", "Pillow", "--break-system-packages", "-q"],
    ]:
        result = subprocess.run(pip_args, capture_output=True, text=True)
        if result.returncode == 0:
            print("Pillow 安装成功")
            return True
        print(f"尝试安装失败: {result.stderr.strip()}")

    print("Warning: Pillow 自动安装失败，大图(>10MB)将跳过压缩直接发送，可能导致 API 报错")
    return False



def image_to_url(image_path: str, max_size_mb: float = 10.0) -> str:
    """
    Convert local image path to base64 data URI, or return URL as-is.
    Automatically compresses image if it exceeds max_size_mb (default 10MB).
    """
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path

    import base64
    has_pil = _ensure_pillow()
    try:
        from PIL import Image
        import io
    except ImportError:
        has_pil = False

    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)

    file_size_mb = os.path.getsize(image_path) / (1024 * 1024)

    if file_size_mb <= max_size_mb or not has_pil:
        if file_size_mb > max_size_mb and not has_pil:
            print(f"Warning: Image is {file_size_mb:.1f}MB, exceeds {max_size_mb}MB limit. Install Pillow to auto-compress: pip install Pillow")
        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
        mime = mime_map.get(ext, "jpeg")
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{mime};base64,{b64}"

    print(f"Image is {file_size_mb:.1f}MB, compressing to fit {max_size_mb}MB limit...")
    img = Image.open(image_path)

    max_dimension = 2048
    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    buf = io.BytesIO()
    quality = 85
    while quality >= 40:
        buf.seek(0)
        buf.truncate()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() / (1024 * 1024) <= max_size_mb:
            break
        quality -= 10

    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    compressed_mb = buf.tell() / (1024 * 1024)
    print(f"Compressed to {compressed_mb:.1f}MB (quality={quality})")
    return f"data:image/jpeg;base64,{b64}"



def build_video_payload(
    prompt: str,
    model: str,
    ratio: str,
    ratio_explicit: bool,
    resolution: str,
    duration: int,
    generate_audio: bool,
    image: str | None,
    last_image: str | None,
) -> tuple[dict, list[str]]:
    caps = MODEL_CAPABILITIES.get(model, {
        "supports_resolution": True,
        "supports_ratio": True,
        "supports_adaptive_ratio": False,
        "supports_duration": True,
        "supports_image_inputs": False,
        "supports_generate_audio": False,
    })
    warnings = []

    payload = {
        "prompt": prompt,
        "model": model,
    }

    if caps.get("supports_duration"):
        payload["duration"] = duration

    if caps.get("supports_resolution"):
        payload["resolution"] = resolution

    if caps.get("supports_ratio"):
        final_ratio = ratio
        payload["ratio"] = final_ratio

    image_inputs = []
    if image or last_image:
        if caps.get("supports_image_inputs"):
            if image:
                image_inputs.append({"url": image_to_url(image), "role": "first_frame"})
            if last_image:
                image_inputs.append({"url": image_to_url(last_image), "role": "last_frame"})
            payload["image_inputs"] = image_inputs
            if image_inputs and not ratio_explicit and caps.get("supports_adaptive_ratio"):
                payload["ratio"] = "adaptive"
        else:
            warnings.append(f"model {model} does not support image inputs, ignored")

    if caps.get("supports_generate_audio"):
        payload["generate_audio"] = generate_audio
    elif generate_audio is False and model in MODEL_CAPABILITIES:
        warnings.append(f"model {model} does not support generate_audio, ignored")

    return payload, warnings



def generate_video(
    prompt: str,
    model: str = DEFAULT_MODEL,
    ratio: str = DEFAULT_RATIO,
    ratio_explicit: bool = False,
    resolution: str = DEFAULT_RESOLUTION,
    duration: int = DEFAULT_DURATION,
    generate_audio: bool = True,
    image: str = None,
    last_image: str = None,
) -> dict:
    """Generate a video and return result dict with video_url."""

    model = normalize_model(model)
    api_key = get_api_key()
    payload, warnings = build_video_payload(
        prompt=prompt,
        model=model,
        ratio=ratio,
        ratio_explicit=ratio_explicit,
        resolution=resolution,
        duration=duration,
        generate_audio=generate_audio,
        image=image,
        last_image=last_image,
    )

    for msg in warnings:
        print(f"Warning: {msg}")

    print(f"Generating video: '{prompt[:60]}...'" if len(prompt) > 60 else f"Generating video: '{prompt}'")
    audio_info = f"audio={'on' if generate_audio else 'off'}" if model in AUDIO_SUPPORTED_MODELS else "no-audio"
    print(f"Settings: {model} · {payload.get('resolution', resolution)} · {payload.get('ratio', ratio)} · {payload.get('duration', duration)}s · {audio_info}")
    print("This may take 1~3 minutes, please wait...")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    max_retries = 6
    retry_codes = {502, 503, 504}
    result = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            result = response.json()
            break
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait = 10 * attempt
                print(f"Request timed out (attempt {attempt}/{max_retries}), retrying in {wait}s...")
                time.sleep(wait)
                continue
            print("Error: Request timed out after all retries.")
            sys.exit(1)
        except requests.exceptions.HTTPError:
            if response.status_code in retry_codes and attempt < max_retries:
                wait = 10 * attempt
                print(f"Server returned {response.status_code} (attempt {attempt}/{max_retries}), retrying in {wait}s...")
                time.sleep(wait)
                continue
            try:
                err = response.json()
                msg = err.get("message") or err.get("detail") or str(err)
            except Exception:
                msg = response.text
            print(f"Error: API returned {response.status_code}: {msg}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    if result is None:
        print("Error: Failed after all retries.")
        sys.exit(1)

    video_url = result.get("video_url")
    if not video_url:
        print(f"Error: No video URL in response: {result}")
        sys.exit(1)

    video_path = None
    try:
        import hashlib
        video_dir = os.path.expanduser("~/.openclaw/workspace/skills/generate-video/output")
        os.makedirs(video_dir, exist_ok=True)
        task_id = result.get("task_id", "")
        if task_id:
            video_filename = f"{task_id}.mp4"
        else:
            video_filename = f"video_{hashlib.md5(video_url.encode()).hexdigest()[:12]}.mp4"
        video_path = os.path.join(video_dir, video_filename)

        print(f"Downloading video to {video_path}...")
        dl_resp = requests.get(video_url, timeout=120)
        if dl_resp.status_code in (401, 403):
            print("Download requires authorization, retrying with Bearer token...")
            dl_resp = requests.get(
                video_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=120,
            )
        dl_resp.raise_for_status()
        with open(video_path, "wb") as f:
            f.write(dl_resp.content)
        print(f"Video downloaded: {video_path} ({len(dl_resp.content) / (1024*1024):.1f}MB)")
    except Exception as e:
        print(f"Warning: Failed to download video: {e}")
        video_path = None

    cover_path = None
    duration_ms = 0
    if video_path:
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            if fps > 0:
                duration_ms = int(frames / fps * 1000)
            ret, frame = cap.read()
            if ret:
                cover_path = video_path.replace(".mp4", "_cover.jpg")
                cv2.imwrite(cover_path, frame)
                print(f"Cover image saved: {cover_path}")
            cap.release()
            print(f"Video duration: {duration_ms}ms ({duration_ms/1000:.1f}s)")
        except ImportError:
            print("Warning: opencv not installed, no cover image. Install with: pip install opencv-python-headless")
        except Exception as e:
            print(f"Warning: Failed to extract cover: {e}")

    output = {
        "video_url": video_url,
        "video_path": video_path,
        "cover_path": cover_path,
        "duration": result.get("duration", duration),
        "duration_ms": duration_ms,
        "resolution": result.get("resolution", resolution),
        "ratio": result.get("ratio", ratio),
        "credits_usage": result.get("credits_usage", 0),
        "generate_audio": result.get("generate_audio", generate_audio),
    }
    print(json.dumps(output, ensure_ascii=False))

    return result


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate videos using EasyClaw Video API")
    parser.add_argument("prompt", help="Text description of the video to generate")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            "模型ID（默认: %(default)s）。传入不支持的模型名会直接报错退出。\n"
            "Seedance 系: doubao-seedance-1-5-pro-251215, doubao-seedance-1-0-pro-fast-251015, doubao-seedance-1-0-pro-250528\n"
            "Veo 系: veo-3.1-fast\n"
            "Lite 系: doubao-seedance-1-0-lite-t2v-250428, doubao-seedance-1-0-lite-i2v-250428\n"
            "注：具体走 EasyRouter 还是原供应商由 Server 端自动决定，Skill 无需关心。"
        ),
    )
    parser.add_argument("--ratio", default=DEFAULT_RATIO,
                        choices=["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
                        help="Aspect ratio (default: 16:9)")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION,
                        choices=["480p", "720p", "1080p"],
                        help="Video resolution (default: 720p)")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION,
                        help="Duration in seconds (default: 6)")
    parser.add_argument("--no-audio", action="store_true",
                        help="Disable audio generation")
    parser.add_argument("--image", help="First frame image (local path or URL)")
    parser.add_argument("--last-image", help="Last frame image (local path or URL)")
    args = parser.parse_args()

    generate_video(
        prompt=args.prompt,
        model=args.model,
        ratio=args.ratio,
        ratio_explicit=(args.ratio != DEFAULT_RATIO),
        resolution=args.resolution,
        duration=args.duration,
        generate_audio=not args.no_audio,
        image=args.image,
        last_image=args.last_image,
    )


if __name__ == "__main__":
    main()
