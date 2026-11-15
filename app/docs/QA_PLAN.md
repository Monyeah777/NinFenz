# NF APP 质量与测试计划（QA0–QA6）

> ⛔ 操作指令：本件是 APP 门禁口径（计划 §13）。所有结论必须由 `python app/gates/run_gates.py` 现场复跑产生；`app/gates/gates.json` 是登记表，`app/results/GATES.json` 是证据。未跑不写成 pass。
> 状态：v1（2026-11-15）。

## 1. 门禁（与 gates.json 一一对应）

| 门 | 内容 | 机器判据 | 当前状态 |
|---|---|---|---|
| QA0 | 架构/数据模型/FFI 契约/威胁模型/ADR 评审 | schema 15 件可解析；CONTRACT/CLI/ARCHITECTURE/THREAT_MODEL 在位；ADR ≥10；正反夹具；schema 测试全绿 | 见 GATES |
| QA1 | Pack/导入/映射/搜索；负例 | cargo test；E2E 导入/Pack 用例；安全负例 + CLI 契约 | 见 GATES |
| QA2 | 协议/管线/装配/校验/导出；golden | golden + oracle 对账；首闭环 E2E | 见 GATES |
| QA3 | 分享/回填/Pack 更新/冲突/回滚；负例 | 更新/冲突/回滚用例；分享/回填用例（未落地则 OPEN） | 见 GATES |
| QA4 | 桌面/TUI/CCOS 交接；跨端一致 | TUI selftest；CCOS 用例；Android/Desktop 构建（工具链缺失记 OPEN） | 见 GATES |
| QA5 | 安全/性能/无障碍/16KB/设备矩阵 | 安全负例；设备矩阵登记；性能预算登记 | 见 GATES |
| QA6 | 发布/签名/公证/数据安全/许可；自审计 P0=0 | 脚本/文档在位；签名证据 OPEN；SELF_AUDIT p0=0 | 见 GATES |

## 2. 测试矩阵（§13.1）

| 面 | 用例落点 | 状态 |
|---|---|---|
| 单元（pack/import/protocol/graph/compile/assemble/validate/pack update） | `app/core/src/**/tests` + `cargo test` | 进行中（rust-core） |
| Python 控制面/契约 | `app/tests/test_cli_contract.py` | 进行中（python-plane） |
| 安全负例 | `app/tests/test_security_negative.py` | 进行中 |
| Golden（Rust ↔ Python） | `app/fixtures/golden/` + `app/tests/test_golden.py` + `test_oracle_parity.py` | 进行中 |
| 首闭环 E2E | `app/tests/test_e2e_first_loop.py` | 进行中 |
| Robolectric/Compose UI/Instrumentation/16KB/设备矩阵 | `app/android/`（工具链缺失） | OPEN-TOOLCHAIN |
| 无障碍/本地化（TalkBack/RTL/字体缩放/pseudo-locale） | Android UI 用例 | OPEN-TOOLCHAIN |
| 性能（启动/装配/内存/包体） | `app/docs/PERF_BUDGET.md` | OPEN（无运行时） |

## 3. 已知盲区闭环（§13.3）

P0 盲区：FFI 契约（→ CLI.md §5 + 契约测试）、进程死亡/状态恢复（→ OPEN，A6 后补）、威胁模型/组件/深链（→ THREAT_MODEL + OPEN-EXTERNAL）、Room 迁移/回滚（Android 未建 → OPEN-TOOLCHAIN）、设备/16KB/ABI 矩阵（→ OPEN-TOOLCHAIN）、无遥测崩溃诊断（→ 设计为仅本地诊断，实现待补）、许可/Play 数据安全（→ LEGAL + OPEN-EXTERNAL）、解析负例（→ test_security_negative）。

P1 盲区：图编辑器无障碍、分享/深链/FileProvider、备份/恢复、缓存配额、性能预算、发布回滚、运营/诊断、无障碍/本地化测试、用户文档、LLM provider/注入、导出保真、迁移工具——逐项在 `app/results/SELF_AUDIT.json.open_items` 登记 owner + next，不静默消失。

## 4. 复跑

```bash
python app/gates/run_gates.py            # 全量门禁（QA0–QA6 + S0–S15）
python app/gates/run_gates.py --only QA2 # 单门
python -m pytest app/tests -q            # 控制面/契约/安全/golden/E2E
cd app/core && cargo test                # 核心单测
```
