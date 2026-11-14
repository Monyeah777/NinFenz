# 一次性审计脚本（历史证据，不删）

状态：**5 个**（2026-11-13 复核；原 6 个，`gen_third_party_notices` 已获判据入口，2026-11-11 移出）。这些脚本在各自阶段做过一次核对，结论已收口；
它们不再被任何流程调用，但保留为**可复核的证据**——需要复查某一项时，直接跑它。

> **最后更新：2026-11-13（复核）**：五个脚本全部在场、`ORPHANS` 冻结集合与下表**逐项一致**；
> `gen_third_party_notices` 移出理由核实成立（`test_third_party_notices_contract` import 该脚本作判据复用）；
> 常驻判据 `test_script_orphans` **5 例**（禁止新增孤儿 + 冻结列表不得陈旧）。见「§现状对照」。

| 脚本 | 当时核什么 | 现在怎么用 |
|---|---|---|
| `scripts/abi_call_vectors.py` | ABI 调用面的向量化核对 | 需要重算 ABI 向量时跑一次 |
| `scripts/adr_check.py` | ADR 的 falsifier / supersedes / evidence 一致性 | 新增 ADR 后手动核一遍（`--check`） |
| `scripts/atom_invariants.py` | 原子不变量 A1–A5 与候选 B1–B5 | 改原子目录后复查 |
| `scripts/engine_status.py` | 引擎（Python/Rust）状态与可装载性 | 换环境时体检（`--json`/`--check`） |
| `scripts/plugin_promote.py` | 插件晋级的清单/工具链核对 | 引入插件时走一遍 |

## 为什么不删

- 删除文件属高危操作，需作者确认；
- 它们记录了「某个判断怎么做出来的」，删掉就只剩结论没有依据；
- 判据 `desktop/tests/test_script_orphans.py` 把这 5 个**冻结**，且禁止新增孤儿脚本。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 本文声明 | 复核结果（读到本行时请重跑） |
|---|---|---|
| 数量 | 5 个 | **5 个，全部在场**（scripts/ 下逐个 `is_file()`） |
| 冻结集合 | 判据 `ORPHANS` 冻结这 5 个 | **`ORPHANS` 与下表 5 名逐项相等**（多/少即红） |
| 移出件 | `gen_third_party_notices` 已获判据入口 | **成立**：`test_third_party_notices_contract` import 该脚本复用真源 |
| 调用关系 | 「不再被任何流程调用」 | **成立**：不在 verify/CI 的调用链上（仅作证据留存） |
| 常驻判据 | 禁止新增孤儿 + 冻结不得陈旧 | `test_script_orphans` **5 例** |
| 删除纪律 | 高危操作需作者确认 | **不变**（本文件存在即保留依据） |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/adr_check.py --check        # 代表性一次性审计：ADR 一致性（只读）
python scripts/engine_status.py --json     # 引擎状态体检（只读）
python -m pytest desktop/tests/test_script_orphans.py -q   # 5 例（孤儿棘轮）
```

- 引用本文时：「历史证据不删 + 5 个冻结 + 禁止新增孤儿」= 长期口径；脚本名与冻结集合以 `test_script_orphans.ORPHANS` 实读为准。
- 新增脚本若无人引用，会被孤儿棘轮判红——要么给入口，要么评审后进 `ORPHANS` 并在此表登记。
