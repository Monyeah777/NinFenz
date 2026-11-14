# decisions/ · 决策记录（**公开面只留模板与格式声明**）

> 2026-10-25 作者裁决（见 `ADR-0000`）：**真实决策记录不进公开仓库**。
> 依据 `STRATEGY.md §四`：公开仓只承载「方向层 / 结果状态 / 面向使用者文档」，计划与决策过程内部消化。

## 本文件怎么读

- **这是什么**：三个内部治理目录（`decisions/` / `handovers/` / `postmortems/`）的**公开面政策说明**——真实件在私有 Plan 仓，公开仓只留模板、政策与投影。
- **怎么读**：真实决策 → 私有仓 `governance/decisions-archive/decisions/`；公开面看 `ADR-0000`（外置政策）+ `ADR-9xxx`（写法/证据纪律模板）+ `INDEX.md`（投影表）+ `ERRATA.json`（勘误，只改引用指针）。
- **怎么验**：`desktop/tests/test_publish_boundary.py`（目录白名单：出现非模板件即 FAIL）、`nf decisions verify`（ID/必填段/证据可解析/回执锚定/INDEX 投影）、check33（新面汇总的决策层面）、`packaging/npm/tools/payload-policy.mjs` 的 `INTERNAL_DIRS`（发布物同样拒绝三目录）。
- **引用约定**：正文 `§N` 指本文件章节；公开仓不出现真实 ADR 编号（仅 `ADR-0000` 与 `ADR-9xxx` 模板位）。

- 真源（真实 ADR）：私有 Plan 仓 `governance/decisions-archive/decisions/`（本地密级档案）。
- 本目录保留：`README.md`（政策说明）+ `ADR-0000`（外置决策本身）+ `ADR-9xxx` 格式模板 + `ERRATA.json` + `INDEX.md`（投影）。
- 判据：`desktop/tests/test_publish_boundary.py` 断言本目录**只有** README/INDEX/ERRATA/ADR-0000/ADR-9xxx；
  出现其它 ADR 即红（防止真实决策再次流入公开仓）。

## 自动化路由（2026-10-25）

不要再手工复制：用私有 Plan 仓的路由工具（**默认 dry-run**）。

> 说明：该工具随私有 Plan 仓分发，**公开仓不包含**；下面用 `<私有仓>` 占位（本机示例根 = `D:/NF-Plan/`）。

```
python <私有仓>/tools/decision-archive-router.py check              # 检查公开仓是否混入真实件
python <私有仓>/tools/decision-archive-router.py archive --apply    # 归档到 Plan + 产品仓删除
python <私有仓>/tools/decision-archive-router.py new --title "..."  # 直接在 Plan 新建决策（编号自增）
python <私有仓>/tools/decision-archive-router.py hook --install     # 装 pre-commit 阻断
```

## 判据与入口

- 目录白名单：`desktop/tests/test_publish_boundary.py`（decisions/ handovers/ postmortems/ 三目录正则；白名单见该文件 `PATTERNS`）。
- 决策语义：`desktop/tests/test_decisions.py` + `nf decisions verify`（配 `nf decisions show <id>` 看单条、`nf decisions reindex` 重建 INDEX）。
- 发布面：`packaging/npm/tools/payload-policy.mjs` 的 `INTERNAL_DIRS` 拒绝三目录进入 npm payload。
- 勘误：`decisions/ERRATA.json`（schema `nf-decisions-errata/1`，只登记引用指针类更正，不改 ADR 正文）。
- 入口：`ADR-0000`（外置政策）/ `ADR-9000`（格式模板）/ `ADR-9001`（证据纪律）/ `INDEX.md`（投影表）。
