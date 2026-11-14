# G2 DoD 收口审计（G2 DOD · QG2）

> ⛔ 操作指令：本件是 G2（生产/装配黄金路径）收口审计人读结果；机读真源 `results/g2_dod.json`（`nf-g2-dod/1`），判据 `desktop/tests/test_g2_dod.py`。**pass-with-open-items ≠ 零缺陷**：外部 OPEN 与 G2-DEBT 显式挂账；P0 阻断=0 才允许进 G3。
> 状态：v1（2026-11-15 · G2 收口）· 依据：§14.3 / §11.2 G2 / §13A QG2 / §13A L4·L7
> 结论：**pass-with-open-items（P0 阻断 = 0）** → 下一 Gate：G3。

## 1. §14.3 DoD（8 条）

| 编号 | 判据 | 状态 | 证据 |
|---|---|---|---|
| DOD-01 | PR-01…08 正/反测试 | pass | 五套判据 + verify.sh |
| DOD-02 | 旧基线能红、新基线全绿（变异自证） | pass | adapter/assembly/output/delivery 变异用例 |
| DOD-03 | 冻结链按序执行并解释 diff | pass | receipt_chain/conformance/approvals/RECEIPTS |
| DOD-04 | .NET/Rust 面同步（如涉及） | **n/a** | G2 未改引擎；dotnet BLOCKED |
| DOD-05 | 文档/ADR/keyword 更新 | pass | 4 篇 G2 文档 + 威胁模型 |
| DOD-06 | SELF_AUDIT P0=0 | pass | `results/trust/SELF_AUDIT.json` |
| DOD-07 | 无未登记 OPEN/TODO | pass-with-open | OPEN-PRODUCT/OPEN-EXTERNAL |
| DOD-08 | 交接报告完整 | pass | BASELINE + RESULTS + 台账 |

## 2. §11.2 G2 交付物（G2-ART：WP-20…24）

| WP | 交付 | 状态 |
|---|---|---|
| WP-20 | Agent Adapter（有界 task→输出契约；mock/local-template parity） | ✅ |
| WP-21 | Assembly Runtime（P00 E2E；双层记录；失败即停） | ✅ |
| WP-22 | Output/Validation（contract+form；失败拒收） | ✅ |
| WP-23 | Delivery（manifest/可选 sidecar/路径安全/篡改检出） | ✅ |
| WP-24 | 生产指标 + check50（50 条 · PASS=91） | ✅ |

## 3. QG2 与 L4/L7 指标

| 编号 | 判据 | 结果 |
|---|---|---|
| QG2-01 | core-only E2E 交付（无治理平面依赖） | pass |
| QG2-02 | 2 adapter 同 spec 可移植（parity=true） | pass |
| QG2-03 | 输出校验（contract/form + 失败拒收） | pass |
| QG2-04 | 生产指标可复算，no-data 不冒充 | pass |
| L7-01 | 交付包完整率 100% + 篡改可检出 | pass |
| L7-02 | 路径违规=0、sidecar 阻塞=0 | pass |
| L4-01 | parity / schema 通过 / 编造引用=0 | pass |
| L4-02 | Adapter 超时/取消/重试路径 | pass-with-open（G2-DEBT-01） |

## 4. OPEN（不阻断 G2）

- **OPEN-PRODUCT**：外部真实生产数据/试点/访谈未执行（M-05/M-06 为 no-data）。
- **OPEN-EXTERNAL**：公共日志提交/外部 witness/离线解包/重复交付属外部操作。
- **G2-DEBT-01**：Adapter 超时分支已实现但未用慢夹具实跑触发。
- **G2-DEBT-02**：真实外部模型 adapter 未接（local-template 仅 parity 桩）。

## 5. 复核命令

```bash
bash verify.sh --checks-only          # 期望 PASS=91 WARN=2 FAIL=0（含 check50）
python -m pytest desktop/tests/test_g2_dod.py -q
python -c "import json;d=json.load(open('results/g2_dod.json',encoding='utf-8'));print(d['verdict'],d['p0_blockers'])"
```
