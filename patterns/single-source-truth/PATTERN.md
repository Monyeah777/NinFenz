---
id: single-source-truth
name: 真源 + 投影，禁止双写
status: active
scope:
  - 协议层
  - 资产层
applies_to:
  - library/INDEX.md
  - library/ALIAS.md
  - patterns/INDEX.md
  - protocol/conformance_report.json
  - protocol/RECEIPTS.json
rules:
  - 每份数据只有一个真源（frontmatter / registry.json / 契约声明），其余形态一律由脚本重生成
  - 生成区必须用显式标记包裹（BEGIN/END GENERATED），人工区不受影响
  - 门禁断言「在盘投影 == 实时重算」——不一致即 FAIL，不允许手工修表
evidence:
  - check34
  - check35
  - desktop/src/core/library.py
---

## 为什么

双写必然漂移：人改了一处、忘了另一处，两份"真相"开始各说各话。NF 的 I5（真相唯一）在各层
落地的方式就是——**真源 + 投影 + 重算断言**。

## 怎么用

```bash
python scripts/nf.py library reindex      # 真源(frontmatter) → INDEX/ALIAS 投影
python scripts/nf.py patterns reindex     # 真源(PATTERN.md) → patterns/INDEX 投影
python scripts/nf.py conformance --write  # 真源(契约) → 报告工件
```

## 反例

直接手改 `library/INDEX.md` 的生成区、或手改 `patterns/INDEX.md` 的表格——下一次重算即被覆盖，
且门禁会先报"投影不一致"。


---

## 现状对照（2026-11-14 · 以投影件/判据实读为准）

| 投影件 | 真源 | 生成方式 | 复核方式 |
|---|---|---|---|
| `library/INDEX.md` | 各馆藏 `frontmatter` | `nf library reindex`（**2 个**生成区：mirror + index） | `nf library verify` |
| `library/ALIAS.md` | 同上（大小写转译表） | 同上（**整页**投影，无生成标记） | `nf library verify` |
| `patterns/INDEX.md` | 各 `PATTERN.md` frontmatter | `nf patterns reindex`（**1 个**生成区 + 实时计数） | `nf patterns verify` |
| `protocol/conformance_report.json` | 契约声明 | `nf conformance --write` | `nf approve --verify`（内容绑定批准） |
| `protocol/RECEIPTS.json` | 馆藏回执链 | `nf receipts --write` | `nf receipts --verify`/`nf library receipts` |

- **两类工件两种锁**：Markdown 投影靠 `BEGIN/END GENERATED` 标记 + 「在盘 == 实时重算」；JSON 工件靠**内容摘要绑定**（批准 / 回执）——它们没有标记，别手改。
- **判据**：`check34`（馆藏投影）· `check35`（深化面汇总，含投影类子扫描）。
- 本文不钉条目数/摘要值：那是运行时事实，**以命令实读为准**。

## 复现与引用口径

```bash
python scripts/nf.py library verify       # 馆藏 frontmatter + INDEX/ALIAS 投影一致
python scripts/nf.py patterns verify      # patterns/INDEX 投影一致
python scripts/nf.py conformance          # 报告工件新鲜度（只读）
```

- 手改生成区/工件 → 下一次重算即覆盖，且判据先报「投影不一致」；正确做法是**改真源再重算**。
