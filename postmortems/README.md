# postmortems/ · 复盘件（**公开面只留模板**）

> 2026-10-25 作者裁决（见 `decisions/ADR-0000-决策记录外置到私有仓.md`）：真实复盘件不进公开仓库。
- 真源（真实复盘）：私有 Plan 仓 `governance/decisions-archive/postmortems/`。
- 本目录保留：本文 + `PO-9xxx` 格式模板（含行动项与判据，供 `nf postmortem verify` 自检）。
- 判据：`test_publish_boundary.py` 断言本目录只有 README / PO-9xxx。


## 本文件怎么读

这是三个内部治理目录（`decisions/` / `handovers/` / `postmortems/`）之一的**公开面政策说明**。真实复盘件在私有 Plan 仓归档，公开仓只留模板与政策，与 `decisions/README.md`、`handovers/README.md` 同构。

## 目录白名单（出现其它件即 FAIL）

| 允许件 | 说明 |
|---|---|
| `README.md` | 本文（政策说明） |
| `PO-9xxx-*.md` | 格式模板位（公开面只能是示例/模板，不能是真实复盘） |

三类内部材料同一规则：`decisions/` 只留 README/INDEX/ERRATA/ADR-0000/ADR-9xxx；`handovers/` 只留 README/HO-9xxx。

## 为什么这么定

`STRATEGY.md §四`：公开仓只承载「方向层 / 结果状态 / 面向使用者文档」，计划与过程材料内部消化；2026-10-25 作者裁决（`decisions/ADR-0000-决策记录外置到私有仓.md`）把决策 / 交接 / 复盘三类真实件迁到私有 Plan 仓。判据是**白名单**而不是黑名单：目录里只要出现非模板件就红。

## 怎么验

| 判据 | 覆盖 | 命令 |
|---|---|---|
| `test_publish_boundary.py` | 本目录只允许 README + PO-9xxx | `python -m pytest desktop/tests/test_publish_boundary.py -q` |
| `nf postmortem check` | 单件：四段 / 无指责 / 根因指向机制 / 行动项带负责人与判据 | `python scripts/nf.py postmortem check postmortems/PO-9000-示例-复盘模板.md` |
| `nf postmortem verify` | 声明 + 全部复盘件一致 | `python scripts/nf.py postmortem verify` |
| `test_postmortem_template_doc_contract.py` | 模板：四段顺序 / **项目符号恰 1 条**（全文 `- ` 行都算行动项） | `python -m pytest desktop/tests/test_postmortem_template_doc_contract.py -q` |

> **复核（2026-11-14）**：政策、私有仓路径、白名单与判据**与 `decisions/README.md` / `handovers/README.md` 同构补齐**（此前本文只有 4 行，同层三个目录里唯独它缺「怎么读 / 白名单 / 为什么 / 怎么验」）。
