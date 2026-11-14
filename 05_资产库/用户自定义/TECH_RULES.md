<!-- nf-asset: key="TECH_RULES" version="1.0" status="active" -->
# 资产键 TECH_RULES · 技术文档规范校验规则
> 05_资产库/用户自定义 扩展资产（P90 技术文档演示，asset_register 登记于 2026-09-03）

## 读法（本文件怎么用、怎么验）

- **这是什么**：技术文档规范校验规则的**域中立示例档**（官方首批入库战例）——供 M90 结构装配做一致性校验；域包可自带规则集替换/补充，本示例不是协议。
- **三类读者**：消费方（M90）= 经 `asset_get("TECH_RULES", id)` 取单条、或 `asset_match("TECH_RULES", DocState)` 做匹配校验；作者 = 按 §schema 新增规则并 `nf asset add` 建档；验收方 = 核对文件头 `nf-asset` 位与 `05_资产库/provenance.json` 台账（check23）。
- **怎么验**：schema required_fields 与 `05_资产库/用户自定义/README.md` §2 速览一致；条目 ID 前缀 R9xx；规则 check 须**可判定**；键在 `protocol/asset_keys.json` 在册（scope=user_asset）。
- **引用约定**：正文 `§N` 指本文件章节；资产键写大写 `TECH_RULES`。

## schema
```yaml
key: TECH_RULES
required_fields: [id, rule_type, check, action]
field_types:
  id: string
  rule_type: structure|terminology|reference|revision
  check: string
  action: warn|fail
id_prefix: R9xx   # 用户自定义 900+ 命名空间
```

## 规则语义

- `rule_type`：structure（章节结构）｜terminology（术语一致）｜reference（引用闭合）｜revision（修订记录）四类；跨类规则请拆成多条，不混用。
- `check`：**可判定**的检查描述（可机器或人逐条核验）；禁止写「风格要好」这类无判定标准的主观要求。
- `action`：warn（提示，可自纠）｜fail（硬错，进入 M80 fail 路径——整段重写，连续 3 次降级最小可读）；判定后的门禁动作以 M80 §3 `gate_action` 为唯一真源，本文件只声明规则与档位。

## 条目
| id | rule_type | check | action |
| --- | --- | --- | --- |
| R901 | structure | 每个章节至少 1 个 body_ref，无孤儿节标题 | fail |
| R902 | terminology | 术语首现须登记 terms 表，全文同词同义 | warn |
| R903 | reference | link_refs / code_refs 全部闭合（无死链/悬空引用） | fail |
| R904 | revision | 每次变更须追加修订记录（ver/date/change） | warn |

> 示例规则集：可按域包整体替换/补充；新增规则须登记 `nf asset add` 并保证 ID 落 R9xx（900+），不改动官方 001-899 区与既有条目语义。

## 校验与机检

- 文件头 `nf-asset`（key/version/status）↔ `05_资产库/provenance.json` 同键台账：check23 三方自证；`nf asset verify` 复核货架单层与台账闭合。
- schema 一致：本文件 `required_fields` / `field_types` ↔ 用户自定义/README §2 速览（防双源漂移，I5）。
- 消费面：M90 经 `asset_get` / `asset_match` 访问（I4 五接口）；运行时寻址按 allowlist 授权（check16-B）。

> 访问：asset_get("TECH_RULES","R901") / asset_match("TECH_RULES", DocState)（I4 五接口）