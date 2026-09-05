#!/usr/bin/env python3
"""Build global ASS subtitles from per-segment edge-tts SRTs.
- cue expansion: sentence-level split, time proportional to char width
- original-copy restoration via {workdir}/replace.json (spoken -> written pairs)
- auto-space at CJK<->latin boundaries, fold lines over 26 CJK-width
- subtitle box constrained to the LEFT (deck) region via MarginL/MarginR
Reads segments.json + manifest.json + subs/src_segNN.srt (+ replace.json) -> subs/global.ass"""
import argparse, json, os, re, sys

MAXW = 26

def parse_srt(path):
    items = []
    txt = open(path, encoding="utf-8").read().strip()
    for block in re.split(r"\n\s*\n", txt):
        lines = block.splitlines()
        if len(lines) < 2: continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m: continue
        g = list(map(int, m.groups()))
        t0 = g[0]*3600 + g[1]*60 + g[2] + g[3]/1000
        t1 = g[4]*3600 + g[5]*60 + g[6] + g[7]/1000
        items.append((t0, t1, "".join(lines[2:])))
    return items

def dwidth(t):
    return sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in t)

def split_sentences(text):
    parts, cur = [], ""
    for ch in text:
        cur += ch
        if ch in "。？！；，、":
            parts.append(cur); cur = ""
    if cur: parts.append(cur)
    return parts

def sanitize(text, replaces):
    for a, b in replaces:
        text = text.replace(a, b)
    text = re.sub(r"(?<=[\u4e00-\u9fff，。？！；、])(?=[0-9A-Za-z&])", " ", text)
    text = re.sub(r"(?<=[0-9A-Za-z%&])(?=[\u4e00-\u9fff])", " ", text)
    return text

def fold_line(text):
    if dwidth(text) <= MAXW:
        return text
    lines, cur = [], ""
    for s in split_sentences(text):
        if not cur or dwidth(cur) + dwidth(s) <= MAXW:
            while dwidth(cur) + dwidth(s) > MAXW and len(s) > 1:
                take = s
                while dwidth(cur) + dwidth(take) > MAXW and len(take) > 1:
                    take = take[:-1]
                cur += take; s = s[len(take):]
                if s:
                    lines.append(cur); cur = ""
            cur += s
        else:
            lines.append(cur); cur = s
    if cur: lines.append(cur)
    return "\\N".join(l for l in lines if l)

def expand_cue(t0, t1, text):
    if dwidth(text) <= MAXW:
        return [(t0, t1, fold_line(text))]
    merged = []
    for s in split_sentences(text):
        if merged and dwidth(s) < 6:
            merged[-1] += s
        else:
            merged.append(s)
    total = sum(dwidth(s) for s in merged) or 1
    out, acc = [], 0.0
    for k, s in enumerate(merged):
        st = t0 + acc * (t1 - t0)
        acc += dwidth(s) / total
        en = t1 if k == len(merged) - 1 else t0 + acc * (t1 - t0)
        out.append((st, en, fold_line(s)))
    return out

def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--margin-r", type=int, default=664,
                    help="ASS MarginR; 664 keeps subs inside the left 1312px region on 1920")
    args = ap.parse_args()
    W = args.workdir
    segs = json.load(open(f"{W}/segments.json"))
    manifest = json.load(open(f"{W}/manifest.json"))
    replaces = []
    rp = f"{W}/replace.json"
    if os.path.exists(rp):
        replaces = [tuple(x) for x in json.load(open(rp))]
        print(f"replace.json: {len(replaces)} spoken->written pairs")

    leads = {}
    lp = f"{W}/sub_leads.json"
    if os.path.exists(lp):
        leads = json.load(open(lp))

    cues, t = [], 0.0
    for i, seg in enumerate(segs, 1):
        info = manifest.get(str(i), {})
        vd = info.get("video_dur")
        if not info.get("ok") or vd is None:
            sys.exit(f"segment {i} not ready/failed — resolve first")
        lead = leads.get(str(i), 0.0)
        for t0, t1, text in parse_srt(f"{W}/subs/src_seg{i:02d}.srt"):
            text = sanitize(text, replaces)
            cues.extend(expand_cue(t + lead + t0, t + lead + min(t1, vd), text))
        t += vd
    cues.sort()

    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Sub,PingFang SC,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4101014,"
        f"-1,0,0,0,100,100,0,0,3,2,1,2,56,{args.margin_r},46,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    with open(f"{W}/subs/global.ass", "w", encoding="utf-8") as f:
        f.write(header)
        for t0, t1, text in cues:
            if t1 - t0 < 0.15: t1 = t0 + 0.15
            bad = re.findall(r"[零一二三四五六七八九十]{2,}(?:年|ZB|兆)", text)
            if bad:
                sys.exit(f"subtitle still in spoken form {bad} in {text!r} — extend replace.json")
            f.write(f"Dialogue: 0,{ts(t0)},{ts(t1)},Sub,,0,0,0,,{text}\n")
    print(f"global.ass: {len(cues)} cues, total {t:.2f}s")

if __name__ == "__main__":
    main()
