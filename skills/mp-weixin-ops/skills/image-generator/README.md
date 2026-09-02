---
name: image-generator
description: |
  Generate images for WeChat articles using EasyRouter.io (gpt-image-2). This skill provides
  the image-generation primitive used after the agent decides whether inline images are
  needed. Called by article-writer after article completion. Supports multiple sizes
  for different use cases. Also supports image-to-image (img2img / 图生图) mode.
---

# Image Generator

Generate inline images for WeChat Official Account articles. Uses [EasyRouter.io](https://easyrouter.io/) 的 `gpt-image-2` 模型，**需要用户提供 EasyRouter API Key**。

This skill does **not** decide by itself whether an article should have images. The agent must make that decision first, then call `generate_image.py` for each approved image.

## 🔑 API Key 要求

每次调用都需要 EasyRouter API Key。Agent 在生图前**必须先向用户索要 Key**。

获取方式：访问 [https://easyrouter.io/](https://easyrouter.io/) 注册后在控制台获取。

调用方式（二选一）：
1. `--api-key sk-xxx` CLI 参数
2. `export EASYROUTER_API_KEY=sk-xxx` 环境变量

## Use Cases

- Triggered by article-writer after it decides inline images are needed
- User explicitly requests "add images to this article"
- Generate specific image with custom prompt
- 用户说"图生图" — 基于参考图变换生成新图片

## 视觉内容总监角色

进入配图插画环节时，Agent 自动激活此角色。

你现在是一位资深视觉内容总监，同时精通内容策略和视觉设计。你的核心职责不是"给文章配一张好看的图"，而是"将文章的核心概念翻译为视觉语言"。

**能力一：内容理解（先读懂，再动手）**
- 精读插图位置前后 2-3 段文字，提取该段落的**核心概念**（不是泛主题，是具体论点）
- 识别段落的**情绪状态**（焦虑、兴奋、反思、启发、冲突、和解...）
- 找到**可视化锚点**——段落中最适合转化为画面的那个意象、比喻或场景
  - 例：文章讲"AI 正在蚕食传统岗位" → 可视化锚点可以是"旧工具在新光线下逐渐透明"
  - 例：文章讲"理财的核心是延迟满足" → 可视化锚点可以是"种子在泥土下缓慢发芽的剖面"
  - 例：文章讲"独居年轻人的周末仪式感" → 可视化锚点可以是"窗边一杯咖啡和摊开的书"

**能力二：视觉翻译（概念→画面）**
- 将可视化锚点转化为具体场景描述，而非抽象概念堆叠
- 每张图只表达一个视觉主题，大量留白，主体突出
- 同一篇文章的所有配图共享视觉风格系统（色调、光影、质感一致）
- 根据公众号领域选择对应的视觉基调（见下方映射表）
- 拒绝"通用素材图"——不要生成"一个人在用电脑"这种毫无特色的画面
- 图片内不放任何文字、标题、水印

**内容→视觉翻译的反面教材（禁止）：**
- 文章讲 AI → 配图"一个机器人" — 太泛，没有传达文章的具体观点
- 文章讲理财 → 配图"一堆金币" — 太直白，像素材库搜出来的
- 文章讲健康 → 配图"一个人在跑步" — 通用素材图，和文章具体内容无关

**正确做法：**
- 文章讲"AI 替代重复劳动" → 配图"空荡的传统工位上方悬浮着一束数据光流，warm/cool 交界"
- 文章讲"长期投资的复利效应" → 配图"微距拍摄：一枚硬币上长出嫩芽，旁边是年轮般的同心圆光影"
- 文章讲"秋季养生茶" → 配图"木质茶桌上的玻璃壶，金色茶汤折射窗外秋叶光斑"

## 领域→视觉基调映射

根据公众号领域选择 `--style` 参数值，控制图片的整体视觉风格。脚本会将该值直接传给 API。

从 config/config.json 的 account.field 或 memory/domain.txt 读取领域：

| 领域 | 推荐 --style | 视觉基调 | 色调倾向 | 避免 |
|------|-------------|---------|---------|------|
| 科技/AI | `tech` | 未来感、精密、冷峻 | 深蓝-紫-银色系 | 暖色调、手绘风 |
| 财经/商业 | `finance` | 权威、专业、克制 | 深蓝-灰-金色系 | 过于鲜艳、可爱风 |
| 生活方式 | `lifestyle` | 温暖、自然、舒适 | 奶油-米白-鼠尾草绿 | 冷硬科技感 |
| 教育/知识 | `education` | 清晰、友好、明快 | 浅蓝-暖黄-白色系 | 暗黑风、过于抽象 |
| 情感/故事 | `cinematic` | 电影感、叙事、沉浸 | 青橙对比、暖金 | 平面设计风 |
| 时尚/美妆 | `editorial` | 杂志感、高级、精致 | 莫兰迪低饱和色系 | 素材图感、过于工整 |
| 通用/未指定 | `editorial` | 杂志编辑风、干净大气 | 低饱和中性色 | 极端风格 |

这是指引而非死规则。Agent 根据具体文章内容灵活调整。**同一篇文章的所有配图应共享同一 --style 值和色彩基调。**

## Prompt 构造五步法

**第一步 — 读文提概念**：精读插图位置的段落，用一句话概括"这段讲的核心是什么"，找到可视化锚点

**第二步 — 定情绪基调**：确定这张图的情绪关键词（1-2 个词），并根据领域映射表选择 `--style` 参数值

**第三步 — 场景化翻译**：将可视化锚点转化为具体的场景描述（而非抽象概念词），按 8 维度逐一填充：
- 风格词在最前面（定整体调性）
- 场景和主体在中间（定画面内容——这是和文章关联的核心部分）
- 光影和色彩在最后（定氛围）

**第四步 — 追加控制词**：
- 脚本不会自动追加质量后缀或负面词。请在 prompt 中手动写入"no text, no watermark"等控制词
- gpt-image-2 不支持 `--negative` 参数。如需排除特定元素，直接在 prompt 中描述（如 "no human figure, no text"）

**第五步 — 一致性检查**：
- 这张图能让读者"看到文章在讲什么"吗？（内容相关性）
- 色调与段落情绪一致吗？（情绪匹配）
- 与同篇文章其他图的风格统一吗？（系列感）

## 8-Dimension Visual Framework

Agent must analyze and specify ALL 8 dimensions before calling the script:

| 维度 | 说明 | 示例 |
|------|------|------|
| 风格/媒介 | 整体视觉风格或创作媒介 | 极简主义设计、胶片摄影、3D Render、水彩插画、扁平设计 |
| 构图 | 画面布局和视觉引导 | 中心对称、三分法、L形布局、对角线构图、鸟瞰俯拍 |
| 空间环境 | 场景背景的材质、反光、结构 | 磨砂玻璃办公室、暖木质书房、工业水泥墙、户外草坪 |
| 主体 | 画面主角的材质、结构、边缘处理 | 模糊人物剪影、精致机械结构、柔和边缘手绘人物 |
| 细节 | 文字内容、字体、纹理等微观元素 | 无文字水印、亚麻纹理背景、像素网格细节 |
| 光影 | 光源方向、反射、氛围光 | 左侧45度暖光、逆光剪影、丁达尔效应、柔和漫反射 |
| 色彩 | 色调倾向和主色调 | 莫兰迪低饱和、冷蓝灰主调 #4A6FA5、暖橙渐变 |
| 镜头 | 焦段和景深效果 | 35mm广角、85mm人像虚化、微距特写、移轴效果 |

**8 维度精选词库（供选取组合，不需要每个词都用）：**

**风格/媒介：** editorial photography, cinematic film still, fine art photography, soft focus lifestyle, macro detail shot, aerial top-down, oil painting texture, watercolor wash, digital illustration flat design, isometric 3D render, minimalist graphic, documentary style

**构图：** rule-of-thirds, centered symmetrical, diagonal dynamic, leading lines, frame within frame, negative space dominant, bird's-eye overhead, low angle heroic, golden ratio spiral, layered depth

**空间环境：** soft studio backdrop gradient, natural outdoor golden hour, modern office glass walls, cozy home warm wood, industrial concrete raw texture, abstract geometric space, misty atmospheric, clean white infinity, urban cityscape bokeh

**主体：** abstract silhouette soft edges, floating geometric objects, detailed mechanical precision, organic natural forms, conceptual metaphor visualization, blurred anonymous figure, product hero shot, landscape panorama, still life arrangement

**细节：** subtle film grain, linen texture, glass reflection, water droplets, metallic sheen, paper texture overlay, light dust particles, fabric folds

**光影：** soft diffused studio, golden hour directional warm, rim light silhouette, Rembrandt dramatic side, flat even ambient, neon accent glow, backlit halo, window light with curtain diffusion

**色彩：** muted desaturated Morandi palette, teal-and-orange cinematic, monochrome with single accent color, warm earth tones, cool blue-gray professional, pastel soft dreamy, deep navy-gold luxurious, sage-cream-terracotta natural

**镜头：** 85mm portrait shallow DOF bokeh, 35mm wide environmental, 50mm standard natural perspective, 100mm macro detail, 24mm ultra-wide dramatic, tilt-shift miniature effect

**Prompt 组装规则：**
- 按 8 维度依次描述，确保每个维度都有值
- 核心描述词建议用英文以获得更好效果
- 脚本不会自动追加质量后缀，prompt 中需手动写 "no text, no watermark"
- 与文章情绪弧线保持一致（焦虑段用冷色调，希望段用暖色调）

## 高质量 Prompt 范例

展示从内容到 prompt 的完整推导，供 Agent 学习思路：

**范例 1 — 科技文章段落："AI Agent 正在改变软件开发的范式"**
- 可视化锚点：不是"一个机器人写代码"，而是"代码在空间中自动编织成网络结构"
- 情绪：前沿、精密、有秩序的变革感
```bash
python3 ${SKILL_DIR}/scripts/generate_image.py \
  "futuristic technology visualization, dynamic diagonal composition, \
dark matte background with subtle hexagonal grid pattern, \
luminous code fragments assembling themselves into an intricate neural network structure, \
holographic translucent nodes with data flowing through connecting threads, \
cool neon blue accent lighting from below with deep purple ambient fill, \
deep navy #1a1a2e base with electric blue #00d4ff and violet #7c3aed accents, \
wide angle 24mm lens deep perspective vanishing point, \
no text, no watermark, no cartoon, no human figure" \
  --style tech --size 1536x1024 --api-key sk-xxx \
  -o drafts/images/img_001.jpg
```

**范例 2 — 生活方式段落："独居的周末，从一杯手冲咖啡开始"**
- 可视化锚点：不是"一杯咖啡"，而是"晨光、手冲壶、蒸汽、一个人的安静仪式"
- 情绪：温暖、安静、仪式感
```bash
python3 ${SKILL_DIR}/scripts/generate_image.py \
  "natural lifestyle editorial photography, relaxed off-center composition, \
cozy kitchen corner with warm wood countertop and morning light, \
hand-pour coffee dripper with rising steam catching sunlight, \
open book and ceramic cup on linen cloth nearby, \
warm golden daylight streaming through sheer curtains with soft shadows, \
cream #F5F0EB and sage green #9CAF88 and warm honey #D4A574 palette, \
35mm wide angle slight vignette natural perspective, \
no text, no watermark" \
  --style lifestyle --size 1536x1024 --api-key sk-xxx \
  -o drafts/images/img_002.jpg
```

**范例 3 — 财经段落："复利效应需要时间，大多数人倒在黎明前"**
- 可视化锚点：不是"金币堆"，而是"黑暗中一棵嫩芽正在突破硬币堆"——寓意坚持和生长
- 情绪：克制、希望、力量感
```bash
python3 ${SKILL_DIR}/scripts/generate_image.py \
  "professional fine art still life photography, centered composition generous negative space, \
dark textured surface with scattered old coins, \
single green sprout breaking through the coin pile reaching toward soft overhead light, \
dramatic Rembrandt side lighting with warm accent from above, \
deep charcoal #2C2C2C base with muted gold #B8964E and fresh green #6B8E5A accent, \
100mm macro lens shallow depth of field with beautiful bokeh, \
no text, no watermark, no bright colors, no person" \
  --style finance --size 1536x1024 --api-key sk-xxx \
  -o drafts/images/img_003.jpg
```

**范例 4 — 情感故事段落："她决定不再回头看那座城市"**
- 可视化锚点：不是"一个女人"，而是"雨后街道上一个模糊背影渐行渐远"——叙事张力
- 情绪：释然、淡淡的忧伤、向前
```bash
python3 ${SKILL_DIR}/scripts/generate_image.py \
  "cinematic film still, wide anamorphic composition with letterbox feel, \
quiet city street after rain with reflective wet pavement and scattered fallen leaves, \
lone figure walking away silhouette with umbrella softly blurred edges, \
golden hour warm backlight from behind with cool blue ambient shadows, \
teal #2C6E6A shadows transitioning to warm amber #E8A87C highlights, \
50mm prime lens natural perspective beautiful circular bokeh, \
no text, no watermark" \
  --style cinematic --size 1536x1024 --api-key sk-xxx \
  -o drafts/images/img_004.jpg
```

## Script Directory

This skill's scripts are located in `${SKILL_DIR}/scripts/`, where `SKILL_DIR` is the directory containing this SKILL.md file.

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/generate_image.py` | Generate single image | `python3 ${SKILL_DIR}/scripts/generate_image.py "描述" --api-key sk-xxx -o output.jpg` |

## Configuration

使用 [EasyRouter.io](https://easyrouter.io/) 的 `gpt-image-2` 模型。每次调用需要通过 `--api-key` 或 `EASYROUTER_API_KEY` 环境变量提供 API Key。

## Dependencies

```bash
pip install requests
```

## Image Sizes

gpt-image-2 支持以下尺寸：

| Size | Use Case | Orientation |
|------|----------|-------------|
| `1024x1024` | Square image | 1:1 |
| `1024x1536` | Portrait | 2:3 |
| `1536x1024` | Landscape (**推荐用于文章插图**) | 3:2 |
| `auto` | Let model decide | - |

兼容旧格式：`1280*720` / `1792x1024` → `1536x1024`，`600*800` / `1024x1792` → `1024x1536`

## Workflow

### Mode 1: Agent-Orchestrated Inline Images (Recommended)

After article writing, the **agent must first make an image decision**, then use this skill to generate the approved images.

**Decision protocol:**

1. Analyze article theme, emotional tone, and structure
2. Decide image count and positions based on content needs
3. Choose one of two outcomes:
   - **Generate images** and insert them into Markdown
   - **Skip images** and explicitly state the reason
4. If generating, follow the **Prompt 构造五步法** above to construct each prompt, then:
   - Create the images directory
   - Call `generate_image.py` once per image
   - Insert `![](./images/img_001.jpg)` into Markdown
5. If skipping:
   - Record the exact reason in the work summary

**Default guidance:**
- News brief / very short article: 0-1 image
- Standard article: usually 1-3 images
- Deep analysis article: usually 2-5 images
- For non-news articles, default to at least 1 image unless there is a clear skip reason

### Mode 2: Single Image Generation

Generate a specific image with custom prompt:

```bash
# Basic usage
python3 ${SKILL_DIR}/scripts/generate_image.py "AI assistant working on laptop" --api-key sk-xxx -o image.jpg

# With custom size
python3 ${SKILL_DIR}/scripts/generate_image.py "Data visualization chart" --size 1536x1024 --api-key sk-xxx -o chart.jpg

# With quality
python3 ${SKILL_DIR}/scripts/generate_image.py "Tech startup office" --quality high --api-key sk-xxx -o office.jpg
```

### Mode 3: Image-to-Image Generation (图生图)

Transform an existing image based on a text prompt. The reference image provides structure and composition, while the prompt controls the style and content changes.

```bash
# Basic img2img — convert to watercolor style
python3 ${SKILL_DIR}/scripts/generate_image.py \
  "转换为水彩画风格，保持原有构图" \
  --image /path/to/reference.jpg \
  --api-key sk-xxx \
  -o output_img2img.jpg

# Multiple reference images (max 4)
python3 ${SKILL_DIR}/scripts/generate_image.py \
  "blend these styles" \
  --image img1.png --image img2.png \
  --api-key sk-xxx \
  -o output_blend.jpg
```

**Supported formats:** PNG, JPG/JPEG, WebP

## Parameters

### generate_image.py

| Parameter | Description | Default |
|-----------|-------------|---------|
| `prompt`（位置参数） | 图片描述文本（必填） | - |
| `--api-key` | EasyRouter API key (or set `EASYROUTER_API_KEY` env var) | - |
| `--size` | Image size: `1024x1024`, `1024x1536`, `1536x1024`, `auto` | `1024x1024` |
| `--quality` | Image quality: `low`, `medium`, `high`, `auto` | `auto` |
| `-o, --output` | Output path | auto-generated in `outputs/` |
| `--image` | Reference image path/URL (enables img2img mode, max 4 images) | - |
| `--style` | Image style preset (e.g. tech, finance, lifestyle, cinematic, editorial) | None (API auto) |
| `--base-url` | API base URL | `https://easyrouter.io/v1` |

| `--model` | Model name | `gpt-image-2` |

## Prompt 构造建议

gpt-image-2 支持 `--style` 参数控制整体视觉风格，但**不支持 `--negative` 负面词参数**。请在 prompt 中直接描述需要避免的元素（如 "no text, no watermark"）。

参考上方「领域→视觉基调映射」表选择 `--style` 值。风格词和色调细节仍需在 prompt 中描述以获得精确控制。

## Content Safety

Agent 应在调用脚本前进行语义级安全判断，确保 prompt 不包含政治敏感、色情、暴力、赌博、毒品、歧视等内容。API 本身也有安全过滤，不安全内容会被拒绝。

## Output

### generate_image.py Output

```
Mode: text-to-image
Model: gpt-image-2
Prompt: ...
Calling API: POST https://easyrouter.io/v1/images/generations
IMAGE_RESULT: /path/to/image.jpg
```

### img2img Output

```
Mode: image-edit (img2img)
Model: gpt-image-2
Prompt: 转换为水彩画风格...
  Loading reference image: /path/to/reference.jpg
Calling API: POST https://easyrouter.io/v1/images/edits
IMAGE_RESULT: /path/to/output.jpg
```

### Example Agent-Orchestrated Output

```
[决策] 文章评估完成，计划插入 3 张插图
[位置] 第 2 段后 (字符 456)
[位置] 第 4 段后 (字符 1234)
[位置] 第 6 段后 (字符 2100)

[生成] 图片 1/3：AI工具界面示意图
[OK] 保存至 images/img_001.jpg
[插入] ![](./images/img_001.jpg)

[生成] 图片 2/3：数据可视化图表
[OK] 保存至 images/img_002.jpg
[插入] ![](./images/img_002.jpg)

[生成] 图片 3/3：团队协作场景
[OK] 保存至 images/img_003.jpg
[插入] ![](./images/img_003.jpg)

[完成] 插图决策已执行，共插入 3 张插图
```

## Skip / Failure Behavior

### When API Key Is Not Provided

```
Error: EasyRouter API key is required.
Provide it via --api-key or set EASYROUTER_API_KEY environment variable.
```

The script exits with code `1`. The caller should treat this as an API failure.

### When API Fails

```
Mode: text-to-image
...
❌ 请求失败（500）：...
```

The script exits with code `1` (after retries). The agent should inform the user and suggest retrying or checking their API key.

## Integration with Other Skills

- **article-writer**: Makes image decisions in Step 8, then calls `generate_image.py` for each approved image
- **cover-generator**: Delegates cover generation (1536x1024 size)
- **publish-orchestrator**: Uploads inline images to WeChat and replaces local paths with media URLs

## Example Usage in article-writer

After article completion and image decision:

```bash
# Step 8: Decide images first
echo "[Step 8] 执行插图决策..."

# Create images directory
mkdir -p "$(dirname "$ARTICLE_PATH")/images"

# Generate one approved image
python3 ${SKILL_DIR}/scripts/generate_image.py \
  "YOUR DETAILED PROMPT HERE, no text, no watermark" \
  --size 1536x1024 \
  --api-key sk-xxx \
  -o "$(dirname "$ARTICLE_PATH")/images/img_001.jpg"

# Output
echo "[完成] 插图决策已执行；如生成成功则已插入图片"
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `API key is required` | No key provided | Use `--api-key` or set `EASYROUTER_API_KEY` env var |
| `认证失败` | Invalid/expired key | Check your EasyRouter API key at https://easyrouter.io/ |
| `requests not found` | Package not installed | `pip install requests` |
| `API 调用失败` | Network or API error | Check network and retry; check EasyRouter service status |
| `Image too dark/bright` | Prompt issue | Add lighting hints to prompt |
| `Image irrelevant` | Prompt too vague | Add more specific descriptive details |
| `参考图片不存在` | `--image` path is wrong | Verify the file path exists |
