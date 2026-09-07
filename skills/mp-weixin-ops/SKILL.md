---
name: mp-weixin-ops
category: 社媒运营
description: 微信公众号一站式运营 Skill。覆盖从热点调研、选题策划、文章写作、配图生成、封面制作、排版转换到推送草稿箱的完整工作流。触发词：写公众号文章、帮我写一篇、公众号运营、从选题到发布、推送草稿箱、帮我配图、生成封面、生成视频、公众号排版、content planning、publish to WeChat。所有子功能内置于 skills/ 子目录，无需单独安装。
---

# mp-weixin-ops — 微信公众号一站式运营

一个 Skill 搞定公众号全链路：热点 → 选题 → 写作 → 配图 → 封面 → 排版 → 发布。

## 完整工作流（7 步）

| Step | 功能 | 脚本 | 类型 |
|------|------|------|------|
| 1 | 热点调研 | `skills/daily-trending/` | 自动 |
| 2 | 选题策划 | `skills/content-planner/scripts/search_wechat.js` | 自动 → 审批 |
| 3 | 文章写作 | `skills/article-writer/` | 自动 → 审批 |
| 4 | 配图生成 | `skills/image-generator/scripts/generate_image.py` | 自动 |
| 5 | 封面生成 | `skills/cover-generator/scripts/generate_cover.py` | 自动 |
| 6 | 排版转换 | `npx -y bun skills/markdown-to-html/scripts/main.ts` | 自动 |
| 7 | 推送发布 | `npx -y bun skills/publish-orchestrator/scripts/wechat-api.ts` | 审批 |

**执行规则：** Step 1→6 自动衔接执行。全程仅有 3 处暂停（详见下方审批节点），其余步骤不询问、不停顿、不问"要不要继续"。Step 7 需用户明确说"发布"才触发。

## 审批节点（全文仅此一处定义，共 3 个）

> ⚠️ 本节是审批行为的唯一定义来源。workflow.md 和各子 skill README 中不再重复描述任何审批行为。每个审批节点只执行一次提问，不重复。

### 节点 1：选题确认（Step 2 完成后）

展示 3-5 个选题候选，一次性收集：选题选择、写作风格、EasyRouter API Key（如尚未提供）。用户选择后立即进入 Step 3，不再追问。

### 节点 2：大纲确认（Step 3a 完成后）

展示文章大纲，用户确认或修改后立即开始写正文，后续 Step 4→6 自动衔接。

### 节点 3：发布确认（Step 6 完成后）

展示最终成果摘要，用户确认后执行 Step 7 推送草稿箱。

### 封面 AI 失败处理（Step 5 内，仅失败时触发）

封面 AI 生成失败时，询问用户是否降级为 Picsum 随机图。仅此一次，不重复问。

### 其余一切步骤自动执行

- 写完正文 → 自动配图，不问
- 配图完成 → 自动封面，不问
- 封面完成 → 自动排版（主题 default），不问
- 排版完成 → 展示成果，等用户说"发布"

## 子 Skill 调用规则

调用各子 skill 时，**只遵循本 SKILL.md 的编排规则**。子 skill README 仅作为操作参考（脚本用法、参数、写作规范），其中定义的审批门/确认步骤**一律忽略**。

具体忽略清单：
- `content-planner/README.md`：Step 1 "Confirm with user"、Step 5 "mandatory approval gate"
- `article-writer/README.md`：Step 2 "Confirm style choice"、Step 5 "mandatory approval gate"、Step 11 "Output Confirmation"
- `markdown-to-html/README.md`：Step 0 "ask whether to fix"、Step 1 "askUserQuestion to confirm theme"
- `publish-orchestrator/README.md`：Step 2 "pause and ask user"

替代行为：写作风格自动推荐（在节点 1 一并展示）、排版主题固定 default、格式问题自动修复、发布预检自动修复可修复项。

## 快速开始

> "帮我写一篇关于 AI Agent 的公众号文章，推送到草稿箱"
> "帮我规划下周的内容选题"
> "把 drafts/ 里的文章发布到公众号"

## 内置子功能

| 子目录 | 功能 |
|--------|------|
| `skills/daily-trending/` | 抓取微博/知乎/百度等多平台热榜 |
| `skills/content-planner/` | 搜索同类公众号文章，生成差异化选题 |
| `skills/article-writer/` | 5 种风格文章写作 |
| `skills/image-generator/` | AI 文章插图生成（文生图/图生图）|
| `skills/cover-generator/` | AI 封面图生成（文生图/图生图）|
| `skills/generate-video/` | 视频生成 |
| `skills/markdown-to-html/` | Markdown 转微信兼容 HTML |
| `skills/publish-orchestrator/` | 推送草稿箱 / 群发 |

## 配置要求

**必须：** 微信公众号凭据，在工作区根目录创建 `.secrets/wechat-config.json`：
```json
{ "appid": "YOUR_APP_ID", "secret": "YOUR_APP_SECRET" }
```

**可选：** EasyRouter API Key（图片/封面生成），访问 https://easyrouter.io/ 获取。通过 `--api-key sk-xxx` 或 `EASYROUTER_API_KEY` 环境变量传入，不写入任何文件。

详细步骤说明见 `references/workflow.md`，依赖说明见 `references/dependencies.md`。

## 脚本路径约定

所有路径相对于本 SKILL.md 所在目录：

```bash
# 图片生成（prompt 是位置参数，不要用 --prompt）
python3 skills/image-generator/scripts/generate_image.py "图片描述，no text, no watermark" --api-key sk-xxx --style tech --size 1536x1024 -o out.jpg

# 封面生成
python3 skills/cover-generator/scripts/generate_cover.py --title "标题" --api-key sk-xxx -o cover.jpg

# 视频生成
python3 skills/generate-video/scripts/generate_video.py "视频描述"

# 公众号文章搜索
node skills/content-planner/scripts/search_wechat.js "关键词" -n 10

# Markdown 排版
npx -y bun skills/markdown-to-html/scripts/main.ts article.md --theme default

# 推送草稿箱
npx -y bun skills/publish-orchestrator/scripts/wechat-api.ts article.md --cover cover.jpg
```
