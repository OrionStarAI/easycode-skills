# Cover Generator

Generate cover images for WeChat Official Account articles. Uses [EasyRouter.io](https://easyrouter.io/) 的 `gpt-image-2` 模型，**需要用户提供 EasyRouter API Key**。

## 🔑 API Key 要求

每次调用都需要 EasyRouter API Key。Agent 在生成封面前**必须先向用户索要 Key**。

获取方式：访问 [https://easyrouter.io/](https://easyrouter.io/) 注册后在控制台获取。

调用方式（二选一）：
1. `--api-key sk-xxx` CLI 参数
2. `export EASYROUTER_API_KEY=sk-xxx` 环境变量

## Dependencies

```bash
pip install requests
```

## Content Safety

The script includes a built-in keyword filter that blocks prompts containing politically sensitive, pornographic, violent, gambling, drug-related, or discriminatory content. The Agent should also perform semantic-level safety judgment before calling the script — the keyword filter is a safety net, not the primary defense.

## Usage

```bash
# Basic usage (requires API key; exits with code 2 on failure)
python3 scripts/generate_cover.py --title "Article Title" --api-key sk-xxx -o cover.jpg

# Custom AI prompt
python3 scripts/generate_cover.py --title "Article Title" --prompt "Cyberpunk city night scene, blue-purple tones" --api-key sk-xxx -o cover.jpg

# Allow automatic fallback to Picsum (user has authorized)
python3 scripts/generate_cover.py --title "Article Title" --allow-fallback --api-key sk-xxx -o cover.jpg

# Skip AI and use Picsum random cover (no API key needed)
python3 scripts/generate_cover.py --title "Article Title" --no-ai -o cover.jpg

# Specify dimensions
python3 scripts/generate_cover.py --title "Article Title" --size 1536x1024 --api-key sk-xxx -o cover.jpg

# Image-to-image cover (图生图封面)
python3 scripts/generate_cover.py --title "Article Title" \
  --image /path/to/reference.jpg --api-key sk-xxx -o cover.jpg
```

## Parameters

| Parameter | Description | Default |
|---|---|---|
| `--title` | Article title (required) | - |
| `--api-key` | EasyRouter API key (or set `EASYROUTER_API_KEY` env var) | - |
| `--prompt` | Custom AI prompt | Auto-generated based on title |
| `--size` | Image size (gpt-image-2 format) | `1536x1024` |
| `--quality` | Image quality: `low`, `medium`, `high`, `auto` | `auto` |
| `-o` | Output path | `output/covers/cover_timestamp.jpg` |
| `--no-ai` | Skip AI and use Picsum random cover directly | false |
| `--allow-fallback` | AI 失败时自动使用 Picsum 随机图（需用户明确授权） | false |
| `--image` | Reference image path/URL (enables img2img mode). Supports PNG/JPG/WebP | - |

## 封面 Prompt 构造指南

封面图的核心目标是在信息流中吸引点击，同时传达文章调性。与文章插图不同，封面更注重视觉冲击力和信息概括性。

**构造原则：**
1. **一眼传达主题** — 封面要让读者在信息流中快速理解文章讲什么
2. **视觉冲击优先** — 封面比插图更需要吸引力，对比度和色彩饱和度可以适当提高
3. **简洁大气** — 封面画面不宜过于复杂，1 个主体 + 干净背景即可
4. **无文字** — 微信会自动叠加标题，封面图本身不应包含文字

**风格选择建议：**

| 文章类型 | 推荐风格思路 | 示例 prompt 方向 |
|---------|------------|----------------|
| 科技/AI | 未来感、深色背景、光效 | dark futuristic, neon accents, tech visualization |
| 财经/商业 | 专业、克制、几何感 | professional, geometric, navy-gold palette |
| 生活方式 | 温暖、自然光、生活场景 | warm lifestyle, natural light, cozy atmosphere |
| 情感/故事 | 电影感、叙事氛围 | cinematic, storytelling mood, dramatic lighting |
| 教育/知识 | 明快、友好、清晰 | bright, friendly, clean educational style |
| 通用 | 杂志编辑风 | editorial photography, clean composition |

**自定义 prompt 时的注意事项：**
- 使用 `--prompt` 参数覆盖默认的基于标题自动生成的 prompt
- prompt 用英文效果更好
- 将需要避免的元素（如 "no text, no watermark"）直接写入 prompt
- 封面尺寸固定为横图（默认 `1536x1024`），不支持竖图

**安全规则：** 封面 prompt 同样适用生图提示词安全规则（政治、色情、暴力、赌博、毒品、宗教、真人肖像、歧视、儿童安全等均禁止）。详见 image-generator SKILL.md 的 Content Safety 章节。

## Generation Logic

```
API key provided?
    ├── Yes → --image provided?
    │           ├── Yes → Call gpt-image-2 (img2img mode) → Success → Save (exit 0)
    │           │                                      → Failure → --allow-fallback?
    │           │                                                    ├── Yes → Fetch Picsum (exit 0/1)
    │           │                                                    └── No → exit 2 (Agent asks user)
    │           └── No → Call gpt-image-2 (txt2img mode) → Success → Save (exit 0)
    │                                                 → Failure → --allow-fallback?
    │                                                               ├── Yes → Fetch Picsum (exit 0/1)
    │                                                               └── No → exit 2 (Agent asks user)
    └── No → --no-ai?
              ├── Yes → Fetch Picsum (exit 0/1)
              └── No → exit 1 (Error: API key required)
```

**Exit codes:** `0` = success, `1` = complete failure (e.g. no API key), `2` = AI failed but fallback not authorized.

`--no-ai` always skips AI and fetches a random image from Picsum Photos (no API key needed).

## Integration with Other Skills

After generating a cover, specify it when publishing via `publish-orchestrator`:

```bash
npx -y bun skills/publish-orchestrator/scripts/wechat-api.ts article.md \
  --cover cover.jpg
```
