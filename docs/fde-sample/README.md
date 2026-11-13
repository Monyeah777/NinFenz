# FDE 交付样例（可跑 · 可复算）

> 定位：证明「NF 是 FDE 的 AI infra 中游标准」——一次完整交付从 **brief** 走到 **证据包**，全程本地、确定性、无网络。
> 栈位说明见 [`../fde-stack.md`](../fde-stack.md)。本样例是那条契约的一次真实行走。
> **最后更新：2026-11-13（复核）**：五道门与两条命令**复核不变**；补机读现状（`evidence/manifest.json`）：
> 声明面 **6** · schema↔data 对 **2** · 概念图 **48 节点 / 拓扑序 47** · 证据强度 **external** · 装配链 **4 件** ·
> 标准锚 **370** · `issues` 空；`--check` 绿（门 5 · 证据件 4）。见「§现状对照」。

## 一、样例对象

| 项 | 值 |
|---|---|
| 域包 | `community/AI系统域包`（系统卡 + 概念图 48 节点 + 闭包产物 + 自带装配流 P07） |
| 交付形态 | 技术文档（techdoc）——交付物 `evidence/deliverable.md` |
| 客户侧输入 | [`brief.md`](brief.md)（客户需求） |
| 照做步骤 | [`run.md`](run.md)（命令原文 + 期望输出 + 退出码） |
| 证据 | `evidence/`：`deliverable.md` · `gates.txt` · `result.jsonl` · `manifest.json` |

## 二、怎么跑（两条命令）

```bash
python scripts/fde_sample_run.py --run     # 跑一遍并落证据（幂等：可重复跑）
python scripts/fde_sample_run.py --check   # 逐字节比对证据与当前仓库状态（防样例腐烂）
```

## 三、五道门（样例的验收判据）

| 门 | 判据 | 为什么它算「中游」证据 |
|---|---|---|
| G1 | 包内 `outputs/INDEX.json` 声明的产出面全部在场且可解析 | 交付面不是口头承诺，是声明 + 实物 |
| G2 | T2 schema ↔ T3 data 逐对通过 JSON Schema 子集校验 | 客户拿到的产物有契约，不是自由文本 |
| G3 | `assets/CONCEPT_GRAPH.md` 概念图健康（无环 / 无悬空 / 别名唯一 / 分支完备） | 装配前提可机检 |
| G4 | 装配链四件（protocol.yaml + 管线 + 两模块）在场可指认 | 交付过程可被第三方照做 |
| G5 | `nf stats --check` 与 `geo_export.py --check` 同时绿 | 交付所引用的数字与标准锚都是实算生成物 |

**当前实跑结果**（`evidence/gates.txt`）：五门全 PASS——G3 的图规模 48 节点 / 拓扑序 47 / 证据强度 `external`；G5 覆盖 370 条标准锚。

## 现状对照（2026-11-13 · 以证据件实读为准）

| 面 | 本文声明 | 复核结果（读到本行时请重跑 `--check`） |
|---|---|---|
| G1 声明面 | 「全部在场且可解析」 | **声明面 6 · 缺失 0 · 不可解析 0**（`facts.declared_outputs=6`） |
| G2 schema↔data | 「逐对通过」 | **2 对 · 不合规 0**（`facts.schema_pairs=2`） |
| G3 概念图 | 48 节点 / 拓扑序 47 / external | **48 / 47 / external**（`facts.concept_nodes/topo_len/provenance_strength`） |
| G4 装配链 | 四件在场 | **4 件 · 缺 0** |
| G5 中游出口 | stats + geo 双绿、370 锚 | **问题 0 / 问题 0**；`facts.standards=370` |
| 证据件 | `evidence/` 四件 | **4 件**（deliverable / gates / result / manifest；manifest 自身不计入 artifacts） |
| 自检 | `--check` 防腐烂 | **绿**（门 5 · 证据件 4） |
| 门禁位置 | 未写 | **check32 子扫描 `fde_sample`**（`verify.sh --checks-only` 内） |

> 本表只作「当时 → 现行」导航，不替代 `--check` 实跑。

## 复现与引用口径

```bash
python scripts/fde_sample_run.py --check   # 逐字节比对证据与当前仓库状态（0=一致）
python scripts/fde_sample_run.py --run     # 重跑并落证据（幂等；改仓库状态后才需要）
```

- 引用本文时：「brief → 证据包全程本地确定性 + 五门可机检」= 长期口径；数字以 `evidence/manifest.json` 实读为准。
- `--check` 失败即样例腐烂：先重跑 `--run`；若 `--run` 报门失败，按门名定位（G1 产出面 / G2 契约 / G3 图 / G4 装配链 / G5 自述与 GEO）。

## 四、复算与失败处置

- 任一 `--check` 报 FAIL → 说明仓库状态变了而证据未刷新：重跑 `--run`；若 `--run` 本身报 FAIL（G1–G4），按门名定位（G1 产出面缺失 / G2 契约违规 / G3 图缺陷 / G4 装配链缺件）。
- G5 失败通常意味着自述数字或 GEO 出口落后：先跑 `python scripts/nf.py stats --write` 与 `python scripts/geo_export.py --write`。
- 本样例**不引入新真源**：全部输入来自域包自身产物与协议层声明。
