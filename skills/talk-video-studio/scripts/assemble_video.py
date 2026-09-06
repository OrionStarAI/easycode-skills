#!/usr/bin/env python3
"""Assemble the conference-style talk video.
Stage norm     : per-seg mp4 -> uniform 720x1280 30fps + audio (flash=native / tts=laid)
Stage concat   : speaker track
Stage title    : PIL pre-rendered title strip (drawtext fontfile paths break -> tofu)
Stage final    : 1920x1080 bg + deck recording left + speaker right + title + ASS subs
Inputs: {workdir}/{segments.json, manifest.json, segments/, audio/, ppt_recording.mp4,
         subs/global.ass, title.txt}
Output: {workdir}/../成片.mp4"""
import argparse, json, os, subprocess, sys

VENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1200:]); sys.exit(f"ffmpeg failed: {cmd[:4]}")

def ffprobe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(r.stdout.strip())

def load(W):
    segs = json.load(open(f"{W}/segments.json"))
    man = json.load(open(f"{W}/manifest.json"))
    out = []
    for i, s in enumerate(segs, 1):
        info = man[str(i)]
        if not info.get("ok"): sys.exit(f"seg{i:02d} missing")
        out.append({"i": i, "dur": info["video_dur"], "src": info.get("audio_src", "flash")})
    return out

def norm(W):
    os.makedirs(f"{W}/norm", exist_ok=True)
    for s in load(W):
        i, vd, src = s["i"], s["dur"], s["src"]
        outp = f"{W}/norm/seg{i:02d}.mp4"
        if os.path.exists(outp): continue
        vf = "scale=720:1280:flags=lanczos,fps=30,format=yuv420p"
        if src == "flash":
            run(["ffmpeg", "-y", "-v", "error", "-i", f"{W}/segments/seg{i:02d}.mp4",
                 "-t", f"{vd:.3f}", "-vf", vf, *VENC,
                 "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", outp])
        else:  # silent fallback: lay the TTS mp3, pad to clip length
            run(["ffmpeg", "-y", "-v", "error",
                 "-i", f"{W}/segments/seg{i:02d}.mp4", "-i", f"{W}/audio/seg{i:02d}.mp3",
                 "-t", f"{vd:.3f}", "-vf", vf, *VENC,
                 "-filter_complex", "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,apad[a]",
                 "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k", outp])
        print(f"norm seg{i:02d} ok ({src})", flush=True)

def concat(W):
    with open(f"{W}/norm/list.txt", "w") as f:
        for s in load(W):
            f.write(f"file '{W}/norm/seg{s['i']:02d}.mp4'\n")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", f"{W}/norm/list.txt", "-c", "copy", f"{W}/speaker_track.mp4"])

def title_png(W, text):
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for p, idx in (("/System/Library/Fonts/STHeiti Medium.ttc", 0),
                   ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
                   ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0)):
        if os.path.exists(p):
            font = ImageFont.truetype(p, 34, index=idx); break
    assert font, "no CJK font found for title"
    tmp = Image.new("RGBA", (10, 10)); d = ImageDraw.Draw(tmp)
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    img = Image.new("RGBA", (w + 8, h + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((4 - box[0], 5 - box[1]), text, font=font, fill=(234, 234, 242, 255),
           stroke_width=1, stroke_fill=(16, 16, 20, 160))
    img.save(f"{W}/title.png")
    return img.size[0]

def final(W, out, layout):
    title_txt = f"{W}/title.txt"
    if not os.path.exists(title_txt):
        sys.exit("write a one-line session title into video-work/title.txt first")
    tw = title_png(W, open(title_txt).read().strip())
    tx = 16 + (1280 - tw) // 2
    sw = layout["speaker_w"]  # right column width (608 default)
    fc = (
        f"color=c=0x101014:s=1920x1080:r=30:d=720[bg];"
        f"[0:v]scale=1280:720:flags=lanczos[p];"
        f"[1:v]scale={sw}:1080:flags=lanczos[s];"
        f"movie={W}/title.png,format=rgba[t];"
        f"[bg][p]overlay=16:180:shortest=1[v0];"
        f"[v0][s]overlay={1920 - sw}:0[v1];"
        f"[v1][t]overlay={tx}:70[v2];"
        f"[v2]subtitles={W}/subs/global.ass:fontsdir=/System/Library/Fonts[v]"
    )
    run(["ffmpeg", "-y", "-v", "error",
         "-i", f"{W}/ppt_recording.mp4", "-i", f"{W}/speaker_track.mp4",
         "-filter_complex", fc, "-map", "[v]", "-map", "1:a:0",
         *VENC, "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", out])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--stage", default="all", choices=["norm", "concat", "final", "all"])
    ap.add_argument("--speaker-w", type=int, default=608)
    args = ap.parse_args()
    W = args.workdir
    out = args.out or f"{os.path.dirname(W.rstrip('/'))}/成片.mp4"
    if not os.path.exists(f"{W}/ppt_recording.mp4"):
        sys.exit("missing ppt_recording.mp4 — run record_deck.py first")
    if args.stage in ("norm", "all"): norm(W)
    if args.stage in ("concat", "all"): concat(W)
    if args.stage in ("final", "all"): final(W, out, {"speaker_w": args.speaker_w})
    print("stage", args.stage, "->", out if args.stage in ("final", "all") else "done")

if __name__ == "__main__":
    main()
