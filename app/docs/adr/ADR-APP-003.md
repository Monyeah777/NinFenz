# ADR-APP-003：Wiki / Spec / Pack 单一真源：APP 只按 ID+digest 引用

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-003 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

仓库根已有内容真源：`01`–`07`、`03_管线库/`、`04_模块库/`、`05_资产库/`、`protocol/**`（9 件 schema + 5 件 production schema + 台账）。APP 若复制内容：出现第二真源，任何一处更新都会漂移；若不复制而只引用：需要可核的引用钉与离线可用性方案。

## 决策

1. 内容真源只在仓库根；APP 不复制协议/模块/资产内容，只新增**作者态/装配态/交付态**的 13 个格式（`app/schema/`）。
2. 所有跨文件引用用 `{id, version, digest}` 三元组；digest 缺一不可，unknown 引用 fail-closed（`NF-E-002`）。
3. APP 产物不写仓库根、不改 `protocol/**`；改动面判据：`git status` 只出现 `app/**` 与 `results/app/**`。
4. 离线分发需要自带内容快照时，唯一受控例外 = `nf-template/1` 内嵌 protocol/spec 快照 + hashes（模板包自带 digest，可对账）。
5. 与既有生产平面同名不同物：`nf-assembly-plan/1` ≠ `protocol/production/assembly.schema.json`；桥接靠 `graph-compile` + 适配器，不互改 schema。

## 后果

**正面**

- 无第二真源：协议/管线/资产更新只在仓库根发生一次。
- 包体小、离线可分：引用钉让产物可追溯到具体内容版本。
- 篡改可发现：digest 不符即 `NF-PCK-004`/`NF-ASM-001`，不静默采纳。

**负面 / 代价**

- 真源不可达时旧项目打不开（fail-closed 的代价）→ 需要迁移/内置快照工具。
- 模板快照与真源漂移需要额外对账（template hashes 必须可复核）。
- 引用钉让「改一处内容」变成「改 version+digest 链」，作者操作成本上升。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. APP 内复制内容真源 | 否决 | 第二真源，必然漂移；违反单点真相 |
| B. 在线拉取真源 | 否决 | 离线/无账号定位；网络面新增攻击面 |
| C. 以 git submodule 引真源 | 否决 | 移动端不可行；构建链依赖外部仓库 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| 真源清单与「APP 新增格式」边界 | `app/docs/CONTRACT.md` §1 |
| 与既有格式逐行对照（不同物/桥接方式） | `app/docs/CONTRACT.md` §9 |
| 引用钉与 canonical/digest 口径 | `app/docs/CONTRACT.md` §2 |
| 13 格式 schema（nf-pack 只存摘要；nf-template 内嵌快照+hashes） | `app/schema/nf-pack.schema.json`、`app/schema/nf-template.schema.json` |
| 既有真源位置 | `protocol/schema/*.json`、`protocol/production/*.schema.json` |
| 仓库既有威胁范式（外来内容按数据处理） | `docs/production/THREAT_MODEL.md` |

## 复审条件

- 真源格式升版或拆分时（引用链/迁移需同步）。
- template 快照与真源 digest 漂移被检出时。
- 出现「APP 需要写真源」的强需求时（应改仓库流程，不是改 APP）。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
