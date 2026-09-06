# Agnes Video 2.5 Flash 数字人配方（实测）

## API

- 创建：`POST https://apihub.agnes-ai.com/v1/videos`（key=`$AGNES_API_KEY`）
- 轮询：`GET https://apihub.agnes-ai.com/agnesapi?video_id=<VID>&model_name=agnes-video-2.5-flash`
  **必须带 `Authorization: Bearer` 头**；完成状态 `completed/succeeded`，下载 URL 在响应**顶层 `url`** 字段（不是 data[0]）
- 顶层字段：`model:"agnes-video-2.5-flash"` / `prompt` / `mode:"reference"` / `images:[...]` / `audios:[...]` / `seconds:"4"–"12"`（字符串整数）/ `size:"720P"` / `aspect_ratio:"9:16"` / `n:1`
- 本地文件直接 **data URI**（`data:image/jpeg;base64,...` / `data:audio/mpeg;base64,...`）——图片压到 ≤300KB，音频用 edge-tts mp3（天然小）
- 免费档：并发 2–3，超限 429 → 指数退避 `45s×attempt`；单任务 2–6 分钟；flash 免费额度充足

## Reference 模式 prompt 模板（关键：台词必须嵌入）

```
真人演讲视频，竖构图。以<Picture 1>这张{照片|视频尾帧}中人物当前的姿态、表情、服装和舞台场景为视频的起始画面{，与上一镜头自然衔接}。
人物面向观众继续演讲，开口清晰连贯地说出下面这句中文台词：
【{台词}】
说完这句台词后保持嘴部闭合不再说话。说话的音色、语气和语速与<Audio 1>中的语音完全一致，
嘴部口型与台词内容逐字同步，视频音轨就是人物所说的这句台词。
人物随内容配合自然的手势与表情，头部小幅移动，
严格保持人物身份、脸型、发型、{服装描述}与舞台背景同<Picture 1>一致，
固定机位，画面稳定，写实风格，无字幕，无水印，无文字
```

- `audios` 只作音色/语速参考——**不嵌台词 = 模型编造乱码语音**
- 语音与参考音频**时间轴逐点对齐**（实测偏差 <0.02s）→ TTS 的 SRT 可零偏移用作字幕
- 输出 720×1280 h264+aac，实际时长 ≈ seconds + 0.2~0.5s

## 链式续接策略

- 页内：抽尾帧 `ffmpeg -sseof -0.1 -i seg.mp4 -update 1 -frames:v 1 -q:v 3 last.jpg`（压缩 ≤720 宽）作为下段 `images` 首图
- 页首：锚定原始讲师照片（页切换=姿态重置，恰好对应 PPT 翻页，导播切镜头观感）
- 由此可**页级并行**（11 条链并发 2–3 跑），比全局单链快 2 倍多

## 已知劣化模式与修复

| 现象 | 根因 | 修复 |
|---|---|---|
| 段首/段尾出现编造乱码语音 | 台词明显短于视频（空隙>0.5s） | 改写加长台词填满；seconds 勿机械 ceil（台词 5.06s 时锁 5 不给 6） |
| 词重复（"在在""抖音在抖音在"） | 句头"名词+在"等模式 | 改句式（如"至于……则是……"）触发新发音路径 |
| 叠词/双同词连读劣化（"真真切切""相似…相似"） | 拗口音节序列 | 换音节交替的表达（"看得见、摸得着"） |
| 同文本复现同样误读 | 生成/参考双确定性 | 必须先改措辞；或同文本重试碰随机性 |

修复循环次序：①改写（换发音+调时长）→ ②同文本重试 → ③手动锁 seconds。每轮双 ASR 验证。

## 验证（双 ASR 交叉）

```
curl -s https://api.siliconflow.cn/v1/audio/transcriptions \
  -H "Authorization: Bearer $SILICONFLOW_API_KEY" \
  -F "model=TeleAI/TeleSpeechASR" -F "file=@seg.wav"
```

- SenseVoiceSmall：快，但**叠词高发误判**（"真真切切"听成三连"切"）
- TeleAI：**判定以此为准**
- 双模型一致听写（如都听到"在在"）才算真缺陷；sim 阈值：均值 ≥0.80 且低值 ≥0.72，但**重复/乱码要人工看转录文本**——相似度对单字重复不敏感
- 判别性标志验证：改过措辞的段，必须在新音轨听出**新措辞**才算替换生效

## 兜底

flash 连续 3 次失败 → `~/.agents/skills/agnes-video/scripts/generate.py`（agnes-video-2.5，无声，`--seconds` 取 8n+1 合法帧数）+ 合成时铺 TTS（manifest `audio_src:"tts"`）。口型稍差，语音保证精准。
