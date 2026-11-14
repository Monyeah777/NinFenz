# NF 决策记录索引（INDEX）

## 本文件怎么用

- **这是什么**：决策记录的**索引投影**——表格由各 ADR frontmatter 生成（`nf decisions reindex` 重建），表格区（BEGIN/END 标记内）**勿手改**。
- **怎么读**：`accepted` = 生效决策（须已被协议回执锚定）；`proposed` = 示例/提案（公开仓仅 ADR-9xxx 模板与示例）；`superseded` = 已被取代（看「取代」列追链）。
- **怎么验**：`nf decisions verify`（ID/文件名一致、必填段、证据可解析、回执锚定、投影漂移）；`nf decisions show <id>` 看单条全文。
- **入口**：`ADR-0000`（决策外置政策）、`ADR-9000`（写法模板）、`ADR-9001`（证据纪律）；勘误见 `ERRATA.json`，真实决策在私有 Plan 仓（公开仓无真实件）。

<!-- BEGIN GENERATED: decisions-index -->

## 决策登记表（由各 ADR frontmatter 生成，勿手改）

| 编号 | 标题 | 状态 | 日期 | 取代 |
|---|---|---|---|---|
| ADR-0000 | 决策记录外置到私有仓：公开仓只留模板与格式声明 | accepted | 2026-10-25 | — |
| ADR-9000 | （示例）一条决策的写法：背景 / 决策 / 后果 + 可解析证据 | proposed | 2026-10-25 | — |
| ADR-9001 | （示例）evidence 字段只写可解析的仓库路径或 checkN | proposed | 2026-10-25 | — |

> 真源 = `decisions/ADR-*.md` 的 frontmatter；本表为投影（`nf decisions reindex` 重建）。

<!-- END GENERATED: decisions-index -->

> 投影修复指引：表格区漂移 → 跑 `nf decisions reindex`（不要手改表格）；新增/更正决策走私有仓路由工具，公开仓只收模板（ADR-0000）。
