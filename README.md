# EasyCode 技能仓库

这是 EasyCode 技能商城当前已发布技能的源码备份仓库。仓库中的内容可审查、可回滚，并保留技能的说明、媒体资源和商城元数据。

当前仓库只放生产商城范围内的 19 个技能；个人、实验中、未上架和仅保存在本地的技能不放入这里。

## 目录结构

每个技能位于 `skills/<技能名>/`：

- `SKILL.md`：技能正文和 YAML frontmatter；
- `marketplace.json`：版本、上下架状态、使用示例、对象存储键等商城元数据；
- `assets/`：图标、详情预览图、缩略图和示例产出文件；
- 其他脚本和参考资料：技能运行时需要的资源。

运行缓存、依赖目录、环境文件和密钥不会提交到仓库。

## 上游同步

14 个技能在 `SKILL.md` 中声明了上游仓库、源码路径和已审核提交号。GitHub Actions 每天北京时间 10:00 检查上游，也可以手动运行 **Sync upstream skills**。发现更新后，Action 会在独立分支创建或更新 PR，供人工审核。

同步使用已审核提交号做三方合并：新增文件自动带入，未被本地修改的删除会同步，本地和上游同时修改的文本会保留冲突标记并等待处理。同步不会直接修改 EasyCode 后台，也不会直接写入 GCS。没有上游元数据的 5 个内部上传技能仍由普通 PR 手工维护。

上游元数据示例：

```yaml
---
name: docx
description: "..."
upstream: anthropics/skills
upstreamPath: skills/docx
upstreamSha: 53048666b05b4799081517d00e09e0a2dd688678
author: anthropics
---
```

## 技能门禁

每个 Pull Request 和推送到 `main` 都会运行 **Skill Gate**。门禁会用真实 YAML 解析器检查 `SKILL.md`，并校验 `marketplace.json`、媒体文件路径和数量、技能目录命名、上游提交号、常见凭据/私钥以及合并冲突标记。未加引号的 description 冒号等问题会在合并前失败。

`main` 已设置分支保护，必须通过 `Validate skills` 才能合并。具体维护规则见 [docs/skill-sync.md](docs/skill-sync.md)。

## 发布边界

目前 GitHub 仓库**没有**单独的 tag 发布 workflow。普通提交、上游同步 PR 和生产发布是三件事：

1. 合并通过门禁的技能源码；
2. 按现有 OpenC3 发布流程在内部发布仓库打 `release-online-*` tag；
3. OpenC3 负责构建、部署以及对象存储产物同步。

`release-online-*` 不是本仓库普通提交的必需步骤；只有要推动生产商城版本时才使用。未来若需要 GitHub tag 直接生成发布包或通知 OpenC3，再单独增加发布 workflow。

## 本地检查

```shell
ruby scripts/validate_skills.rb --self-test
ruby scripts/validate_skills.rb
ruby scripts/sync_upstreams.rb
```

`scripts/sync_upstreams.rb` 只会修改当前工作树，适合在 PR 分支或 CI 临时分支运行；它不会上传对象存储。更多同步、冲突处理和分支保护说明见 [docs/skill-sync.md](docs/skill-sync.md)。
