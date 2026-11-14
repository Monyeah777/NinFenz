# G3 DoD 收口审计（G3 DOD · QG3）

> ⛔ 操作指令：本件是 G3（治理平面，可选）收口审计人读结果；机读真源 `results/g3_dod.json`（`nf-g3-dod/1`），判据 `desktop/tests/test_g3_dod.py`。**pass-with-open-items ≠ 零缺陷**：外部 OPEN 与 G3-DEBT 显式挂账；P0 阻断=0 才允许进 G4。
> 状态：v1（2026-11-15 · G3 收口）· 依据：§14.3 / §11.2 G3 / §13A QG3
> 结论：**pass-with-open-items（P0 阻断 = 0）** → 下一 Gate：G4。

## 1. §14.3 DoD（8 条）

| 编号 | 判据 | 状态 | 证据 |
|---|---|---|---|
| DOD-01 | 治理面正/反测试 | pass | 四套判据 + verify.sh |
| DOD-02 | 旧基线能红、新基线全绿（变异自证） | pass | 契约/适配器/附件/报告变异用例 |
| DOD-03 | 冻结链按序执行并解释 diff | pass | receipt_chain/conformance/approvals/RECEIPTS |
| DOD-04 | .NET/Rust 面同步（如涉及） | **n/a** | G3 未改引擎；dotnet BLOCKED |
| DOD-05 | 文档/ADR/keyword 更新 | pass | 4 篇 G3 文档 + ADR_MAP |
| DOD-06 | SELF_AUDIT P0=0 | pass | `results/trust/SELF_AUDIT.json` |
| DOD-07 | 无未登记 OPEN/TODO | pass-with-open | OPEN-EXTERNAL / OPEN-TOOLS |
| DOD-08 | 交接报告完整 | pass | BASELINE + RESULTS + 台账 |

## 2. §11.2 G3 交付物（G3-ART：WP-30…33）

| WP | 交付 | 状态 |
|---|---|---|
| WP-30 | 契约生命周期/义务（四态 + 引用策略） | ✅ |
| WP-31 | 治理 verify 适配（DSSE/Sigstore/RFC3161/透明日志 + 降级） | ✅ |
| WP-32 | Attachment 模式（none/observe/require + 独立性） | ✅ |
| WP-33 | 治理报告/审计包 + check51（51 条 · PASS=93） | ✅ |

## 3. QG3 与治理指标

| 编号 | 判据 | 结果 |
|---|---|---|
| QG3-01 | 非 NF 产物可验证（只依赖 bundle/策略/锚） | pass |
| QG3-02 | 附件模式语义（observe 不阻塞 / require 缺证据即拒） | pass |
| QG3-03 | 不阻塞生产（三模式装配记录 digest 逐字节一致） | pass |
| L3-01 | 等级诚实：T1 可达、T2+ missing/exit 2（不冒充 T3/T4） | pass |
| L3-02 | 审计包 7/7 + OPEN 有 owner + committed==实时重算 | pass |
| L3-03 | 契约四态义务可核 | pass |

## 4. OPEN（不阻断 G3）

- **OPEN-EXTERNAL**：公共日志提交/外部 witness/第三方合规审核未执行。
- **OPEN-TOOLS**：cosign 不在场；TSA/透明日志请求未执行 → **T2+ 不可达**（报告如实 missing）。
- **G3-DEBT-01**：非 NF 产物验证只有离线样本，真实第三方产物待外部。
- **G3-DEBT-02**：observe 模式缺长期观测数据。

## 5. 复核命令

```bash
bash verify.sh --checks-only          # 期望 PASS=93 WARN=2 FAIL=0（含 check51）
python -m pytest desktop/tests/test_g3_dod.py -q
python -c "import json;d=json.load(open('results/g3_dod.json',encoding='utf-8'));print(d['verdict'],d['p0_blockers'])"
```
