#!/usr/bin/env python3
"""
飞书发送视频脚本 - 将视频URL或本地文件发送为飞书可播放的 media 消息。

流程（URL模式）：
1. 下载视频到临时文件
2. 提取封面图（第一帧）和真实时长
3. 上传视频 + 封面到飞书，拿到 file_key / image_key
4. 发送 media 消息给用户

流程（本地文件模式，--video-path）：
1. 直接使用本地已有视频文件（跳过下载）
2. 若同时传入 --cover-path 则跳过封面提取
3. 上传视频 + 封面到飞书
4. 发送 media 消息给用户

用法：
    # URL 模式（需要带 token 才能访问的 URL 不建议用此模式）
    python3 feishu_send_video.py --video-url <url> --open-id <user_open_id> --duration <秒>

    # 本地文件模式（推荐，尤其适用于内部 URL 视频）
    python3 feishu_send_video.py --video-path <local_mp4> --open-id <user_open_id> --duration <秒>
    python3 feishu_send_video.py --video-path <local_mp4> --cover-path <local_jpg> --open-id <user_open_id> --duration <秒>
"""

import argparse
import json
import os
import sys
import tempfile

import requests


# =============================================================================
# 读取飞书配置
# =============================================================================

def get_feishu_credentials():
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        feishu = config.get("channels", {}).get("feishu", {})
        app_id = feishu.get("appId")
        app_secret = feishu.get("appSecret")
        if not app_id or not app_secret:
            print("Error: 飞书 appId / appSecret 未配置")
            sys.exit(1)
        return app_id, app_secret
    except Exception as e:
        print(f"Error: 读取配置失败: {e}")
        sys.exit(1)


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    token = resp.json().get("tenant_access_token")
    if not token:
        print(f"Error: 获取飞书 token 失败: {resp.text}")
        sys.exit(1)
    return token


# =============================================================================
# 下载视频
# =============================================================================

def download_video(video_url: str, dest: str):
    print(f"下载视频中...")
    resp = requests.get(video_url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    size_mb = os.path.getsize(dest) / 1024 / 1024
    print(f"视频下载完成: {size_mb:.1f}MB")


# =============================================================================
# 提取封面图 + 精确时长（依赖 opencv，可选）
# =============================================================================

def _ensure_opencv():
    """确保 opencv 可用，不可用则自动安装。返回是否成功。"""
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        pass

    import subprocess
    print("opencv-python-headless 未安装，正在自动安装...")
    for pip_args in [
        [sys.executable, "-m", "pip", "install", "opencv-python-headless", "--user", "-q"],
        [sys.executable, "-m", "pip", "install", "opencv-python-headless", "--break-system-packages", "-q"],
    ]:
        result = subprocess.run(pip_args, capture_output=True, text=True)
        if result.returncode == 0:
            print("opencv-python-headless 安装成功")
            return True
        print(f"尝试安装失败: {result.stderr.strip()}")

    print("Error: opencv-python-headless 自动安装失败，视频将无封面图")
    return False


def extract_cover_and_duration(video_path: str, cover_path: str, fallback_duration_s: int):
    """返回 (cover_path_or_None, duration_ms)"""
    if not _ensure_opencv():
        return None, fallback_duration_s * 1000

    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration_ms = int(frames / fps * 1000) if fps > 0 else fallback_duration_s * 1000
        ret, frame = cap.read()
        cap.release()
        if ret:
            cv2.imwrite(cover_path, frame)
            print(f"封面已提取: {cover_path}, 时长: {duration_ms}ms")
            return cover_path, duration_ms
        else:
            return None, duration_ms
    except Exception as e:
        print(f"Warning: 提取封面失败: {e}")
        return None, fallback_duration_s * 1000


# =============================================================================
# 上传到飞书
# =============================================================================

def upload_video(token: str, video_path: str, duration_ms: int) -> str:
    with open(video_path, "rb") as f:
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("video.mp4", f, "video/mp4")},
            data={"file_type": "mp4", "file_name": "video.mp4", "duration": str(duration_ms)},
            timeout=120,
        )
    data = resp.json()
    file_key = data.get("data", {}).get("file_key")
    if not file_key:
        print(f"Error: 上传视频失败: {resp.text}")
        sys.exit(1)
    print(f"视频已上传: file_key={file_key}")
    return file_key


def upload_cover(token: str, cover_path: str) -> str | None:
    try:
        with open(cover_path, "rb") as f:
            resp = requests.post(
                "https://open.feishu.cn/open-apis/im/v1/images",
                headers={"Authorization": f"Bearer {token}"},
                files={"image": ("cover.jpg", f, "image/jpeg")},
                data={"image_type": "message"},
                timeout=30,
            )
        image_key = resp.json().get("data", {}).get("image_key")
        if image_key:
            print(f"封面已上传: image_key={image_key}")
        return image_key
    except Exception as e:
        print(f"Warning: 封面上传失败: {e}")
        return None


# =============================================================================
# 发送 media 消息
# =============================================================================

def send_media_message(token: str, open_id: str, file_key: str, image_key: str | None):
    content = {"file_key": file_key}
    if image_key:
        content["image_key"] = image_key

    resp = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "receive_id": open_id,
            "msg_type": "media",
            "content": json.dumps(content),
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        print(f"Error: 发送消息失败: {resp.text}")
        sys.exit(1)
    print("✅ 视频消息已发送")


# =============================================================================
# 主流程
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="发送视频到飞书")
    parser.add_argument("--video-url", help="视频在线URL（与 --video-path 二选一）")
    parser.add_argument("--video-path", help="本地视频文件路径（与 --video-url 二选一，优先级更高）")
    parser.add_argument("--cover-path", help="本地封面图路径（可选，配合 --video-path 使用时跳过封面提取）")
    parser.add_argument("--open-id", required=True, help="接收用户的飞书 open_id")
    parser.add_argument("--duration", type=int, default=5, help="视频时长（秒），用于 fallback")
    args = parser.parse_args()

    if not args.video_url and not args.video_path:
        print("Error: 必须提供 --video-url 或 --video-path 其中之一")
        sys.exit(1)

    app_id, app_secret = get_feishu_credentials()
    token = get_tenant_access_token(app_id, app_secret)

    file_key = None

    if args.video_path:
        # 本地文件模式：直接上传，跳过下载
        if not os.path.exists(args.video_path):
            print(f"Error: 视频文件不存在: {args.video_path}")
            sys.exit(1)

        cover = None
        duration_ms = args.duration * 1000

        if args.cover_path and os.path.exists(args.cover_path):
            # 已有封面，直接用
            cover = args.cover_path
            print(f"使用已有封面: {cover}")
        else:
            # 提取封面 + 精确时长
            cover_path = args.video_path.replace(".mp4", "_cover_tmp.jpg")
            cover, duration_ms = extract_cover_and_duration(args.video_path, cover_path, args.duration)

        # 上传视频
        file_key = upload_video(token, args.video_path, duration_ms)

        # 上传封面（可选）
        image_key = upload_cover(token, cover) if cover else None

        # 发送 media 消息
        send_media_message(token, args.open_id, file_key, image_key)

    else:
        # URL 模式：下载到临时目录再上传
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            cover_path = os.path.join(tmpdir, "cover.jpg")

            # 1. 下载视频
            download_video(args.video_url, video_path)

            # 2. 提取封面 + 时长
            cover, duration_ms = extract_cover_and_duration(video_path, cover_path, args.duration)

            # 3. 上传视频
            file_key = upload_video(token, video_path, duration_ms)

            # 4. 上传封面（可选）
            image_key = upload_cover(token, cover) if cover else None

            # 5. 发送 media 消息
            send_media_message(token, args.open_id, file_key, image_key)

    print(json.dumps({"success": True, "file_key": file_key}, ensure_ascii=False))


if __name__ == "__main__":
    main()
