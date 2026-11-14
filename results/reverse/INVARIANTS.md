# 不变量（INVARIANTS，§4A R6）

> ⛔ 操作指令：本件是 §4A R6 不变量的人读结果；机读真源 `results/reverse/invariants.json`（`nf-reverse-invariants/1`），判据 `desktop/tests/test_reverse_invariants.py`（**直接断言 + 既有测试存在性 + unobservable 理由**）。`unobservable` 不等于已满足：逐条标 planned_gate。
> 状态：v1（2026-11-14 · G0 §4A R6）· 前置：R1–R5 全部产物
> 路径说明（DEV-05）：计划中的 `tests/invariants/` 映射为 `desktop/tests/test_reverse_invariants.py`（受门禁发现；不覆盖既有 `test_invariants.py`）。

## 1. 逐层不变量

| 编号 | 层 | 不变量 | 方法 | 状态 |
|---|---|---|---|---|
| INV-01 | wiki | 页面必须有 spec_ref/version/provenance/citations | direct-test | tested |
| INV-02 | wiki | 真源变更必导致页面 digest 变化 | unobservable（G1） | unobservable |
| INV-03 | spec | 同 intent+spec 编译逐字节一致 | unobservable（G1） | unobservable |
| INV-04 | spec | 未知 spec/kind 必须拒绝 | unobservable（G1） | unobservable |
| INV-05 | production | 无治理可完成一次交付（PR-01） | existing-test | covered-by-existing |
| INV-06 | production | 治理关闭不改变生产输出（PR-04） | unobservable（G2） | unobservable |
| INV-07 | governance | 非 NF 产物可验证 | existing-test | covered-by-existing |
| INV-08 | governance | 缺锚/等级不足 exit 2（不冒充 T3/T4） | direct-test | tested |
| INV-09 | evidence | 篡改/删叶 bundle 验证失败 exit 1 | direct-test | tested |
| INV-10 | contract | 未知字段 fail-closed（additionalProperties=false） | direct-test | tested |
| INV-11 | contract | Agent 任务有界（slot/spec_refs/acceptance/budget） | direct-test | tested |
| INV-12 | evidence | canonical 确定性 + 域分隔 + 拒 float | direct-test | tested |
| INV-13 | process | 冻结链顺序不可颠倒（未重批准即失效） | existing-test | covered-by-existing |
| INV-14 | process | 生成物/注册表新鲜度（漂移即红） | existing-test | covered-by-existing |

## 2. 覆盖与缺口

- 覆盖：**7 层**；tested 6 / covered-by-existing 4 / **unobservable 4**（INV-02/03/04/06）。
- OPEN：INV-02/03/04 等 G1 编译器（WP-10/11），INV-06 等 G2 双平面开关；不写「已满足」。
- 来源映射：I-01…I-08（R1 隐式契约）、S-01…S-03（R2 状态机）、R3 C-01…C-03、R4-01…09、D-PD-01…03 均已收敛进本表或既有缺口。

## 3. 复核命令

```bash
python -m pytest desktop/tests/test_reverse_invariants.py -q
python -c "import json;d=json.load(open('results/reverse/invariants.json',encoding='utf-8'));print(len(d['invariants']),d['coverage_summary'])"
```

## 4. 交接（G0 收口）

- R6 完成后 §4A 七件套齐全；下一步 G0 DoD 收口审计（§14.3）——`invariants.json` 的 unobservable 项在对应 Gate 前必须转为 tested 或继续挂 OPEN。
