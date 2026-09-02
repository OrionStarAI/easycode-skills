# 依赖与配置说明

## 子 Skill 依赖

使用本 Skill 前，必须在同一工作区安装以下子 Skill：

| Skill 目录名 | 安装方式 |
|-------------|---------|
| `daily-trending` | 已包含在 wechat-bot-skills.zip |
| `content-planner` | 已包含在 wechat-bot-skills.zip |
| `article-writer` | 已包含在 wechat-bot-skills.zip |
| `image-generator` | 已包含在 wechat-bot-skills.zip |
| `cover-generator` | 已包含在 wechat-bot-skills.zip |
| `markdown-to-html` | 已包含在 wechat-bot-skills.zip |
| `publish-orchestrator` | 已包含在 wechat-bot-skills.zip |

将 wechat-bot-skills.zip 解压后，各 Skill 文件夹放入工作区 `skills/` 目录下。

## 外部 API 依赖

### 🔴 必须配置

**微信公众号 API**（发布功能必需）

在工作区根目录创建 `.secrets/wechat-config.json`：

```json
{
  "appid": "wx开头的AppID",
  "secret": "32位AppSecret"
}
```

获取方式：登录 [微信开发者控制台](https://developers.weixin.qq.com/console) → 滚动到「我的业务」→ 点击「公众号」进入 → 在「基础信息」中获取 AppID 和 AppSecret

**权限要求：**
- 草稿箱推送：订阅号 + 服务号均支持
- 群发（freepublish）：仅服务号支持

### 🟡 可选但推荐

**EasyRouter API Key**（图片/封面生成功能）

图片生成和封面生成使用 [EasyRouter.io](https://easyrouter.io/) 的 `gpt-image-2` 模型。需要在 [https://easyrouter.io/](https://easyrouter.io/) 注册并获取 API Key。

**无需写入配置文件**，每次调用脚本时通过以下方式之一传入 Key：

1. CLI 参数：`--api-key sk-xxx`
2. 环境变量：`export EASYROUTER_API_KEY=sk-xxx`

- `image-generator` 和 `cover-generator` 通过此 API 调用文生图/图生图
- **未提供 Key 时**：脚本直接报错退出（cover-generator 可加 `--allow-fallback` 降级为 Picsum 随机图，或用 `--no-ai` 直接用随机图）
- `generate-video` 仍使用原有的视频生成方式（如需视频功能，请参考对应 Skill 文档）

### 🟢 无需配置（爬虫类）

| 服务 | 用途 | 备注 |
|------|------|------|
| `weixin.sogou.com` | 搜狗微信搜索 | 无需 Key，受反爬限制，偶发失效 |
| `tophub.today` | 多平台热榜聚合 | 无需 Key |
| `picsum.photos` | 随机封面图 fallback | 境外域名，国内偶有访问问题 |

## 运行时依赖

### Node.js 环境
```bash
node --version  # 需要 v18+
npx --version   # 需要支持 -y 参数
```

content-planner 的 search_wechat.js 需要安装依赖：
```bash
cd skills/content-planner
npm install  # 安装 cheerio 等依赖
```

### Python 环境
```bash
python3 --version  # 需要 3.9+
pip install requests pillow  # image-generator 和 cover-generator 的依赖
```

### Bun（排版和发布脚本）
```bash
# 通过 npx 自动安装，无需手动安装
npx -y bun --version
```

## 目录结构要求

```
your-workspace/
├── .secrets/
│   └── wechat-config.json      # 微信凭据（必须）
├── drafts/                     # 文章草稿输出目录（自动创建）
│   └── images/                 # 文章插图
├── output/
│   └── covers/                 # 封面图输出目录
└── skills/
    ├── daily-trending/
    ├── content-planner/
    ├── article-writer/
    ├── image-generator/
    ├── cover-generator/
    ├── markdown-to-html/
    ├── publish-orchestrator/
    └── wechat-ops-orchestrator/ # 本 Skill
```
