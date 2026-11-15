# NF APP（移动 / 桌面控制面 + 共享核心）

> 本目录是 `NF-APP-Final-方案-2026-11-15.md` 的实施面。**人的控制面**：Android（NF Mobile）/ 桌面（NF Studio）/ 平板；**CCOS = 执行面**；**TUI/CLI = 终端与检验**。
> 性质：结果/状态件入口。计划原文是作者本地输入，不入仓（见 `STRATEGY.md` §四）。

## 布局

```
app/
  schema/      # 13 个共享格式 + limits/error_codes（A0 单一真源）
  docs/        # CONTRACT.md（契约冻结）/ CLI.md（op 面）/ ARB 架构 / ADR / THREAT_MODEL / QA / DoD
  core/        # Rust 共享核心 nf-app-core（参考实现；CLI + C ABI JSON；cargo test）
  cli/         # Python 控制面 nf_app（用户流：import/map/project/author/assemble/validate/export/
               #   share/pack update/ccos/selftest；内部调 core）
  android/     # Kotlin + Compose 移动端（共享模型经 core FFI）
  desktop/     # Compose Multiplatform NF Studio（完整作者/Graph/DSL/Pack/评审/打印/TUI 集成）
  tests/       # pytest：schema/契约/安全负例/golden/E2E 首闭环
  fixtures/    # schema 正反样例 / sample-pack / golden
  gates/       # QA0–QA6 + S0–S15 自审计（机器门禁）
  scripts/     # Android/Desktop 构建、Windows MSIX、macOS 公证、发布清单
  results/     # APP 侧证据（GATES.json / SELF_AUDIT.json / TOOLCHAIN.md）
results/app/   # 基线 / 结果 / DoD（与仓库 results/ 同级登记）
```

## 复跑（本机）

```bash
# 契约层
python -m pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py -q
# 核心（Rust）
cd app/core && cargo test
# 控制面 + 首闭环
python -m pytest app/tests -q
# APP 门禁（QA0–QA6 + S0–S15 聚合）
python app/gates/run_gates.py
# TUI（既有，不重写）
python tui/nf.py --selftest
```

## 边界（不做什么）

- 不复制仓库内容真源（`01`–`07`/`03`/`04`/`05`/`protocol`）；只按 ID+digest 引用。
- 不做通用 Markdown 编辑器/代码 IDE/云同步/端上 LLM/长驻 MCP。
- 密钥只在 CCOS；APP 不直连 API；无遥测、无账号。
- 新增能力不得占用仓库 `verify.sh` 的 check1–57（只增 check58+）。

## 状态

见 `results/app/BASELINE.md`（基线）、`results/app/RESULTS.md`（结果导航）、`results/app/FINAL_DOD.md`（收口）、`app/results/SELF_AUDIT.json`（自审计）。
