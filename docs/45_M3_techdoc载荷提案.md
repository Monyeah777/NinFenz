# 45 A1 · techdoc 链载荷补充（proposed → 已确认 · 2026-09-09）

> ⛔ 操作指令：以下提案已于 2026-09-09 经作者确认并写入 registry（declared 30/30）；改字段须走 schema/registry 纪律。
> 最后更新：2026-11-13

> **状态：提案已确认并落库（不变）；registry/模块面现状已复核**——5 条 techdoc 事件仍为 `payload_status: declared` 且字段与提案一致；事件登记面已从「declared 30/30」扩到 **事件 443 条 / declared 438 条**（2026-11-13 实读）。**开放项现状**：`intent_received` 字段名已定（`intent_id/mode/text` 落库）；`sections` / `changes` 的**结构粒度**与模块 `io_types` 的 `untyped` 收窄**仍在待办**（M90 的 `DocState`/`doc_delta` 现仍 `untyped`）。见文末「现状对照」。

## 现状（已收口）

5 条 techdoc 事件原无显式 `payload:{…}` 结构；按本提案字段经作者确认后全部转 `payload_status: declared`（每字段 `untyped`，类型待正文补全后收窄）。

## 提案（每条均带依据与开放项）

| 事件 | 来源 | 建议 payload 字段 | 开放项 |
|---|---|---|---|
| doc_structure_ready（M90 发布） | M90 产出 DocState 骨架 | `doc_id, title, version, sections[]` | sections 结构粒度待 M90 补全 |
| doc_delta_committed（M90 发布） | M98 订阅后 `changes=diff(prev,cur)` | `doc_id, prev_ver, new_ver, changes[]` | changes 条目类型待定 |
| intent_received（P90 装载输入闭环） | C3 补发布方时建立 | `intent_id, mode, text` | 字段名待作者定 |
| term_synced（M97 发布） | outputs term_delta/term_status | `delta[], status[], count` | 结构待 M97 补全 |
| term_conflict_detected（M97 发布） | dup definition → status=conflict | `term, definitions[], status` | 冲突形态待定 |

## 落库纪律

- 确认已落库（note 记 `45_M3 techdoc 载荷提案经作者确认`）。
- 后续：建议在 M90/M97/M98 事件契约补显式 payload 以收窄 untyped 类型——**2026-11-13 复核仍未完成**（见现状对照末两行），保持待办不假装收口。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（本文快照） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 5 条事件 payload | 提案 → 作者确认 → declared | **仍 declared**（`protocol/event_registry.json` 在册；字段与提案一致） |
| 事件登记规模 | declared **30/30** | **事件 443 / declared 438**（2026-11-13 实读，非本文件维护） |
| `intent_received` 开放项 | 「字段名待作者定」 | **已定并落库**：`intent_id / mode / text` |
| `sections` / `changes` 结构粒度 | 待 M90/M97 补全 | **仍待办**（payload 字段在册，条目内部结构未收窄） |
| 模块 `io_types` 收窄 | 建议补显式 payload | **仍 `untyped`**：M90 `DocState` / `doc_delta` = untyped（`nf module types` 可复核） |
| 事件背书 | 未涉 | `nf events` 通过（每个被订阅事件都有发布方） |

> 本表只作「当时 → 现行」导航，不替代实跑：事件面以 registry 与 `nf events` 为准。

## 复现与引用口径

```bash
python scripts/nf.py events                     # 全仓事件背书（订阅必有发布方）
python scripts/nf.py module types --json        # 模块 io_types 面（含 untyped 清单；--backlog 看积压）
```

- 事件字段真源：`protocol/event_registry.json`（5 条 techdoc 事件的 `fields` 即提案落地形态）。
- 引用本文时：「declared 30/30」= **2026-09-09 快照**；现行事件数/declared 数与 io_types 收窄状态以实跑为准。
