---
name: generate-video
description: 调用 EasyClaw 视频 API（豆包/Seedance模型）生成视频。仅适用于 EasyClaw.work 企业云端版。触发词：Seedance生视频、豆包生视频、国内模型生视频、EasyClaw生视频、帮我生成一个视频、生成一段视频、制作一个视频、把这张图片生成视频、让这张图动起来、Generate a video、Make a video。
---

# 视频生成技能

## 🚨 前置依赖检查（每次使用前必须执行，不可跳过）

> ❌ **绝对禁止：未检查依赖就直接调用脚本。**
> 缺少 `opencv-python-headless` 会导致视频发送时无封面图；缺少 `Pillow` 会导致大图压缩失败。脚本虽然会自动尝试安装，但**首次使用前应主动确认**。

**在调用任何脚本之前，必须先执行依赖检查：**

```bash
python3 -c "import cv2; import PIL; print('依赖正常')" 2>/dev/null || python3 -m pip install opencv-python-headless Pillow --user -q || python3 -m pip install opencv-python-headless Pillow --break-system-packages -q
```

**强制规则：**
- ❌ 不得跳过此步骤，即使你认为依赖已安装
- ❌ 看到视频无封面时，必须先确认 opencv 已安装，**不得只重发视频**
- ✅ 脚本内置自动安装逻辑，自动安装失败时会打印 Warning，但**不会中断流程**（会降级为无封面发送）
- ✅ 手动安装失败（如系统限制）时，改用：`pip install opencv-python-headless Pillow --break-system-packages`

用自然语言让 Bot 直接生成视频，支持文生视频和图生视频，中英文均可。

---

## 触发词

**精确触发（安装多个视频技能时推荐）：**
- 用 Seedance 生视频 / Seedance 生成视频
- 用豆包生视频 / Doubao 模型生视频
- 国内模型生视频 / 字节模型生视频
- EasyClaw 生视频

**通用触发：**
- 帮我生成一个视频...
- 生成一段视频...
- 制作一个视频...
- 把这张图片生成视频...
- 让这张图动起来...
- Generate a video of...
- Make a video of...

---

## 执行步骤

### 第一步：⚠️ 必须先告知用户稍等

> ⚠️ **此步骤必须执行，不可跳过！** 脚本运行期间 bot 无法发消息，如果不提前告知，用户会以为没有响应。

**先回复用户，再往下执行：**
> "好的，视频生成约需 1~3 分钟，稍等一下"

### 第二步：判断生成模式

**模式一：文生视频**（用户只给了文字描述）

根据用户描述选择比例：

| 用户说 | ratio |
|--------|-------|
| 没说 / 默认 | `16:9` |
| 竖版 / 手机 / 抖音 | `9:16` |
| 方形 | `1:1` |

分辨率默认 `720p`，追求质量用 `1080p`，快速预览用 `480p`。

**模型选择规则：**
- 默认情况下，用户无需知道或指定模型，直接走默认模型 `doubao-seedance-1-5-pro-251215`
- 若用户在聊天中明确指定模型名，则调用脚本时透传 `--model`
- 若用户指定了错误或不支持的模型名，**不要打断流程**，脚本会自动回退到默认模型继续生成
- 仅在用户明确要求时才切换到 Veo 系模型，例如：`veo-3.1-fast`（具体走哪个供应商由 Server 自动决定）

---

**模式二：图生视频**（用户发了图片）

图片要求：
- 格式：jpeg、png、webp、bmp、tiff、gif
- 尺寸：300px ~ 6000px，宽高比 0.4 ~ 2.5
- 大小：< 30MB
- **支持图片 URL 或直接发送本地图片**（脚本自动转 base64）

ratio 默认用 `adaptive`（自动适配图片比例），用户有特殊需求时再指定。

### 第三步：调用生视频脚本

> API Key 自动从 `~/.openclaw/openclaw.json` 的 `models.providers.deepv-easyclaw.apiKey` 读取，无需手动配置。

使用 `exec` 工具调用脚本，建议 timeout 设为 600（视频生成最长约10分钟）：

**文生视频（默认横版 16:9）：**
```
exec("python3 generate_video.py '视频描述'", timeout=600)
```

**竖版视频（9:16，适合抖音/手机）：**
```
exec("python3 generate_video.py '视频描述' --ratio 9:16", timeout=600)
```

**方形视频（1:1，适合社媒）：**
```
exec("python3 generate_video.py '视频描述' --ratio 1:1", timeout=600)
```

**指定时长（如10秒）：**
```
exec("python3 generate_video.py '视频描述' --duration 10", timeout=600)
```

**高清视频（1080p）：**
```
exec("python3 generate_video.py '视频描述' --resolution 1080p", timeout=600)
```

**图生视频（首帧）：**
```
exec("python3 generate_video.py '动作描述' --image 图片路径或URL --ratio adaptive", timeout=600)
```

**图生视频（首尾帧控制）：**
```
exec("python3 generate_video.py '动作描述' --image 首帧路径或URL --last-image 尾帧路径或URL", timeout=600)
```

**有声视频（指定1.5-pro模型）：**
```
exec("python3 generate_video.py '视频描述' --model doubao-seedance-1-5-pro-251215", timeout=600)
```

**Seedance 1.0 Pro（官方名称，Server 自动路由到最优供应商）：**
```
exec("python3 generate_video.py '视频描述' --model doubao-seedance-1-0-pro-250528", timeout=600)
```

**Veo 系（官方名称，仅 EasyRouter 支持）：**
```
exec("python3 generate_video.py '视频描述' --model veo-3.1-fast", timeout=600)
```

> 若用户指定了不支持的模型名，脚本会直接报错退出并列出可用模型列表。

> 脚本默认工作目录为 `~/.openclaw/workspace/skills/generate-video/scripts`

### 第四步：发送视频给用户

**飞书平台** — 调用专用脚本直接发可播放视频（脚本会自动安装 opencv 依赖，首次运行稍慢属正常）：
```
exec("python3 feishu_send_video.py --video-url <video_url> --open-id <用户open_id> --duration <duration>", timeout=180)
```
成功后追加文字：`🎉 视频生成成功！📊 时长 X 秒 · 分辨率 · 消耗积分 X`

**其他平台（或飞书失败时）** — 发链接：
```
🎉 视频生成成功！
📹 [点击查看/下载视频](完整video_url)
📊 时长 X 秒 · 分辨率 · 消耗积分 X
⚠️ 链接 24 小时后过期，请及时保存！
```
> `video_url` 是带签名超长链接，必须完整输出，禁止截断。

失败时：告知用户 `message` 字段中的具体原因。

---

## 常用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `prompt` | 视频描述（必填）| — |
| `--model` | 模型名 | `doubao-seedance-1-5-pro-251215` |
| `--resolution` | `480p` / `720p` / `1080p` | `720p` |
| `--ratio` | `16:9` / `9:16` / `1:1` / `4:3` / `3:4` / `21:9` / `adaptive` | `16:9` |
| `--duration` | 2~12 秒 | `6` |
| `--no-audio` | 关闭音频（默认有声，仅 1.5-pro 支持）| 默认开启 |
| `--image` | 图生视频首帧（URL 或 base64）| — |
| `--last-image` | 图生视频尾帧（URL 或 base64）| — |

---

## ⚠️ 注意事项

- 此技能**仅适用于 EasyClaw.work 企业云端版**，其他环境不可用
- API Key 从 `~/.openclaw/openclaw.json` 的 `models.providers.deepv-easyclaw.apiKey` 自动读取，无需手动配置
- 视频生成约需 **1~3 分钟**，务必提前告知用户
- 消耗用户自己的 EasyClaw 积分（约 20~50 积分/条）
- `generate_audio` 和 `duration=-1` 仅 `doubao-seedance-1-5-pro-251215` 支持，其他模型勿传
- `1.5-pro` 的 duration 范围是 **4~12秒**（其他模型是 2~12秒），默认5秒无问题
- 图生视频不传 `--ratio` 时脚本自动用 `adaptive` 适配图片比例；明确传 `--ratio 16:9` 则以用户指定为准
- 图生视频图片要求：
  - 格式：jpeg、png、webp、bmp、tiff、gif（1.5-pro 额外支持 heic、heif）
  - 宽高比：0.4 ~ 2.5（即不能太宽或太高）
  - 尺寸：最小 300px，最大 6000px
  - 大小：**小于 30MB**
  - 支持图片 URL 或 Base64 编码（格式：`data:image/png;base64,xxx`）

---

## 已知踩坑

| 问题 | 原因 | 解决 |
|------|------|------|
| `duration=-1` 报错 | 仅 1.5-pro 支持，其他模型会报错 | 指定 `--model doubao-seedance-1-5-pro-251215` 才能用 `-1` |
| 504 超时 | 视频生成慢，默认超时不够 | exec 调用时设 `timeout=600`，脚本内部已设 10 分钟 |
| 视频没有封面图 | opencv 未安装 | 脚本会自动安装，首次约多等 30 秒；若仍失败，手动执行 `pip install opencv-python-headless --user` |
| 视频链接打不开 | 链接被截断 | 必须完整输出带签名的超长链接 |
| 积分不足 | 余额不足 | 提示用户前往 EasyClaw.work 充值 |
| 图生视频 500 - 图片太小 | 图片尺寸小于 300px | 换正常尺寸图片（300~6000px）|
| 图生视频 500 - 图片太大 | 图片超过 30MB | 压缩图片后重试 |
| 图生视频 500 - 宽高比异常 | 宽高比超出 0.4~2.5 范围 | 裁剪图片使宽高比在范围内 |
| 图生视频失败 | 图片 URL 无法访问 | 确认图片 URL 公开可访问，飞书临时链接需鉴权 |
