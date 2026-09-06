#!/usr/bin/env python3
"""Split page-level speech into flash-safe chunks; TTS each chunk.
Reads {workdir}/../speech.json -> writes {workdir}/segments.json, audio/segNN.mp3, subs/src_segNN.srt.
Chunk width must stay in [20,56] CJK-width: flash fills gibberish when the line is
much shorter than the clip, and lines over 56 chars exceed the 12s ceiling."""
import argparse, json, math, os, re, subprocess, sys

def split_sentences(text):
    return [p for p in re.split(r"(?<=[。？！；])", text) if p.strip()]

def dwidth(t):
    return sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in t)

def dur(path):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--voice", default="zh-CN-YunjianNeural")
    ap.add_argument("--min-chars", type=int, default=20)
    ap.add_argument("--max-chars", type=int, default=53)
    args = ap.parse_args()

    W = args.workdir
    os.makedirs(f"{W}/audio", exist_ok=True)
    os.makedirs(f"{W}/subs", exist_ok=True)
    script = json.load(open(f"{W}/../speech.json"))

    segments = []
    for item in script:
        sents = []
        for sent in split_sentences(item["tts"]):
            if len(sent) > args.max_chars:  # hard-split over-long sentence at commas
                cur = ""
                for piece in re.split(r"(?<=[，、：——])", sent):
                    if len(cur) + len(piece) > args.max_chars and cur:
                        sents.append(cur); cur = piece
                    else:
                        cur += piece
                if cur: sents.append(cur)
            else:
                sents.append(sent)
        # greedy fill
        chunks, cur = [], ""
        for s in sents:
            if len(cur) + len(s) > args.max_chars and cur:
                chunks.append(cur); cur = s
            else:
                cur += s
        if cur: chunks.append(cur)
        # fold tiny chunks into neighbours (<= max_chars + 3 tolerance)
        lim = args.max_chars + 3
        changed = True
        while changed:
            changed = False
            for i, c in enumerate(chunks):
                if len(c) >= args.min_chars: continue
                if i > 0 and len(chunks[i-1]) + len(c) <= lim:
                    chunks[i-1] += chunks.pop(i); changed = True; break
                if i < len(chunks) - 1 and len(c) + len(chunks[i+1]) <= lim:
                    chunks[i] += chunks.pop(i+1); changed = True; break
        for c in chunks:
            segments.append({"page": item["page"], "tts": c.strip()})

    for i, seg in enumerate(segments, 1):
        mp3 = f"{W}/audio/seg{i:02d}.mp3"
        srt = f"{W}/subs/src_seg{i:02d}.srt"
        ok = False
        for _ in range(3):
            r = subprocess.run(["uvx", "edge-tts", "--voice", args.voice, "--text", seg["tts"],
                                "--write-media", mp3, "--write-subtitles", srt],
                               capture_output=True, text=True)
            if r.returncode == 0 and os.path.getsize(mp3) > 1000:
                ok = True; break
        if not ok:
            sys.exit(f"TTS failed seg{i}")
        d = dur(mp3)
        seg["dur"] = round(d, 3)
        seg["seconds"] = max(4, min(12, math.ceil(d)))
        print(f"seg{i:02d} p{seg['page']:02d} {d:5.2f}s -> {seg['seconds']}s  {seg['tts'][:24]}")

    json.dump(segments, open(f"{W}/segments.json", "w"), ensure_ascii=False, indent=1)
    bad = [(i+1, len(s["tts"])) for i, s in enumerate(segments)
           if len(s["tts"]) < args.min_chars or len(s["tts"]) > args.max_chars + 3]
    total = sum(s["dur"] for s in segments)
    print(f"{len(segments)} chunks, speech {total:.1f}s | out-of-range: {bad if bad else 'NONE'}")
    if bad:
        print("WARNING: fix these chunks by editing speech.json wording (see SKILL.md rule 2/3)")

if __name__ == "__main__":
    main()
