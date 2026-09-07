# Image Prompt Style Library Reference

改造自 awesome-gpt-image-2 风格库（MIT License © 2026 liyue-aigc / freestylefly），适配 Easy Code Agent 工作流。

## 模板总览（22 套）

| ID | 模板名 | 分类 | 适用 |
|---|---|---|---|
| ui-screenshot-system | UI 截图系统 | UI & Interfaces | App截图、仪表盘、社媒截图 |
| infographic-engine | 信息图引擎 | Charts & Infographics | 解释图、技术图解、知识卡片 |
| scientific-scale-diagram | 科学尺度缩放图 | Charts & Infographics | 微观到宏观尺度科普 |
| poster-layout-system | 海报排版系统 | Posters & Typography | 活动海报、封面、社媒传播 |
| sports-campaign-poster | 运动商业 Campaign | Posters & Typography | 运动品牌、运动员海报 |
| conceptual-typography-poster | 概念字体海报 | Posters & Typography | 标题即主视觉 |
| ink-double-exposure-poster | 水墨双重曝光海报 | Posters & Typography | 诗意人像、水墨氛围 |
| nature-science-poster | 自然科普海报 | Posters & Typography | 自然主题高级科普 |
| product-commerce-visual | 商品商业视觉 | Products & E-commerce | 商品主图、包装、详情页 |
| personalized-beauty-report | 个性化美妆报告 | Products & E-commerce | 美妆推荐、肤质报告 |
| brand-identity-package | 品牌身份包 | Brand & Logos | Logo 系统、VI 套件 |
| brand-touchpoint-board | 品牌触点视觉板 | Brand & Logos | 多触点 Campaign 展示 |
| architecture-space | 建筑与空间 | Architecture & Spaces | 室内、建筑表现、城市地图 |
| realistic-photography | 写实摄影 | Photography & Realism | 人像、街拍、商品摄影 |
| street-accident-moment | 街头意外瞬间摄影 | Photography & Realism | 街头抓拍、手机纪实 |
| illustration-art-style | 插画与艺术风格 | Illustration & Art | 动漫、水彩、水墨、风格实验 |
| character-design-sheet | 角色设定表 | Characters & People | 角色三视图、动作网格 |
| 3d-collectible-toy | 3D 收藏玩具 | Characters & People | 收藏公仔、潮玩、盲盒 |
| scene-storytelling | 场景叙事 | Scenes & Storytelling | 分镜、世界观、情绪叙事 |
| history-classical-themes | 历史与古风题材 | History & Classical Themes | 古风长卷、朝代服饰、诗词视觉 |
| document-publishing | 文档与出版物 | Documents & Publishing | 白皮书、手册、百科图鉴 |
| concept-product-breakdown | 概念产品研发拆解 | Other Use Cases | 拆解图、研发视觉板 |

## 选择规则

1. 先匹配显式产品类型 → 模板分类（product / poster / UI / infographic / brand / photography / character / document）
2. 再匹配视觉词 → Styles 标签（realistic / 3D / illustration / classical / brand / poster / UI）
3. 再匹配语境词 → Scenes 标签（commerce / education / social / food / travel / story / history / tech / creative / fashion）
4. 需求模糊时，提供 2-3 个最强的模板方向并询问用户选择，再写最终提示词
5. 最终输出必须包含：所选模板名 + 可直接复制的完整提示词 + 文字/画幅/版式/负面约束

## 风格标签关键词表

| 标签 | 中文 | 触发关键词 |
|---|---|---|
| 3D | 3D | 3d, render, figure, 玩具, 公仔 |
| Brand | 品牌 | brand, logo, identity, 品牌, 标志 |
| Character(s) | 角色/人物 | character, avatar, mascot, 角色, 人物, ip |
| Charts | 图表 | chart, diagram, graph, 图表, 数据 |
| Classical | 古典 | classical, ink, scroll, 古风, 水墨, 长卷 |
| Documents | 文档 | document, manual, handbook, 白皮书, 手册 |
| History | 历史 | history, dynasty, ancient, 历史, 唐宋 |
| Illustration | 插画 | illustration, anime, watercolor, 插画, 漫画 |
| Infographic | 信息图 | infographic, knowledge, map, 信息图, 图谱 |
| Photography | 摄影 | photo, camera, lens, 摄影, 相机 |
| Poster | 海报 | poster, cover, typography, 海报, 封面 |
| Product(s) | 商品 | product, packaging, 商品, 包装 |
| Realistic | 写实 | photo, realistic, camera, 写真, 写实 |
| Scenes | 场景 | scene, world, storyboard, 场景, 世界观 |
| UI | 界面 | ui, interface, dashboard, 界面, 截图 |

## 场景标签关键词表

| 标签 | 中文 | 触发关键词 |
|---|---|---|
| Creative | 创意 | 创意, 实验, 概念 |
| Tech | 科技 | ai, rag, tech, data, 技术, 数据 |
| Commerce | 商业 | product, brand, ad, campaign, 商品, 商业, 广告 |
| Education | 教育 | guide, atlas, science, learning, 学习, 科普 |
| Social | 社媒 | social, wechat, 朋友圈, 社媒 |
| Fashion | 时尚 | fashion, clothing, portrait, 服饰, 写真 |
| Food | 食品饮品 | food, drink, coffee, tea, 餐厅, 咖啡, 茶 |
| Travel | 旅行 | city, map, street, 城市, 地图, 街头 |
| Story | 叙事 | story, scene, world, 故事, 场景 |
| History | 历史 | history, dynasty, ancient, 历史, 古希腊, 唐 |

## 来源与许可

- 上游项目：https://github.com/freestylefly/awesome-gpt-image-2 （MIT License）
- 本文件为衍生改造版本，遵循原仓库 MIT 许可证的署名要求。
