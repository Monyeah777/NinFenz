# 实践包（patterns）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：货架定位 / 入库铁律 / 用法**复核不变**；补可核现状（`nf patterns` 实读）：
> **7 条 pattern 全部 active**（dependency-direction / error-message-guidance / fail-closed-verification /
> predicate-single-source / single-source-truth / verifier-must-run / worktree-vs-index）· frontmatter 必填 **6 键**
> （id/name/status/scope/applies_to/rules）· status 词表 2 值（active / deprecated）· 投影件 `patterns/INDEX.md`
> 与真源逐字一致（`patterns verify` 绿）。见「§现状对照」。

## 是什么

`patterns/` 是与 `community/`（内容域包）并列的**实践包货架**：每条 pattern 是可发布、可消费、
可移植的最佳实践。真源 = `patterns/<name>/PATTERN.md` 的 frontmatter，`patterns/INDEX.md` 是投影。

## 入库铁律（可证性）

`applies_to` 指向的路径/通配**必须匹配到仓库内真实文件**；`evidence` 必须指向真实件或 `checkN`
——指向空气的 pattern 会被 `nf patterns verify` 判 FAIL。**不为齐全而造 pattern。**

## 怎么用

```bash
python scripts/nf.py patterns ls
python scripts/nf.py patterns show single-source-truth
python scripts/nf.py patterns for library/INDEX.md     # 反向查：这个文件适用哪些 pattern
python scripts/nf.py patterns verify
python scripts/nf.py patterns reindex                  # 重建 INDEX 投影
```

## 现状对照（2026-11-13 · 以 `nf patterns verify` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| pattern 数 | **7**（全部 active） | `nf patterns ls` |
| 真源 | `patterns/<name>/PATTERN.md` frontmatter | `core/patterns.REQUIRED` |
| 必填键 | **6**：id / name / status / scope / applies_to / rules | 同上 |
| status 词表 | **2**：active / deprecated | `core/patterns.STATUSES` |
| 投影 | `patterns/INDEX.md`（`reindex` 重建，逐字对账） | `nf patterns verify` |
| MCP 面 | 工具 `pattern_read` + 资源 `nf://repo/pattern/{id}` | 能力表 |

> 本表只作「当时 → 现行」导航；条数以 `nf patterns ls` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py patterns verify      # 三项：格式合规 / 适用面与证据可证 / INDEX 投影一致
python scripts/nf.py patterns reindex     # 重建投影（手改 INDEX 属违规）
python scripts/nf.py patterns for library/INDEX.md   # 反向查适用面
```

- 引用本文时：「不为齐全而造 pattern；指向空气即 FAIL」= 长期口径。
- `patterns/INDEX.md` 是**生成物**：只许 `reindex` 重建，不手改（同 `library/INDEX.md` 纪律）。

MCP 侧：`pattern_read`（工具）/ `nf://repo/pattern/{id}`（资源）。
