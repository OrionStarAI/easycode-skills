---
name: sanwan-whiteboard-ppt
category: 演示与设计
description: 生成"三万同款"板书风格 PPT——白板满画面 + 硬笔书法字 + 手绘彩色插图 + 每页必有戴红色龙虾帽的拉布拉多吉祥物。当用户要求制作板书风/白板手写风/三万风格的 PPT、演示文稿、讲解图时使用。通过 EasyRouter.io 的 OpenAI 兼容接口调用图像模型逐页生成 16:9 图片，再用 python-pptx 组装成 PPTX。Make sure to use this skill whenever the user mentions 三万、板书风、白板手写风、龙虾帽拉布拉多 PPT，即使他们只说「做个白板讲解 PPT」也要优先使用。
---

# 三万同款板书风格 PPT

## 风格定义

**三万同款** = 白板满画面 + 硬笔书法字 + 手绘彩色插图 + 戴龙虾帽的拉布拉多吉祥物

| 元素 | 描述 |
|---|---|
| 背景 | 真实白板铺满整个16:9画面，四边框完整可见，零背景 |
| 文字 | 硬笔钢笔手写书法（硬笔书法），笔画精准流畅，有墨色变化，不是粗马克笔 |
| 插图 | 手绘彩色卡通，黑色马克笔勾线/彩色马克笔上色，有层次阴影，非平面矢量 |
| 吉祥物 | **每页必须出现**：戴着红色龙虾帽的可爱拉布拉多，chibi风格，表情配合页面内容 |
| 标注 | 红色/黑色手绘笔迹（箭头、下划线、✕、✓） |

## 标准 STYLE 前缀（每页 Prompt 必须以此开头）

```
Whiteboard filling the ENTIRE 16:9 frame, all four silver/gray magnetic
frame borders fully visible at image edges, zero background, zero office or room visible.
Clean white whiteboard surface. All text rendered in elegant Chinese hard-pen fountain pen
handwriting calligraphy (硬笔书法) — precise clean strokes, ink variation, flowing and
neat, fine pen line quality, NOT thick marker, NOT digital font. Illustrations are
hand-drawn cartoon style: bold black marker outlines (like Copic multiliner), filled with
vivid colored markers (Copic/Prismacolor style), layered shadows and highlights for depth,
NOT flat vector, NOT watercolor wash — solid marker color with visible stroke direction.
MANDATORY MASCOT on every single page without exception: a super cute chibi Labrador
retriever wearing a red lobster-claw hat, big sparkling eyes, rosy cheeks, fluffy golden
fur, hand-drawn marker style — expression matching the page mood (curious, excited,
thinking, celebrating, etc.). DO NOT omit the Labrador mascot under any circumstances.
Annotation marks in red or black hand-drawn pen (arrows, underlines, ✕, ✓). 16:9 widescreen.
```

> 该前缀已内置于 `scripts/generate_slide.py`，脚本会自动拼接，无需手动重复。

## EasyRouter API 配置

图片生成通过 **EasyRouter.io** 的 OpenAI SDK 兼容接口调用：

| 项 | 值 |
|---|---|
| Base URL | `https://easyrouter.io/v1` |
| Endpoint | `https://easyrouter.io/v1/chat/completions` |
| 模型 | `gemini-3.1-flash-image`（风格/模型均不得改） |
| 密钥来源 | 用户提供 → 可选本地安全存储 |

### 本地密钥存储（约束路径）

- 目录：`~/.config/sanwan-whiteboard-ppt/`
- 文件：`~/.config/sanwan-whiteboard-ppt/easyrouter_api_key`
- 权限：目录 `0700`，文件 `0600`
- 内容：纯文本一行 API Key，无额外 JSON/注释
- **严禁**把 key 写入 skill 目录、脚本、对话回显或 git 仓库

辅助脚本：

```bash
# 检测本地是否已有 key（退出码 0=有，1=无；stdout 为路径，绝不打印 key 内容）
python scripts/manage_api_key.py status

# 安全写入本地（stdin 读 key，或 --key；写入后用掩码确认，不回显全文）
python scripts/manage_api_key.py save --key "sk-你的密钥"
# 或：printf '%s' "$KEY" | python scripts/manage_api_key.py save

# 删除本地 key
python scripts/manage_api_key.py clear
```

`generate_slide.py` 读取优先级（高→低）：

1. CLI `--api-key`
2. 环境变量 `EASYROUTER_API_KEY`
3. 本地文件 `~/.config/sanwan-whiteboard-ppt/easyrouter_api_key`

## 工作流程

### Step 0：确认 EasyRouter API Key（生成前必做）

在写大纲或开始生图之前，先处理密钥。规则：

1. 运行 `python scripts/manage_api_key.py status`
2. **若本地已有 key**：询问用户是否使用本机已保存的 EasyRouter key。
   - 同意 → 后续脚本不带 `--api-key`，自动读本地文件
   - 拒绝 → 请用户提供新 key；提供后询问是否覆盖保存到本地
3. **若本地没有 key**：请用户提供 EasyRouter API key（获取：https://easyrouter.io/）。
   - 收到 key 后立刻询问：是否将 key **安全存储到本机** `~/.config/sanwan-whiteboard-ppt/easyrouter_api_key`，以便以后直接使用
   - 同意 → `python scripts/manage_api_key.py save --key "..."`（或 stdin）
   - 拒绝 → 仅本次会话通过 `--api-key` 或当前 shell 的 `EASYROUTER_API_KEY` 使用，不落盘
4. **绝不**在回复中完整回显用户的 key；最多显示前 4 + `…` + 后 4 的掩码。
5. 依赖：`pip install requests python-pptx`（缺失时先装）。

### Step 1：确认大纲

与用户确认：主题、页数、每页内容要点（适合对比/步骤/介绍/总结类内容）。
除非用户已给出完整大纲，否则先列出「每页标题 + 要点 + 插图创意 + 吉祥物表情/位置」
的分页大纲让用户确认，再开始生成。

### Step 2：逐页生成图片

对每一页，先按「Prompt 内容写法」写好页面描述（不含 STYLE 前缀），存为
`/tmp/sanwan_slides/page_NN.txt`（Windows 下用工作目录内 `sanwan_slides/` 亦可），然后调用脚本：

```bash
# 已保存本地 key 或已 export EASYROUTER_API_KEY 时：
python scripts/generate_slide.py --prompt-file /tmp/sanwan_slides/page_01.txt --out /tmp/sanwan_slides/slide_01.png

# 仅本次传入 key（未落盘）时：
python scripts/generate_slide.py --prompt-file /tmp/sanwan_slides/page_01.txt --out /tmp/sanwan_slides/slide_01.png --api-key "sk-..."
```

脚本行为：

- 按优先级解析 API key，请求 `https://easyrouter.io/v1/chat/completions`
- 模型固定 `gemini-3.1-flash-image`，自动拼接 STYLE 前缀
- 通过 `image_config.aspect_ratio: 16:9` 与 Prompt 双重要求 16:9（否则易输出正方形）
- 成功时打印保存路径；失败时打印错误并以非零码退出

逐页生成，每页成功后再生成下一页。若某页失败，重试一次；仍失败则告知用户跳过或中止。

### Step 3：组装 PPT

全部图片生成完毕后：

```bash
python scripts/build_pptx.py --images "/tmp/sanwan_slides/slide_*.png" --out /tmp/sanwan_slides/output.pptx
```

脚本行为：按文件名排序，将每张图片铺满 13.33×7.5 英寸（16:9）空白页。

### Step 4：交付

PPT 组装完成后：

1. 告知用户 PPTX 的完整本地路径
2. 若当前对话在飞书环境且可用 `send_feishu_file`，将 PPTX 发到当前飞书对话
3. 桌面/非飞书环境：给本地路径即可，用户自行打开
4. 不要逐页发送预览图

## Prompt 内容写法

每页 Prompt（脚本拼接后）= **STYLE前缀** + **排版内容描述** + **吉祥物位置强调（必须）**

固定措辞：

- 文字：`elegant fountain pen Chinese calligraphy handwriting`
- 插图：`hand-drawn cartoon illustration, bold black marker outline, vivid colored marker fill (Copic style), layered shadows for depth, NOT flat vector`
- 吉祥物：`[MUST INCLUDE] cute chibi Labrador with red lobster-claw hat, [表情], placed at [位置]`
- 强调色：`bold red fountain pen Chinese`

**三栏对比/介绍页示例**（写入 prompt-file 的内容，不含 STYLE）：

```
Top: large elegant fountain pen Chinese calligraphy: 页面标题
Medium fountain pen below: 副标题说明
Red hand-drawn pen underline.

Three sections side by side, separated by thin hand-drawn vertical lines:

Left section:
Hand-drawn cartoon illustration: [插图描述，vivid colors, marker-colored]
Elegant fountain pen Chinese below: 标题一
Smaller fountain pen text: 说明文字

Center section:
Hand-drawn cartoon illustration: [插图描述]
Elegant fountain pen Chinese below: 标题二
Smaller fountain pen text: 说明文字

Right section:
Hand-drawn cartoon illustration: [插图描述]
Elegant fountain pen Chinese below: 标题三
Smaller fountain pen text: 说明文字

[MUST INCLUDE] cute chibi Labrador with red lobster-claw hat, excited expression,
waving paw, placed at bottom-left corner.
Bottom center, large bold red fountain pen Chinese: 核心金句或CTA
```

## 完成判定标准

- [ ] 生成前已走完 Key 确认流程（本地已有则询问是否沿用；没有则索取并询问是否落盘）
- [ ] 每页图片均为 16:9，白板四边框完整可见、无背景环境
- [ ] 每页均包含戴红色龙虾帽的拉布拉多吉祥物
- [ ] 所有页面组装为一个 PPTX，图片铺满整页无留白
- [ ] 已将 PPTX 路径告知用户
- [ ] 飞书场景下已尝试发送 PPTX 文件

## 注意事项

- 白板边框：用 `all four borders fully visible, zero background`，勿用 `EXTREME CLOSE-UP`
- **吉祥物每页必须出现**，在 Prompt 结尾单独用 `[MUST INCLUDE]` 再强调一次位置和表情
- 中文文字内容直接写在 Prompt 中
- 只发 PPTX 文件给用户，不发预览图
- API 调用超时 180 秒；图像生成较慢属正常
- **API Key 只能出现在环境变量、本地约束路径文件或一次性 CLI 参数中**；任何情况下不得写入 skill 源码或完整回显给用户
- 模型、STYLE 前缀、板书风格定义不要改动；本 skill 仅切换网关为 easyrouter.io 并增加本地 key 管理
