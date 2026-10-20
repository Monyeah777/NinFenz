# 05_资产库/用户自定义 · 扩展资产包
>
> 位置：05_资产库/用户自定义/（扩增协议槽，见 05_资产库/README §5）
> 承载：官方核心机制资产（域中立，M80/M90 消费；经 asset_register 登记）。

## 1. 资产键清单

| 资产键 | 文件 | schema | 条目后缀 |
| --- | --- | --- | --- |
| STYLE_DNA | STYLE_DNA.md | {dna_id, name, rule, applies_to} | 用户自定（示例档见文件 §3） |
| TECH_TEMPLATES | TECH_TEMPLATES.md | {id, doc_type, sections[], required_fields[]} | T9xx（900+） |
| TECH_RULES | TECH_RULES.md | {id, rule_type, check, action} | R9xx（900+） |

## 2. 登记记录

- 2026-09-03：经 asset_register 登记 TECH_TEMPLATES / TECH_RULES（用户自定义 900+ 命名空间，不触碰官方 001-899 区）。
- 2026-10-13：补登记 STYLE_DNA（M80 双门重构 2026-09-08 引入）——键并入 protocol/asset_keys.json，台账并入 05_资产库/provenance.json，文件头补 nf-asset 位。

## 3. 三原则（05_资产库/README §5）

不覆盖官方条目 / 不污染官方命名空间 / 可追溯（本 README 即溯源记录）。

- **机器台账（40 总纲 v2.7 波A S2）**：本资产根 05_资产库/provenance.json 为溯源键表 + version/status 位的机读真相，由 `nf asset add` 建档维护、`nf asset verify` / verify check23 逐次自证。
