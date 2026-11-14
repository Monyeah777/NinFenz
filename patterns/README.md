# NF Patterns · 实践包品类
> ⛔ 操作指令：本文含可直接执行的命令与格式判定，阅读即执行。
> 最后更新：2026-11-14（复核）
> **复核（2026-11-14）**：格式、入库铁律与命令面**复核不变**；补「§现状对照」「§复现与引用口径」与「§新增/审阅一条 pattern」，把「几个包、几个必填键、词表几值、投影怎么重建」写清。

## 现状对照（2026-11-14 · 以 `nf patterns` 与 `core/patterns` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 实践包 | **7**（见 `INDEX.md` 生成区） | `python scripts/nf.py patterns ls` |
| 状态 | 全部 **active**（词表 **2 值**：`active` / `deprecated`） | 各包 frontmatter |
| 必填键 | **6 个**：`id` / `name` / `status` / `scope` / `applies_to` / `rules` | `core/patterns.py` 的 `REQUIRED` |
| 可证性 | `applies_to` 必须匹配真实文件；`evidence` 至少 **1** 条且可解析（真实件或 `checkN`） | `nf patterns verify` |
| 投影 | `INDEX.md` **整页生成**（`reindex` 重建，含「现状对照」计数）；幂等 | `reindex`（无变化即输出「无变化」） |
| 机检 | `nf patterns verify`：格式 + 适用面/证据可证 + INDEX 投影一致 | 命令实跑 |

> 本表只作「当时 → 现行」导航；数字以 `patterns ls` 与 `INDEX.md` 生成区为准。

## 新增/审阅一条 pattern（四步）

1. 建目录 `patterns/<id>/PATTERN.md`（**id 与目录同名**），frontmatter 填 6 必填键 + `evidence`；
2. `applies_to` 写**仓库内真实存在**的路径或通配；`evidence` 写真实件或 `checkN`（指向空气会被判 FAIL）；
3. `python scripts/nf.py patterns reindex` 重建 `INDEX.md`；
4. `python scripts/nf.py patterns verify` 必须绿；退役用 `status: deprecated`（**不要直接删包**，删了会丢掉历史口径）。

## 复现与引用口径

```bash
python scripts/nf.py patterns ls                 # 7 条（真源：各 PATTERN.md frontmatter）
python scripts/nf.py patterns verify             # 格式 + 可证性 + INDEX 投影一致
python scripts/nf.py patterns reindex            # 重建 INDEX（幂等）
```

- **INDEX.md 不要手改**（整页生成物，含计数）；要改内容请改对应 `PATTERN.md`。
- 引用本页时：「入库铁律 = 仓库内实证」是长期口径——没有 `applies_to`/`evidence` 的 pattern 不许入库。

## 这是什么

`patterns/` 是 NF 的**实践包**货架（与 `community/` 的内容域包并列）：每条 pattern 是一份
**可发布、可消费、可移植**的最佳实践——它不说"这个世界的魔法怎么运作"，而说
"这类文件应当怎么写"。

**入库铁律**：每条 pattern 必须有**仓库内实证**——`applies_to` 指向的路径/通配必须真的匹配到文件，
`evidence` 必须指向真实件或 `checkN`。指向空气的 pattern 会被 `nf patterns verify` 判 FAIL。

## 目录结构

```
patterns/
  README.md              # 本文（品类说明）
  INDEX.md               # 登记表（投影，由 frontmatter 重生成）
  <name>/PATTERN.md      # 一个 pattern 包（真源 = 头部 frontmatter）
```

## PATTERN.md 格式

```markdown
---
id: <目录同名>
name: <人读名>
status: active|deprecated
scope: [<这条 pattern 管哪一层，如 协议层 / 代码层>]
applies_to:            # 适用面（必须是仓库内真实存在的路径或通配）
  - desktop/src/core/*.py
rules:                 # 可执行规则（每条一句话、可检查）
  - ...
evidence:              # 可证性：真实件路径 或 checkN
  - check27
  - desktop/src/core/purity_scan.py
---

正文：为什么、怎么用、反例。
```

## 怎么用

```bash
python scripts/nf.py patterns ls                 # 列全部 pattern
python scripts/nf.py patterns show <id>          # 看单条（frontmatter + 正文）
python scripts/nf.py patterns for <文件路径>      # 反向查：这个文件适用哪些 pattern
python scripts/nf.py patterns verify             # 机检（格式 + 可证性）
python scripts/nf.py patterns reindex            # 重建 INDEX 投影
```
