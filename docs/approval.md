# 内容绑定批准记录（approve）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13

> **复核（2026-11-13）**：机制口径不变（内容绑定、对象一改即失效、不判质量）；补三处现状：① 现存 **1 条**批准记录（`protocol/approvals/protocol__conformance_report.json`，对象 = `protocol/conformance_report.json`，`--verify` 有效）；② 本命令是 **release 冻链条的一环**（`core/release_gate.DEFAULT_FREEZE_CHAIN`：conformance → approve → receipts）；③ `nf approve --json` 可机读。见「§现状对照」。

## 是什么

把「有人批准了」从散文变成**内容绑定、可重放**的记录：`protocol/approvals/*.json`
（`subject` + `subject_digest` + `approved_by` + `approved_at` + `note`）。
**被批准对象一改，记录立刻失效**——批准不是永久通行证。

| 字段 | 含义 |
|---|---|
| `schema` | 记录格式版本（机读分流用） |
| `subject` | 被批准对象（仓库相对路径） |
| `subject_digest` | 对象内容的摘要——**绑定实体**：内容改则摘要不匹配 → 记录失效 |
| `approved_by` | 批准人标识（可追溯，不是权限系统） |
| `approved_at` | 批准时点（UTC/RFC3339 或同款时间串） |
| `note` | 批准说明（变更理由/范围） |

## 怎么用

```bash
python scripts/nf.py approve <路径> --by <批准人> --note "…"   # 写记录
python scripts/nf.py approve --verify                          # 校验（对象改动即 FAIL）
python scripts/nf.py approve --list                            # 列记录（含失效标记）
```

## 边界

- 只判「声明是否在场、是否仍与对象内容绑定」，**不判内容质量**。
- NF 为单人治理：不存在 MCOP 意义上的"拒绝自批准"——批准人字段是**可追溯标识**，不是权限系统。

## 在冻链条中的位置

发布冻结链（真源 `core/release_gate.DEFAULT_FREEZE_CHAIN`，不在本文手抄第二份）：

1. `python scripts/nf.py conformance --write`（27 契约全绿）
2. `python scripts/nf.py approve protocol/conformance_report.json`（**本文的命令**：给一致性报告写内容绑定批准）
3. `python scripts/nf.py receipts --scope protocol --write`（协议层回执）

> `nf release --freeze`（缺省只打印，`--apply` 才执行）按此顺序直调；顺序真源不在本文。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（本文快照） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 批准记录 | 机制刚立（1 条） | **1 条**（`protocol__conformance_report.json`，`--verify` 有效） |
| 记录字段 | 5 字段散文式列举 | **6 键**：`schema/subject/subject_digest/approved_by/approved_at/note` |
| 机读 | 未提 | `nf approve --list --json` / `nf approve --verify --json` |
| 冻链位置 | 未提 | **冻链条第 2 环**（conformance → approve → receipts），`nf release --freeze` 消费 |
| 与 audit 的关系 | 未提 | `nf audit rebind` 迭代记录→ `nf audit verify` 59 件一致（审计面独立于批准面） |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/nf.py approve --list --json   # 现存批准记录（含失效标记）
python scripts/nf.py approve --verify        # 全体有效性（内容绑定未失效）
python scripts/nf.py release --plan          # 看冻链条与本命令在链中的位置
```

- 引用本文时：「内容绑定、改则失效、不判质量」= 长期口径；记录数与有效性以 `--list`/`--verify` 实跑为准。
- 顺序真源：`core/release_gate.DEFAULT_FREEZE_CHAIN`（本文只描述、不复制为权威）。
