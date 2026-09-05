---
name: talk-video-studio
description: "把任意材料（一段话、文档、网址、一堆资料）制成行业大会演讲视频的完整流水线：知识文档 → HTML 动态 PPT → 演讲稿 → AI 数字人讲解视频（含声音+口型）→ 左 PPT 右人物带字幕的成片。用户说做成演讲视频/分享视频/数字人讲解/把文档或文章做成 PPT 再做成视频/做一个会讲话的 presenter 时使用，即使没提具体工具名。"
upstream: tangshuang/skills
upstreamPath: talk-video-studio
upstreamSha: c12dbdd248fd341e66fae8839b02b4da5736e6bf
author: tangshuang
---

# Talk Video Studio

输入一段内容 / 一个文档 / 一个网址 / 一堆资料，产出"行业大会演讲视频"：
**左侧 PPT 播放（HTML 动态效果，屏幕录制）+ 右侧 AI 数字人讲师（9:16，自带语音与口型）+ 句级字幕（原始文案写法）**，音画同步、翻页与讲稿逐页对齐。

```
{主题}/                          ← 一切产物放在主题子目录，勿污染根目录
├── 知识文档.md                  ← 阶段1产出
├── deck.html                    ← 阶段2产出（HTML PPT，单文件）
├── speech.json                  ← 阶段3产出（页级讲稿，tts+display 双版本）
├── 成片.mp4                     ← 最终产物
└── video-work/                  ← 中间产物
    ├── segments.json            ← 分镜清单（权威时间轴）
    ├── manifest.json            ← 每段视频生成状态
    ├── audio/segNN.mp3          ← TTS 参考音频
    ├── subs/                    ← SRT/ASS 字幕
    ├── frames/                  ← 人物照片+各段尾帧
    ├── segments/segNN.mp4       ← 数字人视频段
    ├── norm/                    ← 标准化段
    └── ppt_recording.mp4        ← PPT 屏幕录制
```

## 铁律（每次都要遵守）

1. **TTS 音色性别必须与人物照片对齐**。人物人设（性别）在生成照片前敲定，之后 TTS 音色、照片、视频人物三者一致。映射：中文男 `zh-CN-YunjianNeural`（演讲激情风）/ 女 `zh-CN-XiaoxiaoNeural`（`--rate=+5%`）；英文男 `en-US-AndrewNeural` / 女 `en-US-AriaNeural`。
2. **讲稿拆段：每段 20–56 个全角字符宽（≈4.2–11.9s）**。低于 20 字 → flash 会在剩余时间编造乱码语音；高于 56 字 → 超出 12s 上限。
3. **台词时长 ≈ 视频实际时长**（模型输出普遍比请求 seconds 长 0.2–0.5s）。空隙 >0.5s 就有段首/段尾乱码填充风险。**seconds 不要机械 ceil**——台词刚过整数线（如 5.06s）时手动锁回下限（5），让台词塞满实际输出。
4. **多阶段流水线防"假成功"**：某阶段失败后，后续阶段可能拿旧中间产物跑通。每阶段的验证必须用**判别性标志**（只有新内容才会出现的东西），不能靠同义内容抽检。
5. 字幕显示**原始文案**（阿拉伯数字、原术语），不是朗读稿；但句子内容跟随语音（改写过的台词按新措辞显示）。
6. 视频段音轨用 **flash 自带语音**（口型同源）；`manifest.json` 的 `audio_src` 留有 `tts` 外铺开关作兜底。

## 流程

### 阶段 0 · 取材

- 网址 → `web_reader webReader`（或 WebFetch）抓正文，落 `原始材料.md`
- 文件/一堆资料 → 通读后合并整理，事实性数据标注出处
- 若材料是纯观点/自媒体来源，先核实关键事实；无法核实的部分在知识文档中标注

### 阶段 1 · 知识文档 `知识文档.md`

把材料泛化为结构化知识文档：主题定义 → 核心概念（每个配"是什么/为什么重要/一个具体例子"）→ 关键数据（带来源）→ 方法/流程 → 总结金句。要求：每节有具体的人/事/数，删掉空话；这是 PPT 与讲稿的共同源头，宁精勿滥（对应 8–12 页 PPT 的信息量）。

### 阶段 2 · HTML PPT `deck.html`

**读 `references/html-deck.md`** 后制作。要点：单文件 HTML、16:9（1280×720 逻辑画布）、每页 `<section class="slide">`、CSS/JS 进场动画（录制时才能被捕捉，这正是弃用 pptxgenjs 静帧的原因）、支持键盘与 `goToPage(n)` 双控。配色从主题派生（BACKGROUND→PRIMARY→ACCENT 三角色），PingFang SC 字体，深色封面/结尾 + 浅色内容页。

### 阶段 3 · 演讲稿 `speech.json`

按 PPT 页逐页写讲稿（页 1 对应开场，末页对应收尾致谢）。语速按 **4.8 汉字/秒** 估时长，每页 30–90 字。每页两个字段：

```json
{"page": 1, "tts": "大家好！……二零一八年……", "display": "大家好！……2018 年……"}
```

- `tts` = 朗读稿：**数字逐位/改读中文**（2018→二零一八，25Mb→二十五兆），多音字、易误读词预替换；edge-tts 对同一文本确定性输出——**改发音必须先改措辞**
- `display` = 原始文案（数字、术语书面写法），字幕还原用
- 避开拗口音节序列：叠词（真真切切）、双同词连读（相似的人喜欢相似）、句头"名词+在"（抖音在排序）——都是 flash 复述劣化高发区

### 阶段 4 · 分镜 + TTS + 人物照片

```bash
# 拆段（读 speech.json → segments.json + audio/ + 词级 SRT）
python3 scripts/tts_segments.py --workdir video-work --voice zh-CN-YunjianNeural
```

人物照片（agnes-image，`--ratio 9:16 --size 2K`）：真实感讲师站行业大会舞台、面向观众、讲解手势、深色背景虚化光斑**不含文字**；压缩到 ≤300KB JPG 作参考图（`frames/speaker_ref.jpg`）。

### 阶段 5 · 数字人视频段（agnes-video-2.5-flash）

**先读 `references/flash-recipe.md`**（API 配方与全部坑）。核心：reference 模式，`images=[参考图]`（首段=照片/页首=照片锚定/页内=上段尾帧）+ `audios=[该段 TTS]`（音色语速参考）+ **台词嵌入 prompt**（不嵌台词必出乱码语音）。

```bash
python3 scripts/gen_chain.py --workdir video-work          # 页级并行链全量生成（页内尾帧续接）
```

免费档并发 2–3，429 指数退避；28 段约 70 分钟。**完成后必须逐段抽检**（`fix_segment.py --verify-only`），发现词重复/乱码按修复循环处理：

```bash
# 改写台词 → 重 TTS → 重生成 → 双 ASR 自动验证（不达标自动重试）
python3 scripts/fix_segment.py --workdir video-work --seg 15 \
    --old "多维特征可以自动交叉组合" --new "多维特征能够自动交叉组合" [--seconds 7]
# 不改文本只重试（利用生成随机性）：
python3 scripts/fix_segment.py --workdir video-work --seg 19 --retry-only
```

修复循环次序：①改写措辞（换发音路径+撑时长）→ ②同文本重试 → ③手动锁 seconds。验证用双 ASR 交叉（SenseVoice 叠词高发误判，TeleAI 为准；双模型一致听写才算真缺陷）。

### 阶段 6 · PPT 屏幕录制 `video-work/ppt_recording.mp4`（已实测：时长零漂移）

用**控制脚本 + 屏幕录制**按时间顺序捕捉 HTML 动态播放（时间轴 = `segments.json` 按页聚合的 `manifest.json` video_dur）：

```bash
python3 scripts/record_deck.py --workdir video-work --deck deck.html
```

playwright（已随 skill 安装在 skill 目录的 node_modules，脚本自动解析；chromium 在 `~/Library/Caches/ms-playwright`，缺了用 `PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright npx playwright install chromium` 补）做程序化屏幕录制：绝对时间轴排程翻页（防页间延迟累积）+ lead 测量回传裁剪（去掉加载空屏）。产物时长应与人物轨零漂移；**差 >0.5s 先排查再进合成**。

### 阶段 7 · 字幕 + 合成

```bash
python3 scripts/build_subs.py --workdir video-work      # 句级字幕+原始文案还原+宽度控制
python3 scripts/assemble_video.py --workdir video-work  # 布局合成+标题条+烧录字幕
```

- 字幕：ASS，句级拆分（时间按字符宽比例分摊）、单句 >26 全角宽折行、MarginR 限左区、顶部标题条用 **PIL 预渲染 PNG**（drawtext 的 fontfile 路径常不存在→豆腐块）
- 布局：1920×1080，右栏 608×1080 人物，左区 PPT 居中 + 底部字幕 + 顶部标题（ffmpeg `overlay`，勿用 xstack——不允许层叠）
- 还原替换表写 `video-work/replace.json`（本项目数字/术语的 tts→display 对照），脚本内置残留校验（仍含中文数字串即中止）

## 最终 QC（缺一不可）

1. **时长**：三轨（人物/录制/字幕）总长一致，差 <0.5s
2. **ASR 抽检**：首/中/尾 + 全部修复过的段，TeleAI 转录对照台词
3. **翻页对齐**：每页时间中点抽帧，PPT 区域与 `deck` 对应页像素比对（HTML 录制允许动画中差，取停留态）
4. **判别标志**：改过的台词必须在新音轨中听出新措辞
5. 交付：成片路径 + 时长 + 页数/段数 + 修复记录摘要

失败兜底：flash 连续 3 次失败 → agnes-video-2.5 无声生成（skill helper）+ 后期铺 TTS（`audio_src: tts`），口型稍差但语音保证精准。
