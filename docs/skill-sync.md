# Skill 同步与门禁

这个仓库把“源码备份”“上游同步”和“EasyCode 发布”分成三个阶段：

1. `SKILL.md` 中声明了 `upstream`、`upstreamPath` 和 `upstreamSha` 的技能，参加上游同步。
2. GitHub Actions 每天 `02:00 UTC`（北京时间 `10:00`）检查上游，也可以在 Actions 页面手动运行 **Sync upstream skills**。
3. 有更新时，Action 在 `chore/sync-upstream-skills` 分支创建或更新 PR。同步不会直接发布 Marketplace，也不会直接写 GCS。
4. PR 必须通过 **Skill Gate** 才能合并；合并本身不会触发生产发布。需要上线时，再按 EasyCode/OpenC3 的既有发布流程打 release tag。

## GitHub 仓库标签（暂不启用）

当前仓库没有 tag 触发的发布 workflow，也不要求普通提交打 tag。GitHub 仓库标签未来可以用于生成固定版本技能包或通知 OpenC3，但这属于独立的发布流程，暂时不配置。

## 上游元数据

以 Anthropic 技能为例：

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

Remotion 技能使用相同格式，但来源是 `remotion-dev/skills`；`guizang-ppt-skill` 和 `guizang-social-card-skill` 分别使用 `op7418/guizang-ppt-skill`、`op7418/guizang-social-card-skill`，两者源码都位于上游仓库根目录，因此 `upstreamPath` 填 `.`。`upstreamSha` 是上一次已审核的基线提交，不使用浮动分支内容作为发布依据。未声明这些字段的技能（例如内部上传技能）不会被自动覆盖，仍由仓库维护者通过普通 PR 更新。

同步脚本会：

- 拉取当前上游提交；
- 用 `upstreamSha` 作为基线做文本三方合并；
- 自动复制新增、删除且未被本地修改的文件；
- 对本地和上游同时修改的文本保留冲突标记，交给 PR 评审；
- 只有无冲突时才更新 `upstreamSha`。

## Skill Gate 检查项

`ruby scripts/validate_skills.rb` 不依赖 npm 包，主要检查：

- `SKILL.md` 必须有可解析的 YAML frontmatter、`name`、`description`，且名称与目录一致；
- 未加引号的 description 冒号等 YAML 语法错误；
- `marketplace.json` 的 schema、技能名、版本、存储键、媒体数量和媒体路径；
- 媒体文件不能逃逸技能目录，技能目录名称不能重复；
- 常见 GitHub/GitLab/GCS/OpenAI 凭据、私钥和合并冲突标记；
- 上游元数据的仓库格式、路径和提交号。

本地提交前可运行：

```shell
ruby scripts/validate_skills.rb --self-test
ruby scripts/validate_skills.rb
ruby scripts/sync_upstreams.rb
```

同步 PR 合并后，仓库只完成源码备份和审查；生产版本仍由管理员按照现有 OpenC3 发布配置在内部发布仓库打 `release-online-*` tag。对象存储只作为发布产物和下载分发层，仓库是可审计的源代码备份。

## 让门禁真正阻断合并

工作流本身会在 PR 页面报告失败；仓库管理员还需要在 GitHub 的 Rulesets/分支保护中把 **Skill Gate / Validate skills** 设为 `main` 的 required status check，并禁止绕过该规则。同步 PR 使用仓库的 `GITHUB_TOKEN`，若创建 PR 被拒绝，需要在仓库设置中允许 GitHub Actions 创建 pull request。
