# handovers/ · 接力件（**公开面只留模板**）

> 2026-10-25 作者裁决（见 `decisions/ADR-0000-决策记录外置到私有仓.md`）：真实交接件不进公开仓库。
- 真源（真实交接）：私有 Plan 仓 `governance/decisions-archive/handovers/`。
- 本目录保留：本文 + `HO-9xxx` 格式模板（含 1 条带判据的未决项，供 `nf handover verify` 自检）。
- 判据：`test_publish_boundary.py` 断言本目录只有 README / HO-9xxx。

## 本文件怎么读

- **这是什么**：三个内部治理目录（`decisions/` / `handovers/` / `postmortems/`）之一——接力件的**公开面政策说明**。真实交接件在私有 Plan 仓，公开仓只留模板与政策。
- **怎么读**：真实交接 → 私有仓 `governance/decisions-archive/handovers/`；公开面看本文（政策）+ `HO-9000-示例-接力模板.md`（写法模板，含 1 条带判据的未决项）。
- **怎么验**：`nf handover check <件>`（五段齐 / 未决非空且每条带判据 / refs 可解析）、`nf handover verify`（声明 + 全部件）、`nf handover ls`（列状态）、`desktop/tests/test_publish_boundary.py`（目录白名单）、`desktop/tests/test_handover_template_doc_contract.py`（模板 ↔ `protocol/handover.json` ↔ CLI 三方对账）。
- **引用约定**：本目录不出现真实交接编号（仅 `HO-9xxx` 模板位）；协议件是 `protocol/handover.json`。

## 目录白名单（出现其它件即 FAIL）

| 允许件 | 说明 |
|---|---|
| `README.md` | 本文（政策说明） |
| `HO-9xxx-*.md` | 格式模板位（公开面只能是示例/模板，不能是真实交接） |

三类内部材料同一规则：`decisions/` 只留 README/INDEX/ERRATA/ADR-0000/ADR-9xxx；`postmortems/` 只留 README/PO-9xxx。

## 为什么这么定

`STRATEGY.md §四`：公开仓只承载「方向层 / 结果状态 / 面向使用者文档」，计划与过程材料内部消化；
2026-10-25 作者裁决（`decisions/ADR-0000-决策记录外置到私有仓.md`）把决策 / 交接 / 复盘三类真实件迁到私有 Plan 仓，公开仓只留模板。
判据是**白名单**而不是黑名单：目录里只要出现非模板件就红，防止真实交接再次流入。

> **复核（2026-11-14）**：政策、私有仓路径、白名单与判据**与 `decisions/README.md` 同构补齐**（此前本文只有 4 行，缺「怎么读 / 怎么验 / 为什么」）。
