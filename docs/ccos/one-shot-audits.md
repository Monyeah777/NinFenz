# 一次性审计脚本（历史证据，不删）

状态：**6 个**（截至 2026-11-09）。这些脚本在各自阶段做过一次核对，结论已收口；
它们不再被任何流程调用，但保留为**可复核的证据**——需要复查某一项时，直接跑它。

| 脚本 | 当时核什么 | 现在怎么用 |
|---|---|---|
| `scripts/abi_call_vectors.py` | ABI 调用面的向量化核对 | 需要重算 ABI 向量时跑一次 |
| `scripts/adr_check.py` | ADR 的 falsifier / supersedes / evidence 一致性 | 新增 ADR 后手动核一遍 |
| `scripts/atom_invariants.py` | 原子不变量 A1–A5 与候选 B1–B5 | 改原子目录后复查 |
| `scripts/engine_status.py` | 引擎（Python/Rust）状态与可装载性 | 换环境时体检 |
| `scripts/plugin_promote.py` | 插件晋级的清单/工具链核对 | 引入插件时走一遍 |
| `scripts/gen_third_party_notices.py` | 从 PyPI 官方 API 汇总工具链第三方许可证 | 依赖变动后重新生成 |

## 为什么不删

- 删除文件属高危操作，需作者确认；
- 它们记录了「某个判断怎么做出来的」，删掉就只剩结论没有依据；
- 判据 `desktop/tests/test_script_orphans.py` 把这 5 个**冻结**，且禁止新增孤儿脚本。
