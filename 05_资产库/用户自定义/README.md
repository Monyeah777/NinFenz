# 05_资产库/用户自定义 · 扩展资产包
> 位置：05_资产库/用户自定义/（扩增协议槽，见 05_资产库/README §5）
> 承载：官方核心机制资产（域中立，M80/M90 消费；经 asset_register 登记）。

## 读法（本文件怎么用、怎么验）

- **这是什么**：用户自定义扩展槽的**登记面**——键清单 + schema 速览 + 登记记录；条目字段真源是各资产文件（本表只是投影，冲突以资产文件为准，I5）。
- **三类读者**：消费方 = 经五接口取条目（如 `asset_get("TECH_RULES","R901")`）；作者 = 按 §1 键 + §2 schema + 900+ 后缀新增，再 `nf asset add` 建档；验收方 = 跑 `nf asset verify` 与 check23。
- **怎么验**：键在 `protocol/asset_keys.json` 词表在册（§1）；条目字段合 §2 schema（真源 = 各资产文件的字段声明段，逐键对账）；台账 `05_资产库/provenance.json` 的 key/version/status 与文件头 `nf-asset` 位一致（check23 三方自证）；货架单层（不建子目录）→ `nf asset verify` 硬规。
- **引用约定**：正文 `§N` 指本文件章节；资产键一律大写；条目 ID 前缀见 §2（T9xx / R9xx）。

## 1. 资产键清单
| 资产键 | 文件 | schema（速览） | 条目后缀 |
| --- | --- | --- | --- |
| STYLE_DNA | STYLE_DNA.md | {dna_id, name, rule, applies_to} | 用户自定（示例档见 STYLE_DNA.md §3） |
| TECH_TEMPLATES | TECH_TEMPLATES.md | {id, doc_type, sections[], required_fields[]} | T9xx（900+） |
| TECH_RULES | TECH_RULES.md | {id, rule_type, check, action} | R9xx（900+） |

> schema 真源 = 各资产文件里的字段声明（TECH_TEMPLATES / TECH_RULES 的 `## schema` 段；STYLE_DNA 见其 §2 资产键表与 §3 示例档）——本表是速览投影，冲突以资产文件为准。

## 2. 条目 schema 速览（真源 = 各资产文件）
| 资产键 | required_fields | field_types | id_prefix |
| --- | --- | --- | --- |
| STYLE_DNA | dna_id, name, rule, applies_to | dna_id: string；name: string；rule: string；applies_to: [string] | 用户自定 |
| TECH_TEMPLATES | id, doc_type, sections, required_fields | id: string；doc_type: guide\|reference\|tutorial\|note；sections: [string]；required_fields: [string] | T9xx |
| TECH_RULES | id, rule_type, check, action | id: string；rule_type: structure\|terminology\|reference\|revision；check: string；action: warn\|fail | R9xx |

## 3. 登记记录
- 2026-09-03：经 asset_register 登记 TECH_TEMPLATES / TECH_RULES（用户自定义 900+ 命名空间，不触碰官方 001-899 区）。
- 2026-10-13：补登记 STYLE_DNA（M80 双门重构 2026-09-08 引入）——键并入 protocol/asset_keys.json，台账并入 05_资产库/provenance.json，文件头补 nf-asset 位。

## 4. 文件头与台账对账（check23）
- 每份资产文件头带 `<!-- nf-asset: key="..." version="..." status="..." -->` 机读位；`05_资产库/provenance.json` 同键记录 version/status/source，两处一致（check23 逐次自证）。
- 新增/变更经 `nf asset add` 建档（asset_register 语义），禁止手改台账绕过（check23 键无孤儿）。

## 5. 校验与机检
- `nf asset verify`：货架单层（非递归 glob）+ 台账闭合 + 键无孤儿。
- verify check23：资产供应链闭合门禁（本目录 → provenance.json → 文件头三方一致）。
- 键词表：`protocol/asset_keys.json`（键在册才有发现面；scope=user_asset）。

## 6. 三原则（05_资产库/README §5）
不覆盖官方条目 / 不污染官方命名空间 / 可追溯（本 README + 文件头 + provenance.json 即溯源记录）。
- **机器台账（40 总纲 v2.7 波A S2）**：本资产根 05_资产库/provenance.json 为溯源键表 + version/status 位的机读真相，由 `nf asset add` 建档维护、`nf asset verify` / verify check23 逐次自证。
