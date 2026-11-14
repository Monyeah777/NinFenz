# 模块边界冻结（module signature）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：边界字段集 / 冻结语义 / WARN 与 FAIL 分档**复核不变**；补可核现状：
> 模块 **248** · 已签 **248**（全签、无漂移）· 边界字段 **7**（`inputs`/`outputs`/`events`/`interfaces`/`layer`/`category`/`io_types`，
> 真源 `module_signature._BOUNDARY_KEYS`）· 一致性报告契约 `module-signature` 覆盖本面；
> 本文按 `doc_hygiene` 分类为 **how-to**。见「§现状对照」。

## 是什么

模块对外的**承诺**（`inputs` / `outputs` / `events` / `interfaces` / `layer` / `category` /
`io_types`）冻结成基线 `protocol/module_signatures.json`（摘要 + 路径）。
边界改了而没重签 → **FAIL**；这样"顺手改边界"不能悄悄发生（机制借自 Pipelex `signature_for`）。

## 怎么用

```bash
python scripts/nf.py module signature            # 校验（漂移即 FAIL）
python scripts/nf.py module signature --write    # 评审后显式重签
```

## 现状对照（2026-11-13 · 以实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 模块 | **248** | `nf module signature` 头行 |
| 已签 | **248**（全签） | 同上 |
| 边界字段 | **7**：inputs / outputs / events / interfaces / layer / category / io_types | `module_signature._BOUNDARY_KEYS` |
| 漂移 | **0**（漂移即 FAIL） | `nf module signature` 尾行 |
| 一致性报告 | 契约 `module-signature` 覆盖本面 | `nf conformance` |
| 文档分类 | **how-to** | `doc_hygiene` 分类表 |

> 本表只作「当时 → 现行」导航；数字以 `nf module signature` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py module signature   # 校验（漂移即 FAIL；未签/撤下只 WARN）
python scripts/nf.py conformance        # 契约 module-signature 亦覆盖本面
```

- 引用本文时：「边界字段冻结，改了必须显式重签」= 长期口径；字段清单以 `_BOUNDARY_KEYS` 为唯一真相。
- 重签是**评审动作**：`--write` 前先确认边界改动是有意的；`description`/`note` 等易变文本不参与，避免假漂移。

## 边界

- 只取**边界字段**，`description`/`note` 等易变文本不参与（避免假漂移）。
- 未签（新增模块）与撤下（基线有、仓库无）记 WARN；**漂移**才是 FAIL。
