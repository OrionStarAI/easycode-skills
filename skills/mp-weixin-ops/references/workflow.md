# 工作流详细说明

> 审批行为由 SKILL.md 统一定义（3 个节点 + 封面失败处理），本文件不重复描述审批逻辑。各步骤只标注 `[自动]` 或 `[审批]`，标注 `[审批]` 的步骤按 SKILL.md 审批节点执行。

## Step 1：热点调研 [自动]

调用 `skills/daily-trending/`，从微博/知乎/百度等平台抓取热榜，筛选 5~10 个选题方向。

完成后自动进入 Step 2。

## Step 2：选题策划 [自动 → 审批]

调用 `skills/content-planner/scripts/search_wechat.js` 搜索竞品文章，生成 3-5 个差异化选题方案（含标题建议、写作角度、推荐风格）。

```bash
node skills/content-planner/scripts/search_wechat.js "关键词" -n 10
```

完成后触发**审批节点 1**（见 SKILL.md）：展示选题，一次性收集选题选择 + 风格 + API Key。用户选择后自动进入 Step 3。

## Step 3：文章写作 [自动 → 审批]

调用 `skills/article-writer/`，按确认的选题和风格写作。

**3a. 生成大纲** → 完成后触发**审批节点 2**（见 SKILL.md）：展示大纲，用户确认后继续。

**3b. 正文写作** → 按大纲撰写完整正文。

**3c. 自动润色** → 运行 `polish_text.py` 修复长句、被动语态、空话套话等。

输出：`drafts/YYYYMMDD_标题.md`

完成后自动进入 Step 4。

## Step 4：配图生成 [自动]

调用 `skills/image-generator/scripts/generate_image.py` 生成 2-3 张插图，自动选择插入位置，生成后立即插入 Markdown。

```bash
python3 skills/image-generator/scripts/generate_image.py \
  "图片描述，no text, no watermark" \
  --api-key sk-xxx \
  --style tech \
  --size 1536x1024 \
  -o drafts/images/img_XX.jpg
```

配图规则：
- prompt 是位置参数，不要用 `--prompt`
- `--style` 传给 API 的 `style` 字段，同篇所有配图用相同值（如 tech/finance/cinematic/editorial/lifestyle）
- prompt 中手动写 "no text, no watermark" 等控制词

完成后自动进入 Step 5。

## Step 5：封面生成 [自动]

调用 `skills/cover-generator/scripts/generate_cover.py` 生成封面。

```bash
python3 skills/cover-generator/scripts/generate_cover.py \
  --title "文章标题" \
  --api-key sk-xxx \
  -o output/covers/cover_YYYYMMDD.jpg
```

- 默认尺寸 1536x1024
- AI 成功 → 直接使用
- AI 失败 → 触发**封面失败处理**（见 SKILL.md）：询问用户是否降级 Picsum

完成后自动进入 Step 6。

## Step 6：排版转换 [自动]

调用 `npx -y bun skills/markdown-to-html/scripts/main.ts`，主题固定 `default`，自动修复中文排版问题。

```bash
npx -y bun skills/markdown-to-html/scripts/main.ts drafts/文章.md --theme default
```

输出：同目录 `文章.html`

完成后展示成果摘要，触发**审批节点 3**（见 SKILL.md）：等待用户说"发布"。

## Step 7：推送发布 [审批]

用户确认后执行。推送到草稿箱（默认）或群发（需用户明确说"群发"）。

```bash
# 草稿箱
npx -y bun skills/publish-orchestrator/scripts/wechat-api.ts \
  drafts/文章.md --cover output/covers/cover_YYYYMMDD.jpg --theme default

# 群发
npx -y bun skills/publish-orchestrator/scripts/wechat-api.ts \
  drafts/文章.md --cover output/covers/cover_YYYYMMDD.jpg --publish
```
