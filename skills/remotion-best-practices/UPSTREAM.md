# 上游来源与维护规则

- 上游仓库：<https://github.com/remotion-dev/skills>
- 固定版本：`54e9b19a612897171e0b3b242e01c2badba4a272`
- 导入日期：2026-09-02
- 导入范围：上游 `skills/remotion-best-practices/` 的完整复合包。

这个技能包包含总入口和嵌套的专题资料。必须整体发布为一个商城技能，不能将其中的子目录拆成独立 ZIP；它们之间依赖相对 Markdown 链接。

为避免提交第三方访问值，`remotion-docs/REFERENCE.md` 已改为使用官方文档站点搜索或受限网页搜索。其余上游内容保持目录结构不变。

后续升级必须固定新的上游 commit，经引用完整性、敏感信息和许可证复核后，以内部 Merge Request 导入；不得自动追随上游 `main` 或直接从上游写入 GCS。
