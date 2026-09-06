#!/usr/bin/env python3
"""Fix one problematic segment: optional rewrite -> TTS -> flash regen -> dual-ASR
verify -> adopt on pass, auto-retry. See references/flash-recipe.md for the
repair-loop rationale (reword first, then same-text retry, then manual seconds).
Usage:
  fix_segment.py --workdir W --seg 15 --old "..." --new "..." [--seconds 7]
  fix_segment.py --workdir W --seg 19 --retry-only            # same text, new roll
  fix_segment.py --workdir W --seg 5 --verify-only            # just ASR-check existing mp4
Requires: $AGNES_API_KEY, $SILICONFLOW_API_KEY"""
import argparse, base64, difflib, json, math, os, subprocess, sys, time
import urllib.request, urllib.error

API_CREATE = "https://apihub.agnes-ai.com/v1/videos"
API_POLL = "https://apihub.agnes-ai.com/agnesapi"

def duri(p, m):
    return "data:%s;base64," % m + base64.b64encode(open(p, "rb").read()).decode()

def ffprobe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(r.stdout.strip())

def asr(wav, model):
    r = subprocess.run(["curl", "-s", "https://api.siliconflow.cn/v1/audio/transcriptions",
                        "-H", f"Authorization: Bearer {os.environ['SILICONFLOW_API_KEY']}",
                        "-F", f"model={model}", "-F", f"file=@{wav}"],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout).get("text", "")
    except Exception:
        return ""

def create_task(key, payload):
    for attempt in range(8):
        req = urllib.request.Request(API_CREATE, data=json.dumps(payload).encode(),
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())["video_id"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503):
                w = 45 * (attempt + 1); print(f"  create {e.code}, backoff {w}s", flush=True)
                time.sleep(w)
            else:
                raise
    raise RuntimeError("create retries exhausted")

def poll(key, vid):
    for _ in range(40):
        time.sleep(15)
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
            raise RuntimeError("task failed")
    raise RuntimeError("poll timeout")

def download(url, path):
    rq = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(rq, timeout=300) as r, open(path, "wb") as f:
        f.write(r.read())

def verify(mp4, line, tag):
    wav = f"{os.path.dirname(mp4)}/../qc_{tag}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-vn", "-acodec", "pcm_s16le", wav],
                   capture_output=True)
    texts = [asr(wav, m) for m in ("FunAudioLLM/SenseVoiceSmall", "TeleAI/TeleSpeechASR")]
    sims = [difflib.SequenceMatcher(None, line[:38], t[:38]).ratio() for t in texts]
    for name, t, s in zip(("SenseVoice", "TeleAI"), texts, sims):
        print(f"  {name} sim={s:.2f}: {t[:52]}", flush=True)
    sim_ok = sum(sims) / 2 >= 0.80 and min(sims) >= 0.72
    print("  >>> MANUAL CHECK the transcripts above for word repetition / gibberish tail —")
    print("      similarity alone passes single-word stutters (known blind spot).", flush=True)
    return sim_ok, texts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--seg", type=int, required=True)
    ap.add_argument("--old"); ap.add_argument("--new")
    ap.add_argument("--seconds", type=int, help="manual clip seconds (avoid blind ceil)")
    ap.add_argument("--voice", default="zh-CN-YunjianNeural")
    ap.add_argument("--retry-only", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()
    W, KEY = args.workdir, os.environ["AGNES_API_KEY"]
    segs = json.load(open(f"{W}/segments.json"))
    seg = segs[args.seg - 1]
    i = args.seg

    if args.verify_only:
        verify(f"{W}/segments/seg{i:02d}.mp4", seg["tts"], f"seg{i:02d}")
        return

    if args.old and args.new:
        assert args.old in seg["tts"], f"--old not found in seg{i} tts"
        seg["tts"] = seg["tts"].replace(args.old, args.new)
        srt = f"{W}/subs/src_seg{i:02d}.srt"
        r = subprocess.run(["uvx", "edge-tts", "--voice", args.voice, "--text", seg["tts"],
                            "--write-media", f"{W}/audio/seg{i:02d}.mp3", "--write-subtitles", srt],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-300:]
        d = ffprobe_dur(f"{W}/audio/seg{i:02d}.mp3")
        seg["dur"] = round(d, 3)
        seg["seconds"] = args.seconds if args.seconds else max(4, min(12, math.ceil(d)))
        json.dump(segs, open(f"{W}/segments.json", "w"), ensure_ascii=False, indent=1)
        print(f"seg{i:02d}: rewritten, tts {d:.2f}s -> seconds {seg['seconds']}")
    elif args.seconds:
        seg["seconds"] = args.seconds
        json.dump(segs, open(f"{W}/segments.json", "w"), ensure_ascii=False, indent=1)
        print(f"seg{i:02d}: seconds locked {args.seconds}")
    elif not args.retry_only:
        sys.exit("need --old/--new, --seconds, or --retry-only")

    img = f"{W}/frames/speaker_ref.jpg" if i == 1 else f"{W}/frames/last_seg{i-1:02d}.jpg"
    assert os.path.exists(img), f"missing reference frame {img}"
    prompt = ("真人演讲视频，竖构图。以<Picture 1>这张视频尾帧中人物当前的姿态、表情、服装和舞台场景为视频的起始画面，与上一镜头自然衔接。"
              "人物面向观众继续演讲，开口清晰连贯地说出下面这句中文台词：\n"
              f"【{seg['tts']}】\n"
              "说完这句台词后保持嘴部闭合不再说话。说话的音色、语气和语速与<Audio 1>中的语音完全一致，"
              "嘴部口型与台词内容逐字同步，视频音轨就是人物所说的这句台词。"
              "人物随内容配合自然的手势与表情，头部小幅移动，"
              "严格保持人物身份、脸型、发型、服装与舞台背景同<Picture 1>一致，"
              "固定机位，画面稳定，写实风格，无字幕，无水印，无文字")
    payload = {"model": "agnes-video-2.5-flash", "prompt": prompt, "mode": "reference",
               "images": [duri(img, "image/jpeg")],
               "audios": [duri(f"{W}/audio/seg{i:02d}.mp3", "audio/mpeg")],
               "seconds": str(seg["seconds"]), "size": "720P", "aspect_ratio": "9:16", "n": 1}

    manifest = json.load(open(f"{W}/manifest.json")) if os.path.exists(f"{W}/manifest.json") else {}
    for attempt in range(3):
        try:
            vid = create_task(KEY, payload)
            print(f"seg{i:02d}: task {vid} (attempt {attempt+1})", flush=True)
            url = poll(KEY, vid)
            tmp = f"{W}/segments/seg{i:02d}_fix.mp4"
            download(url, tmp)
            sim_ok, texts = verify(tmp, seg["tts"], f"seg{i:02d}_fix")
            if sim_ok:
                subprocess.run(["mv", tmp, f"{W}/segments/seg{i:02d}.mp4"], check=True)
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.10",
                                "-i", f"{W}/segments/seg{i:02d}.mp4", "-update", "1",
                                "-frames:v", "1", "-vf", "scale='min(720,iw)':-2",
                                "-q:v", "3", f"{W}/frames/last_seg{i:02d}.jpg"], check=True)
                vd = ffprobe_dur(f"{W}/segments/seg{i:02d}.mp4")
                manifest[str(i)] = {"video_id": vid, "video_dur": round(vd, 2),
                                    "audio_dur": seg["dur"], "ok": True, "audio_src": "flash"}
                json.dump(manifest, open(f"{W}/manifest.json", "w"), indent=1)
                print(f"seg{i:02d}: ADOPTED ({vd:.2f}s) — confirm transcripts look clean, then rebuild")
                return
            print(f"seg{i:02d}: verify failed, retrying", flush=True)
        except Exception as e:
            print(f"seg{i:02d}: attempt error {e}", flush=True); time.sleep(30)
    print(f"seg{i:02d}: NOT ADOPTED — try rewording (--old/--new) or manual --seconds")

if __name__ == "__main__":
    main()
