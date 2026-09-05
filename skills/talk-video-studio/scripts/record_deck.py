#!/usr/bin/env python3
"""Record the HTML deck with a scripted timeline (playwright as programmatic
screen recording — CSS animations only exist when captured live).
Page dwell time = sum of that page's segment video durations from manifest.json.
Requires: playwright (npm i -g playwright && npx playwright install chromium), deck.html
exposing goToPage(n) per references/html-deck.md.
Writes {workdir}/ppt_recording.mp4 (30fps h264)."""
import argparse, json, os, subprocess, sys

def ffprobe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return -1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--deck", required=True, help="path to deck.html")
    ap.add_argument("--enter-wait", type=float, default=1.2,
                    help="seconds to let enter animations settle after each page turn")
    args = ap.parse_args()
    W = args.workdir
    deck = os.path.abspath(args.deck)

    segs = json.load(open(f"{W}/segments.json"))
    manifest = json.load(open(f"{W}/manifest.json"))
    pages = {}
    for i, s in enumerate(segs, 1):
        info = manifest.get(str(i), {})
        if not info.get("ok"):
            sys.exit(f"segment {i} not ok — finish generation before recording")
        pages[s["page"]] = pages.get(s["page"], 0.0) + info["video_dur"]
    total = sum(pages.values())
    print("page timeline:", {p: round(d, 2) for p, d in sorted(pages.items())},
          f"total {total:.2f}s")

    js = """
const { chromium } = require('playwright');
(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'deckrec-'));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1,
    recordVideo: { dir: tmp, size: { width: 1280, height: 720 } }
  });
  const tNewPage = Date.now();
  const page = await ctx.newPage();
  const video = page.video();
  await page.goto('file://' + process.argv[2]);
  await page.waitForTimeout(parseInt(process.argv[5] * 1000));  // load+settle, counted as lead
  const n = await page.evaluate(() => document.querySelectorAll('.slide').length);
  if (n !== parseInt(process.argv[3], 10)) { console.error('slide count mismatch: ' + n); process.exit(2); }
  const timeline = JSON.parse(process.argv[4]);
  const t0 = Date.now(); let cum = 0;
  for (let p = 1; p <= n; p++) {                 // absolute-time scheduling: no drift build-up
    await page.evaluate(k => goToPage(k - 1), p);
    cum += timeline[p];
    const wait = t0 + cum * 1000 - Date.now();
    if (wait > 0) await page.waitForTimeout(wait);
  }
  await ctx.close(); await browser.close();
  const vp = await video.path();
  fs.copyFileSync(vp, process.argv[6]);          // tmp dir is wiped after node exits
  console.log(JSON.stringify({ lead_ms: t0 - tNewPage, webm: process.argv[6] }));
})();
"""
    script = f"""
const fs = require('fs'), os = require('os'), path = require('path');
{js}
"""
    # enter-wait eats into dwell; keep it inside the page budget (timeline already counts it)
    # the runner script lives NEXT TO this file so require('playwright') resolves from
    # the skill's own node_modules (global npm often lacks perms on this machine)
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".rec_runner.js")
    with open(script_path, "w") as f:
        f.write(script)
    try:
        r = subprocess.run(["node", script_path, deck, str(len(pages)),
                            json.dumps({str(k): v for k, v in pages.items()}),
                            str(args.enter_wait), f"{W}/ppt_raw.webm"],
                           capture_output=True, text=True)
    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)
    webm = f"{W}/ppt_raw.webm"
    if r.returncode != 0 or not os.path.exists(webm):
        sys.exit(f"recording failed:\n{r.stderr[-800:]}\n{r.stdout[-400:]}")
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
        lead = info.get("lead_ms", 0) / 1000.0
    except Exception:
        lead = 0.0
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, lead - 0.05):.3f}",
                    "-i", webm, "-t", f"{total:.3f}",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
                    f"{W}/ppt_recording.mp4"], check=True)
    rd = ffprobe_dur(f"{W}/ppt_recording.mp4")
    print(f"ppt_recording.mp4: {rd:.2f}s (speaker track {total:.2f}s, diff {abs(rd-total):.2f}s)")
    if abs(rd - total) > 1.5:
        print("WARNING: recording duration drifts from speaker track >1.5s — check animations/timeline")

if __name__ == "__main__":
    main()
