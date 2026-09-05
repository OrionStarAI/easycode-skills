#!/usr/bin/env python3
"""Chain-generate talking-speaker segments with agnes-video-2.5-flash (reference mode).
Page-level parallel chains: within a page, tail-frame linked; page heads anchored on
the speaker photo (matches PPT page turns). In-flight cap + 429 backoff.
Requires: $AGNES_API_KEY, {workdir}/segments.json, frames/speaker_ref.jpg, audio/segNN.mp3
Writes: segments/segNN.mp4, frames/last_segNN.jpg, manifest.json"""
import argparse, base64, json, os, subprocess, sys, threading, time
import urllib.request, urllib.error

API_CREATE = "https://apihub.agnes-ai.com/v1/videos"
API_POLL = "https://apihub.agnes-ai.com/agnesapi"
POLL_INTERVAL, POLL_CAP = 15, 40

def duri(path, mime):
    return "data:%s;base64," % mime + base64.b64encode(open(path, "rb").read()).decode()

def ffprobe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(r.stdout.strip())

def extract_last(W, i):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.10",
                    "-i", f"{W}/segments/seg{i:02d}.mp4", "-update", "1", "-frames:v", "1",
                    "-vf", "scale='min(720,iw)':-2", "-q:v", "3", f"{W}/frames/last_seg{i:02d}.jpg"],
                   check=True)

def build_prompt(seg, head):
    line = seg["tts"]
    cont = ("以<Picture 1>这张照片中人物的站立姿态、表情、服装和舞台场景为视频的起始画面" if head else
            "以<Picture 1>这张视频尾帧中人物当前的姿态、表情、服装和舞台场景为视频的起始画面，与上一镜头自然衔接")
    return ("真人演讲视频，竖构图。" + cont +
            "。人物面向观众继续演讲，开口清晰连贯地说出下面这句中文台词：\n"
            f"【{line}】\n"
            "说完这句台词后保持嘴部闭合不再说话。说话的音色、语气和语速与<Audio 1>中的语音完全一致，"
            "嘴部口型与台词内容逐字同步，视频音轨就是人物所说的这句台词。"
            "人物随内容配合自然的手势与表情，头部小幅移动，"
            "严格保持人物身份、脸型、发型、服装与舞台背景同<Picture 1>一致，"
            "固定机位，画面稳定，写实风格，无字幕，无水印，无文字")

def create_task(key, prompt, img, audio, seconds):
    payload = {"model": "agnes-video-2.5-flash", "prompt": prompt, "mode": "reference",
               "images": [duri(img, "image/jpeg")], "audios": [duri(audio, "audio/mpeg")],
               "seconds": str(seconds), "size": "720P", "aspect_ratio": "9:16", "n": 1}
    body = json.dumps(payload).encode()
    for attempt in range(8):
        req = urllib.request.Request(API_CREATE, data=body,
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())["video_id"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503):
                w = 45 * (attempt + 1)
                print(f"    create {e.code}, backoff {w}s", flush=True); time.sleep(w)
            else:
                raise
    raise RuntimeError("create retries exhausted")

def poll_task(key, vid):
    for _ in range(POLL_CAP):
        time.sleep(POLL_INTERVAL)
        req = urllib.request.Request(f"{API_POLL}?video_id={vid}&model_name=agnes-video-2.5-flash",
                                     headers={"Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
        except Exception:
            continue
        if d.get("status") in ("completed", "succeeded"):
            return d.get("url")
        if d.get("status") == "failed":
            raise RuntimeError(f"task failed: {d.get('error')}")
    raise RuntimeError("poll timeout")

def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
        f.write(r.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--max-inflight", type=int, default=3)
    args = ap.parse_args()
    W, KEY = args.workdir, os.environ["AGNES_API_KEY"]
    for d in ("segments", "frames", "norm"):
        os.makedirs(f"{W}/{d}", exist_ok=True)
    if not os.path.exists(f"{W}/frames/speaker_ref.jpg"):
        sys.exit("missing frames/speaker_ref.jpg (generate speaker photo first)")

    segs = json.load(open(f"{W}/segments.json"))
    manifest = json.load(open(f"{W}/manifest.json")) if os.path.exists(f"{W}/manifest.json") else {}
    sema = threading.Semaphore(args.max_inflight)
    lock = threading.Lock()

    def run_segment(i, seg, img, head):
        mp4 = f"{W}/segments/seg{i:02d}.mp4"
        try:
            with sema:
                vid = create_task(KEY, build_prompt(seg, head), img,
                                  f"{W}/audio/seg{i:02d}.mp3", seg["seconds"])
                print(f"seg{i:02d}: task {vid}", flush=True)
                url = poll_task(KEY, vid)
            download(url, mp4)
            vd = ffprobe_dur(mp4)
            extract_last(W, i)
            with lock:
                manifest[str(i)] = {"video_id": vid, "video_dur": round(vd, 2),
                                    "audio_dur": seg["dur"], "ok": True, "audio_src": "flash"}
                json.dump(manifest, open(f"{W}/manifest.json", "w"), indent=1)
            print(f"seg{i:02d}: done {vd:.2f}s", flush=True)
        except Exception as e:
            print(f"seg{i:02d}: ERROR {e}", flush=True)

    def page_chain(page):
        idxs = [(i, s) for i, s in enumerate(segs, 1) if s["page"] == page]
        for k, (i, seg) in enumerate(idxs):
            if manifest.get(str(i), {}).get("ok") and os.path.exists(f"{W}/segments/seg{i:02d}.mp4"):
                if not os.path.exists(f"{W}/frames/last_seg{i:02d}.jpg"):
                    extract_last(W, i)
                continue
            img = f"{W}/frames/speaker_ref.jpg" if k == 0 else f"{W}/frames/last_seg{i-1:02d}.jpg"
            if k > 0 and not os.path.exists(img):
                print(f"p{page} seg{i:02d}: predecessor frame missing", flush=True); return
            run_segment(i, seg, img, head=(k == 0))

    threads = [threading.Thread(target=page_chain, args=(p,)) for p in sorted({s["page"] for s in segs})]
    for t in threads: t.start()
    for t in threads: t.join()
    ok = sum(1 for v in manifest.values() if v.get("ok"))
    print(f"ALL CHAINS DONE: {ok}/{len(segs)} segments ok", flush=True)

if __name__ == "__main__":
    main()
