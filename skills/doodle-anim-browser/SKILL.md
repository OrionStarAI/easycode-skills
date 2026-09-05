---
name: doodle-anim-browser
description: "零安装涂鸦动画渲染通道：用 Easy Code 内置浏览器替代 Playwright 逐帧渲染 doodle-anim 模板并合成 MP4，只需 Node + ffmpeg。当用户环境没有 playwright/chromium、希望零下载快速出片，或要求用内置浏览器采集 Canvas 动画帧时使用。"
license: MIT
---

# doodle-anim-browser — 零安装涂鸦动画渲染通道（Easy Code 内置浏览器版）

本技能是 `doodle-anim` 技能的**零 Playwright 替代渲染通道**：复用 Easy Code Desktop
内置浏览器（Electron Chromium）作为逐帧渲染器，只需要 Node（≥18）+ ffmpeg 两个常见依赖，
不需要安装 playwright / chromium（约省 150MB 下载）。

与 doodle-anim 共用同一套模板（templates/*.html）。本技能目录不重复携带模板，
使用时通过 `--templates` 指向 doodle-anim 技能目录的 templates/，或任何含模板的目录。

## 何时用我

- 目标机器没有装 playwright/chromium，或不想装
- 只想快速出一条片，接受比 Playwright 慢约 25% 的采集速度
- 想要"所见即所得"——采集过程就在你眼前的浏览器标签里发生

## 原理（3 分钟看懂）

```
Easy Code 内置浏览器（Electron Chromium 视图）
  └─ 加载 templates/xxx.html（自包含动画页，暴露 window.__seek(t)）
  └─ 注入采集脚本：for 每帧: __seek(t) → canvas.toBlob(PNG) → fetch POST /frame
                                                        │（二进制直传，无 base64）
server.mjs（Node，帧接收器）                              ▼
  └─ POST /frame：req.pipe(fs.createWriteStream) 流式落盘
  └─ GET 其余路径：静态服务 templates/ 目录
ffmpeg：PNG 序列 → MP4 → 混音（TTS/BGM/SFX 可复用 doodle-anim 管线产物）
```

确定性保证：与 Playwright 版用的是**同一个渲染引擎**（Blink + Skia），页面遵守
doodle-anim 的确定性契约（seeded PRNG + `__seek` 纯函数），同 seed 逐帧字节一致。

## 工作流（三步）

### 第 1 步：起帧接收服务器

```bash
node server.mjs <模板目录> <帧输出目录> [端口]
# 例：
node server.mjs ../doodle-anim/templates ./frames 8739
```

### 第 2 步：内置浏览器加载页面并注入采集脚本

用 `browser_navigate` 打开 `http://localhost:8739/explainer.html`（或 doodle.html 等），
然后用 `browser_run_script` 注入采集脚本（完整脚本见 capture-snippet.js）：

```js
(async () => {
  const FPS = 30, N = 856;               // 帧数 = 时长 × fps
  // 若是 explainer：先 __setScenes(timeline) 重建时间轴，见下文"解说片时间轴"
  const canvas = document.querySelector('canvas');
  const jobs = [];
  for (let i = 0; i < N; i++) {
    window.__seek(i / FPS);
    const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));
    jobs.push(fetch('/frame', { method: 'POST',
      headers: { 'X-Frame-Name': `f${String(i).padStart(5,'0')}.png` }, body: blob }));
    if (jobs.length >= 32) { await Promise.all(jobs); jobs.length = 0; }  // 分批 await，防连接堆积
  }
  await Promise.all(jobs);
  return 'done';
})()
```

**性能纪律（实测教训，务必遵守）**：
- 一定要**一次调用跑完整个循环**。Agent 逐批调用（如 60 帧/批 ×14 次）会引入
  每批之间的编排空闲，实测 856 帧从 47s 恶化到 160s。
- `browser_run_script` 有 ~15s 超时。超过 15s 的采集，调用会报超时错误，但
  **页面里的循环不会中断，会继续跑完**——不要慌，用 shell 时间戳或数落盘帧数确认进度。
- toBlob 二进制 + 32 帧分批 await 是当前最优平衡；实测 55ms/帧（856 帧共 47s）。

### 第 3 步：ffmpeg 合成

```bash
# 无声视频轨
ffmpeg -y -framerate 30 -i frames/f%05d.png -pix_fmt yuv420p silent.mp4
# 有解说配音时：TTS/BGM/SFX 可复用 doodle-anim 管线的 audio 目录（见下文"混音"）
```

## 解说片（explainer）时间轴重建

`render-explainer.mjs`（Playwright 版）的镜头时长公式：`dur = max(语音时长 + 1.0, 3.2)`。
内置浏览器版要在页面里重建同一时间轴，才能对齐配音：

```js
// lines = 每句配音的实测秒数（ffprobe 测 line*.wav）
const story = [ { visual: 'bedroom', line: '……' }, … ];
const timeline = story.map((s, i) => ({ ...s, dur: Math.max(lines[i] + 1.0, 3.2) }));
window.__setScenes(timeline);   // 返回总时长
```

混音公式（与 Playwright 版一致）：每句 `adelay=t0*1000`，BGM×0.30，SFX×0.85，
`amix normalize=0` 后整体 `volume=1.6`，`apad` 补齐到总时长。

## 实测数据（2026-09，M 系列 Mac）

| 通道 | 856帧(28.5s@30fps)采集 | 单帧 |
|------|----------------------|------|
| Playwright（doodle-anim 原版） | 37.5s | 44ms |
| 本技能 v2（单次调用+二进制） | 47s | 55ms |
| 本技能 v1（分批调用+base64，反例） | 160s | 187ms |

## 故障排查

- **采集超时报错**：正常现象（>15s 的调用必超时），循环仍在跑；数帧目录文件数即可。
- **帧不连续/缺帧**：检查 `X-Frame-Name` 的编号格式与 ffmpeg 的 `%05d` 匹配。
- **画面与 Playwright 版不一致**：确认 URL 参数（seed/count 等）和时间轴完全一致。
- **端口冲突**：换端口即可，浏览器侧 fetch 用相对路径 `/frame`，无需改脚本。
