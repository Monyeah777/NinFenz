# G4 DoD 收口审计（G4 DOD · QG4）

> ⛔ 操作指令：本件是 G4（AI 信任 + 生态导出）收口审计人读结果；机读真源 `results/g4_dod.json`（`nf-g4-dod/1`），判据 `desktop/tests/test_g4_dod.py`。**pass-with-open-items ≠ 零缺陷**：外部 OPEN 与 G4-DEBT 显式挂账；P0 阻断=0 才允许进 G5。
> 状态：v1（2026-11-15 · G4 收口）· 依据：§14.3 / §11.2 G4 / §13A QG4
> 结论：**pass-with-open-items（P0 阻断 = 0）** → 下一 Gate：G5。

## 1. §14.3 DoD（8 条）

| 编号 | 判据 | 状态 | 证据 |
|---|---|---|---|
| DOD-01 | AI 面正/反测试 | pass | 四套判据 + verify.sh |
| DOD-02 | 旧基线能红、新基线全绿（变异自证） | pass | 证据链/AIBOM/策略/标识变异用例 |
| DOD-03 | 冻结链按序执行并解释 diff | pass | receipt_chain/conformance/approvals/RECEIPTS |
| DOD-04 | .NET/Rust 面同步（如涉及） | **n/a** | G4 未改引擎；dotnet BLOCKED |
| DOD-05 | 文档/ADR/keyword 更新 | pass | 4 篇 G4 文档 + ADR_MAP |
| DOD-06 | SELF_AUDIT P0=0 | pass | `results/trust/SELF_AUDIT.json` |
| DOD-07 | 无未登记 OPEN/TODO | pass-with-open | OPEN-EXTERNAL / OPEN-TOOLS |
| DOD-08 | 交接报告完整 | pass | BASELINE + RESULTS + 台账 |

## 2. §11.2 G4 交付物（G4-ART：WP-40…44）

| WP | 交付 | 状态 |
|---|---|---|
| WP-40 | AI 证据链（模型卡/血缘/人类复核三件绑定） | ✅ |
| WP-41 | AIBOM/Model Card 导出（CycloneDX + SPDX） | ✅ |
| WP-42 | 策略适配（nf-policy/1，默认拒绝、判定可复算） | ✅ |
| WP-43 | AIGC/标注证据（机器可读标识 + 绑定闭合） | ✅ |
| WP-44 | 判据门禁 check52（52 条 · PASS=95） | ✅ |

## 3. QG4 与 AI 面指标

| 编号 | 判据 | 结果 |
|---|---|---|
| QG4-01 | AI 信任：三件绑定、状态 APPROVED | pass |
| QG4-02 | 生态导出：AIBOM 闭合/无秘密/确定性 | pass |
| QG4-03 | 策略诚实：默认拒绝、T4 缺适配器即拒 | pass |
| QG4-04 | AIGC 标识：闭合、未标注不默认 human | pass |
| L4-01 | eval digest 实时绑定（协议变即失效） | pass |
| L4-02 | 门禁汇总 check52 绿（PASS=95） | pass |

## 4. OPEN（不阻断 G4）

- **OPEN-EXTERNAL**：公共日志提交/外部 witness/第三方合规审核未执行。
- **OPEN-TOOLS**：cosign 不在场；TSA/透明日志请求未执行 → **T2+ 不可达**。
- **G4-DEBT-01**：真实外部模型 adapter 未接（local-template 仅 parity 桩）。
- **G4-DEBT-02**：AIBOM 为最小闭合集，未追全量规范字段。
- **G4-DEBT-03**：策略引擎非 OPA/Cedar 运行时，跨语言策略互操作未做。

## 5. 复核命令

```bash
bash verify.sh --checks-only          # 期望 PASS=95 WARN=2 FAIL=0（含 check52）
python -m pytest desktop/tests/test_g4_dod.py -q
python -c "import json;d=json.load(open('results/g4_dod.json',encoding='utf-8'));print(d['verdict'],d['p0_blockers'])"
```
