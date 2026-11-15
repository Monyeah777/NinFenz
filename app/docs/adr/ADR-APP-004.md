# ADR-APP-004：Pack = base + overlay；更新走 diff / merge / 回滚

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-004 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

Pack 是可分发内容包，但用户会改条款开关/参数/预设/自定义资产。若 Pack 本身可变：升级会覆盖用户改动；若用户 fork：合并不可控。需要一种「内容可整体替换、用户改动不丢、失败可回滚」的结构。

## 决策

1. Pack 分三层 kind：`base`（只读内容）/ `template`（模板包）/ `overlay`（用户覆盖层）；同 id 不同 version 并存，`latest` 指针单独文件。
2. 用户改动一律落 overlay（条款开关/参数/预设/自定义资产），以稳定 ID（clause/field/slot/node 的 id）迁移。
3. 更新 = `pack-diff`（added/removed/modified 按 path 升序，impact = 受影响项目 + overlay 键，breaking = 删除或 schema 变更）→ 冲突裁决 → `pack-merge`（备份 → 原子替换 → 复验 → 失败回滚；旧版保留）。
4. 冲突三类（删除/重命名/schema 变更）必须进 `conflicts[]` 并要求用户决定，默认 `defer`；未裁决 → `NF-PCK-006` 不应用。不得静默丢本地改动。
5. 同 `id+version` 不同 digest = 篡改/冲突 → `NF-PCK-004`（exit 3），不覆盖安装。

## 后果

**正面**

- base 可整体替换，用户改动（overlay）不丢。
- 更新可回滚（备份 + 复验 + 旧版保留），失败不会留下半新半旧状态。
- 冲突显式化：三类冲突强制人决定，避免静默丢数据。

**负面 / 代价**

- overlay 迁移规则复杂（尤其重命名与 schema 变更）；实现与测试成本高。
- 存储双份（base + overlay）；备份进一步增加磁盘占用（需配额策略）。
- 冲突 UI/裁决流是端壳必做项，而端壳尚未建（OPEN-TOOLCHAIN）。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. 单一可变 Pack | 否决 | 升级覆盖用户改动；不可回滚 |
| B. 用户 fork 全量 Pack | 否决 | 合并不可控；存储爆炸 |
| C. 仅出补丁文件 | 否决 | 无稳定 ID 语义，重命名/删除无法安全应用 |
| D. 覆盖层用 git 式三方合并 | 否决（暂） | 内容语义（条款开关/槽位）不是行级文本，三方合并会误判 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| 更新/overlay 语义（diff、冲突三类、备份→原子替换→复验→回滚、NF-PCK-004） | `app/docs/CONTRACT.md` §5.9 |
| overlay 结构 | `app/schema/nf-overlay.schema.json` |
| 更新计划结构（changes/impact/merge/conflicts/policy） | `app/schema/nf-pack-update.schema.json` |
| kind 枚举 base/template/overlay 与 items/tree 摘要口径 | `app/schema/nf-pack.schema.json` |
| 错误码 NF-PCK-002/004/005/006/007 | `app/schema/error_codes.json` |
| 用例门禁（update/rollback/conflict） | `app/gates/gates.json` QA3 `q3-update` |

## 复审条件

- 出现第四类冲突（如资产二进制替换）时。
- overlay 体积/备份占用超预算时（需配额与回收策略）。
- 备份保留/回滚失败处置口径变化时。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
