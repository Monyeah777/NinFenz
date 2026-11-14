# 策略适配（WP-42，G4）

> ⛔ 操作指令：本件是 WP-42 策略适配的人读说明；机读真源 `protocol/policy_rules.json`（`nf-policy/1`），判据 `desktop/tests/test_policy_engine_contract.py`，实现 `desktop/src/core/policy_engine.py`。策略外置、默认拒绝、判定可复算；不引 Rego/Cedar 运行时。
> 状态：v1（G4 · 2026-11-15）· 依据：G4 WP-42（OPA/Cedar 策略适配——机制借鉴）

## 规则集（示例）

| 规则 | 优先级 | 效果 | 条件 | 理由 |
|---|---|---|---|---|
| P-001 | 10 | deny | contract_status=retired | 退役契约不得被引用/消费 |
| P-002 | 20 | deny | attachment_mode=require 且 has_evidence=false | require 缺证据即拒 |
| P-003 | 30 | deny | required_level=T3 | 本机适配器缺失，T3 不可达 |
| P-004 | 40 | deny | required_level=T4 | 公共锚未执行，T4 不可达 |
| P-005 | 100 | allow | contract_status=active 且 has_evidence=true | 允许 |

## 求值语义

- **默认拒绝**：无规则命中 → deny（不静默放行）；
- 优先级数值越小越先评估；同优先级 deny 胜 allow；require 规则产生义务清单；
- 缺事实 → 规则不匹配；完全无事实 → `FACTS-MISSING`（不猜）；
- 输出 `nf-policy-decision/1`：allowed/effect/reason/matched/obligations/missing_facts；
- 与 WP-31 联动：T3/T4 deny 与适配器 `verify_plan` 不可达一致（判据交叉断言）。

## 复核命令

```bash
python -c "import sys;sys.path.insert(0,'desktop/src');from core import policy_engine as p;print(p.evaluate({'required_level':'T1','contract_status':'active','has_evidence':True}))"
python -m pytest desktop/tests/test_policy_engine_contract.py -q
```

## 边界

只借「策略即代码/判定可复算」机制；**不声称 OPA/Cedar 兼容**，不替代人类复核/外部审计。
