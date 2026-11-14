# 管线抽象执行（dry-run → GraphSpec）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：判决分层（hard / advisory）与边界**复核不变**；补可核现状（`nf pipeline dryrun --all` 实读）：
> 管线 **114** · 执行模块 **282** · 官方核心基座 **13** · **hard 0 条** · advisory **1142 条**
> （同层依赖序 **2** / 跨包或外部事件 **1134** / 跨包或外部依赖 **6**）· CLI 两个子命令（`new` / `dryrun`）。见「§现状对照」。

## 是什么

**不调模型、不动状态、不写盘**，只用声明跑一遍管线：按层取 `default_modules`，读各模块
`machine_contract` 的 inputs/outputs/events/io_types，产出执行图（steps/edges/tokens/issues/notes）。
此前 NF 只能答"声明自洽吗"，现在能答"跑得通吗"。

## 判决分层（关键）

- **hard**：模块在仓库找不到；依赖的提供方在**严格更后的层**。
- **advisory**：同层依赖序（NF 的 I5 明确"层内顺序由注册表合并裁决"）；依赖/事件由
  **references 跨包闭包或外部域包**提供。

## 怎么用

```bash
python scripts/nf.py pipeline dryrun --pipeline community/西幻生存领域包/pipelines/P03_西幻生存流管线.md
python scripts/nf.py pipeline dryrun --all          # 全仓扫（hard 数即门禁口径）
```

## 现状对照（2026-11-13 · 以 `nf pipeline dryrun --all` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 管线 | **114** | `dryrun --all` 头行 |
| 执行模块 | **282** | 同上 |
| 官方核心基座 | **13**（恒执行） | 同上 |
| hard 缺陷 | **0** | 同上尾行 |
| advisory | **1142**（同层序 2 / 跨包事件 1134 / 跨包依赖 6） | 同上分列 |
| CLI 子命令 | **2**：`new`（脚手架派生）/ `dryrun`（抽象执行） | `nf pipeline --help` |

> 本表只作「当时 → 现行」导航；数字以 `nf pipeline dryrun --all` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py pipeline dryrun --all     # 全仓扫：hard 数即门禁口径
python scripts/nf.py pipeline new <id>         # 自 P00 骨架派生新管线（脚手架）
python -m pytest desktop/tests/test_pipeline_loader.py -q
```

- 引用本文时：「hard 判死、advisory 供人工裁决」= 长期口径；advisory 多不等于坏，但**同一事件反复跨包**要当缺口复审。
- 执行集 = 官方核心基座 ∪ 管线各层模块；dry-run **不调模型、不动状态、不写盘**。

## 边界

- 执行集 = **官方核心基座（registry.json modules[]，恒执行）∪ 管线各层模块**。
- advisory 不判死，但会列出所在模块与事件名，供人工裁决是否为真缺口。
