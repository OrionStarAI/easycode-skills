// capture-snippet.js — paste into browser_run_script (Easy Code built-in browser).
// Captures N frames from a doodle-anim template page via __seek + toBlob, POSTs to server.mjs.
//
// Two flavors below. Keep FPS/N in sync with the ffmpeg step (-framerate FPS).

// ---- Flavor A: plain pages (doodle.html / faces.html / friends.html / mannay.html) ----
(async () => {
  const FPS = 30;
  const N = Math.floor(FPS * DURATION_SECONDS); // set me, e.g. 12s → 360
  const canvas = document.querySelector('canvas');
  const jobs = [];
  for (let i = 0; i < N; i++) {
    window.__seek(i / FPS);
    const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));
    jobs.push(fetch('/frame', {
      method: 'POST',
      headers: { 'X-Frame-Name': `f${String(i).padStart(5, '0')}.png` },
      body: blob,
    }));
    if (jobs.length >= 32) { await Promise.all(jobs); jobs.length = 0; }
  }
  await Promise.all(jobs);
  return `captured ${N} frames`;
})()

// ---- Flavor B: explainer.html — rebuild the narrated timeline first ----
// lines = measured voice-over durations in seconds (ffprobe each line*.wav).
// dur formula must match render-explainer.mjs: max(voice + 1.0, 3.2).
/*
(async () => {
  const FPS = 30;
  const lines = [3.08, 2.17]; // one entry per scene line
  const story = [
    { visual: 'bedroom', line: '……' },
    { visual: 'mirror',  line: '……' },
  ];
  const timeline = story.map((s, i) => ({ ...s, dur: Math.max(lines[i] + 1.0, 3.2) }));
  const total = window.__setScenes(timeline);
  const N = Math.ceil(total * FPS);
  const canvas = document.querySelector('canvas');
  const jobs = [];
  for (let i = 0; i < N; i++) {
    window.__seek(i / FPS);
    const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));
    jobs.push(fetch('/frame', {
      method: 'POST',
      headers: { 'X-Frame-Name': `f${String(i).padStart(5, '0')}.png` },
      body: blob,
    }));
    if (jobs.length >= 32) { await Promise.all(jobs); jobs.length = 0; }
  }
  await Promise.all(jobs);
  return `captured ${N} frames, total ${total.toFixed(2)}s`;
})()
*/

// NOTE: browser_run_script times out at ~15s. Longer captures keep running in the
// page after the error — verify progress by counting files in the frames directory.
