<!-- nf-asset: key="STANDARDS_ANCHORS" version="1.0" status="active" -->
# 资产键 STANDARDS_ANCHORS · 技术文档标准锚点

> 资产键：`STANDARDS_ANCHORS`｜归属：技术文档域包（P06）｜消费方：`gate_profiles/techdoc-strict.json`（clause.source 的出处对账）、M90 结构装配（结构合法性依据）、人工评审（条款溯源）。
> 可达性口径（如实声明）：本件为**文档锚**——登记标准编号/条款位置与映射关系；**未做**逐条 URL 本机可达性实测（本包资产线不承担外部实测，实测由作者显式触发；不假装可达）。标准正文以发布机构正式版本为准。

## 1. DITA 1.3 元素映射（Markdown 等价形）

| DITA 元素/概念 | 本域包 Markdown 等价形 | 判据/模板 | profile 条款 |
|---|---|---|---|
| topic / title | 文档唯一 H1 标题 | 标题唯一 | `DITA-1.3-TITLE-01` |
| topic id / @id | 标题显式锚 `{#id}` | 锚可寻址 | `DITA-1.3-TOPIC-ID-ANCHOR` |
| section / title | `##` / `###` 章节标题 | 同级标题唯一、层级不跳 | `DITA-1.3-TOPIC-ID-01` / `GB-19678-HIER-01` |
| shortdesc | 标题下一行 blockquote 简摘 | 简摘在场 | `DITA-1.3-SHORTDESC-01` |
| xref / conref | 文内链接 `[文字](#锚)` | 目标可寻址 | `DITA-1.3-CONREF-01` |
| task / steps | 操作/安装章节有序列表 | 有序步骤 | `DITA-1.3-TASK-STEPS-01` |
| topic type（information type） | `> 文档类型：<type>` 声明 | 白名单 | `DITA-1.3-DOCTYPE-01` |

## 2. GB/T 19678.1-2018 主题锚

| 标准主题（条款域） | 本域包能力面 | 判据/模板 | profile 条款 |
|---|---|---|---|
| 使用说明书的构成（结构完整） | 安全/开箱/安装/操作/故障/规格六类章节 | 必备章节齐全 | `GB-19678-STRUCT-01` |
| 术语与定义 | `TECH_GLOSSARY` 术语表资产 + 术语表章节 | 术语表表格化 | `GB-19678-GLOSSARY-01` |
| 术语首次使用 | 首用即定义（术语表或就地括注） | 首用定义 | `GB-19678-TERM-01` |
| 术语一致性 | 规范术语与别名不并存 | 别名一致性 | `GB-19678-TERM-02` |
| 层次编号 | H1–H4 递进、不跳级 | 层级判据 | `GB-19678-HIER-01` / `GB-19678-HIER-02` |
| 修订记录 | 版本递增 + ISO 8601 日期 + 变更摘要 | 修订追溯 | `GB-19678-REVISION-01` / `GB-19678-REVISION-02` |
| 安全信息分级 | 危险/警告/注意三级信号词 | 警示标签在场 | `GB-19678-SAFETY-01` |

## 3. Microsoft Style Guide 条目锚

| 指南条目 | 本域包规则 | profile 条款 |
|---|---|---|
| Headings（句式大小写、陈述式） | S1 标题句式 | `MS-STYLE-HEADING-SENTENCE` |
| Headings（标点） | S2 标题末尾标点 | `MS-STYLE-HEADING-PUNCT` |
| Spacing | S3 单空格 | `MS-STYLE-SPACE-01` |
| Abbreviations | S4 缩写首用定义 | `MS-STYLE-ABBR-01` |
| Clear wording（避免含糊） | S5 弱表达 | `MS-STYLE-WEAK-01` |
| Release-ready content | S6 占位符清零 | `MS-STYLE-PLACEHOLDER-01` |
| Lists | S7 列表标记 | `MS-STYLE-LIST-01` |
| Code examples | S8 围栏成对 | `MS-STYLE-FENCE-01` |
| Tables | S9 表格列数 | `MS-STYLE-TABLE-01` |

## 4. 条款到机器的边界（如实）

- 本表只做**条款→可机检形状**的映射：每条 profile clause 的 `source.standard` 都能在本表找到对应行；不把「符合标准」写成结论——结论由 `nf assemble --check` 与 profile 报告给出。
- 标准正文的语义判断（例如某句警示是否充分）不在机器判据内，由人工评审按本表条款位置核对。
- 外部标准版本升级时：先更新本表与 profile 条款，再重签 `package.version`，不静默改判据。
