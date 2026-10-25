# decisions/ · 决策记录（**公开面只留模板与格式声明**）

> 2026-10-25 作者裁决（见 `ADR-0000`）：**真实决策记录不进公开仓库**。
> 依据 `STRATEGY.md §四`：公开仓只承载「方向层 / 结果状态 / 面向使用者文档」，计划与决策过程内部消化。

- 真源（真实 ADR）：私有 Plan 仓 `governance/decisions-archive/decisions/`（本地密级档案）。
- 本目录保留：`ADR-0000`（外置决策本身）+ `ADR-9xxx` 格式模板 + `ERRATA.json` + `INDEX.md`（投影）。
- 判据：`desktop/tests/test_publish_boundary.py` 断言本目录**只有** README/INDEX/ERRATA/ADR-0000/ADR-9xxx；
  出现其它 ADR 即红（防止真实决策再次流入公开仓）。
