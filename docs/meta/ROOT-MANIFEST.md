# 根目录清单（SP-01 的本仓口径）

> 生成/校验方式：`python scripts/check_root_manifest.py`（清单本体在脚本的 MANIFEST 常量里，单一真源）。
> 本文件只解释**为什么**这么定，不重复清单内容。

## 1. 为什么不按手册原字面（根 ≤10 条 + 固定白名单）

手册 SP-01 的白名单是 src/docs/tests 型项目模板。本仓是内容契约仓：

- 根目录的 `01_核心协议.md` / `02_联动注册表.md` / `06` / `07` 是协议真源，verify 段 A 的协议一致性判据直接读；
- `STRATEGY.md` 是 `protocol/RECEIPTS.json` 的回执锚（收据链以它为固定件），迁出即断链；
- `verify.sh` 是 42 条 check 的门禁本体，被 AGENTS/CONTRIBUTING/文档大量引用；
- `handovers/` `postmortems/` `results/` 与 `desktop/src/core` 的 Python、Rust、.NET 三面实现互相读路径。

按原字面搬迁会与上述**已存在的更强约束**冲突（手册 §0.6 属中漂移 → 修正执行）。

## 2. 本仓口径（比原字面更严的部分）

每个根条目都必须：**登记 kind + 用途**，且**至少被一处入口面引用**（README/AGENTS/llms/docs/scripts/verify 语料；自身自引用不算）。
新增根条目若不同时改清单，`scripts/check_root_manifest.py` 直接 FAIL。根目录出现 `*.log/*.tmp/*.bak/NUL` 类产物同样 FAIL。

也就是说：判定标准从「条目数少」变成「**个个有据、新增即拦**」——原字面想拦的「根目录变成垃圾场」被更直接地拦住了。

## 3. 已经搬走的（本轮实际缩减）

| 旧路径 | 新路径 | 引用同步 |
|---|---|---|
| `CONTRIBUTING.md` `SECURITY.md` `CODE_OF_CONDUCT.md` `SUPPORT.md` `MAINTAINERS.md` | `.github/` | 协议 normative/LAYERS 条目、5 个单测、ISSUE 模板链接 |
| `GLAMA.md` | `docs/meta/GLAMA.md` | docs/mcp.md（中/英/日） |
| `napcat-qr.png` `napcat-qr-src.png` | `docs/assets/` | 运行期资产（本地运维用，无仓内引用） |
| `ruff.toml` | `pyproject.toml` 的 `[tool.ruff]` | 单测与 .NET 探针引用改向 |

根条目：63 → 53（不含本地运行期目录）。剩下的 53 条全部有登记与引用证据。

## 4. 例外与复查

- **入口例外**：`verify.sh`、`STRATEGY.md`（回执锚）、`AGENTS.md`、`llms.txt`、`01/02/06/07`——理由在清单的 why 字段里。
- **工具约定**：`.editorconfig`/`.gitattributes`/`.gitignore`/`.markdownlint.json`/`.pre-commit-config.yaml`/`pyproject.toml`/`requirements.txt`/`Dockerfile*`/`wrangler.jsonc`/`glama.json`/`REUSE.toml`/`CITATION.cff`——工具只在这些固定位置查找，挪走即失效（手册 SP-02 伪解②）。
- **复查触发**：新增/删除根条目时；`verify.sh` 或回执链结构变更时。
