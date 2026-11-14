<!-- nf-asset: key="TECH_TEMPLATES" version="1.0" status="active" -->
# 资产键 TECH_TEMPLATES · 技术文档章节骨架模板
> 05_资产库/用户自定义 扩展资产（P90 技术文档演示，asset_register 登记于 2026-09-03）

## 读法（本文件怎么用、怎么验）

- **这是什么**：技术文档章节骨架模板的**域中立示例档**——M90 按文档类型选骨架、展开章节；域包可自带模板替换/补充，本示例不是协议。
- **三类读者**：消费方（M90）= `asset_get("TECH_TEMPLATES", doc_type)` 取骨架、`asset_query("TECH_TEMPLATES", doc_type=…)` 查同类型模板；作者 = 按 §schema 新增模板并 `nf asset add` 建档；验收方 = 核对文件头 `nf-asset` 位与 `05_资产库/provenance.json` 台账（check23）。
- **怎么验**：schema required_fields 与 `05_资产库/用户自定义/README.md` §2 速览一致；条目 ID 前缀 T9xx；每条 `required_fields` 必须是 `sections` 的子集（骨架顺序即章节顺序，不得引用不存在的章节）。
- **引用约定**：正文 `§N` 指本文件章节；资产键写大写 `TECH_TEMPLATES`。

## schema
```yaml
key: TECH_TEMPLATES
required_fields: [id, doc_type, sections, required_fields]
field_types:
  id: string
  doc_type: guide|reference|tutorial|note
  sections: [string]
  required_fields: [string]
id_prefix: T9xx   # 用户自定义 900+ 命名空间
```

## 模板语义

- `doc_type` 四类：guide（操作指南）｜reference（参考手册）｜tutorial（分步教程）｜note（一页速记）；模板按类型选骨架，不跨类复用章节序。
- `sections`：章节骨架的**顺序即渲染顺序**（概览在前、修订记录收尾是示例约定，域包可自定义）。
- `required_fields`：该骨架下**必须出现**的章节子集——必须是 `sections` 的子集；缺章节即骨架不完整（M90 装配时应 fail-closed 提示，不静默补章）。

## 条目
| id | doc_type | sections | required_fields |
| --- | --- | --- | --- |
| T901 | guide | [概述, 快速开始, 概念, 操作步骤, 故障排查, 修订记录] | [概述, 修订记录] |
| T902 | reference | [术语表, 参数表, 返回码表, 示例, 修订记录] | [术语表, 修订记录] |
| T903 | tutorial | [目标, 前置条件, 分步练习, 验证, 修订记录] | [目标, 验证] |
| T904 | note | [背景, 要点, 结论, 修订记录] | [要点, 修订记录] |

> 示例模板集：可按域包整体替换/补充（doc_type 四类示例各一）；新增模板须登记 `nf asset add` 并保证 ID 落 T9xx（900+），不改动官方 001-899 区与既有条目语义。

## 校验与机检

- 文件头 `nf-asset`（key/version/status）↔ `05_资产库/provenance.json` 同键台账：check23 三方自证；`nf asset verify` 复核货架单层与台账闭合。
- schema 一致：本文件 `required_fields` / `field_types` ↔ 用户自定义/README §2 速览（防双源漂移，I5）。
- 消费面：M90 经 `asset_get` / `asset_query` 访问（I4 五接口）；模板缺失 fail-closed 不编造骨架；运行时寻址按 allowlist 授权（check16-B）。

> 访问：asset_get("TECH_TEMPLATES","T901") / asset_query("TECH_TEMPLATES", doc_type=guide)（I4 五接口）