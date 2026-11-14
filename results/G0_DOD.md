# G0 DoD 收口审计（G0 DOD）

> ⛔ 操作指令：本件是 G0 收口审计人读结果；机读真源 `results/g0_dod.json`（`nf-g0-dod/1`），判据 `desktop/tests/test_g0_dod.py`。**pass-with-open-items ≠ 零缺陷**：外部 OPEN 与 BLOCKED 工具显式挂账；P0 阻断=0 才允许进 G1。
> 状态：v1（2026-11-14 · G0 收口）· 依据：§14.3 / §11.2 / §13A QG0 / §4A DoD / §12.1–12.2
> 结论：**pass-with-open-items（P0 阻断 = 0）** → 下一 Gate：G1。

## 1. §14.3 DoD（8 条）

| 编号 | 判据 | 状态 | 证据 |
|---|---|---|---|
| DOD-01 | FR/NFR 有正/反测试 | pass | `results/BASELINE.md`、`verify.sh`、不变量执行器 |
| DOD-02 | 旧基线能红、新基线全绿（变异/负例自证） | pass | 各 WP 变异自证测试 + BASELINE |
| DOD-03 | 冻结链按序执行并解释 diff | pass | receipt_chain / conformance / approvals / RECEIPTS |
| DOD-04 | .NET/Rust 面同步（如涉及） | **n/a** | 本 Gate 未改引擎；dotnet BLOCKED 如实记 |
| DOD-05 | 文档/ADR/keyword 索引更新 | pass | ADR_MAP + registry + docs/layers |
| DOD-06 | SELF_AUDIT.json P0=0 | pass | `results/trust/SELF_AUDIT.json`（stop.p0=0） |
| DOD-07 | 无未登记 OPEN/TODO 关键路径 | pass-with-open | 保证案例/RAID/产品登记 |
| DOD-08 | 交接报告完整 | pass | BASELINE + RESULTS |

## 2. Gate 级判据

| 编号 | 判据 | 状态 | 证据/缺口 |
|---|---|---|---|
| G0-ART | WP-00…04 + WP-0A…0H 全落地 | pass | BASELINE/INVENTORY/THREAT/PRIVACY/OPS/AI/LEGAL/A11Y/I18N/ASSURANCE/CQ/PRODUCT |
| G0-BLIND | P0 BL-01…05 全关；P1 BL-06/07/08/09/10/12 达 closure 条件 | pass-with-open | OPEN-PRODUCT / OPEN-EXTERNAL 未关（外部操作） |
| G0-4A | §4A 七件齐 + ≥3 不一致 + ≥1 同行影响设计 + 不变量有测试/UNOBSERVABLE + 未解决进 OPEN | pass | R0–R6 全部产物 |
| G0-QG0 | schema/边界/威胁/不变量评审，无默认放行 | pass | independence/threat_vectors/INVARIANTS/verify |
| G0-RULES | §12.1 必须 7 条 + §12.2 禁止 8 条有证据 | pass-with-open | cosign/gitleaks BLOCKED |
| G0-TOOLS | CQ0 工具矩阵固定版本（13 件） | pass-with-open | dotnet/cosign/gitleaks BLOCKED |
| G0-REVIEW | 审查模板/AI provenance 就绪；CQ2 人工审查未执行 | pass-with-open | REVIEW_CHECKLIST；CQ2-NOT-RUN |

## 3. OPEN（不阻断 G0，但不得静默）

- **OPEN-PRODUCT**：访谈/试点/LOI 外部操作未执行（假设全 unverified）。
- **OPEN-EXTERNAL**：公共日志提交/外部 witness/语言服务/第三方合规审核属外部操作。
- **UNOBS-4**：INV-02/03/04（G1 编译器）、INV-06（G2 双平面开关）。
- **BLOCKED-TOOLS**：dotnet/cosign/gitleaks 本机不可用。
- **CQ2-NOT-RUN**：人工高危审查模板就绪、执行属后续 Gate。

## 4. 结论与下一步

- **G0：pass-with-open-items，P0 阻断=0** → 允许进入 **G1**。
- G1 首批：WP-10 Wiki 编译器（`nf wiki build/check/get/search/related/context` + check43）、WP-11 Spec Compiler（intent→spec→task + check44）。
- 本审计不替代 G1–G5 门禁；外部 OPEN 在后续 Gate 前仍需保持挂账，不得改写成已关闭。

## 5. 复核命令

```bash
python -m pytest desktop/tests/test_g0_dod.py -q
python -c "import json;d=json.load(open('results/g0_dod.json',encoding='utf-8'));print(d['verdict'],d['p0_blockers'])"
```
