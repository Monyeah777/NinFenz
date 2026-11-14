# NF-Final 质量报告收口 + 最终 Gate 审计（FINAL DOD）

> ⛔ 操作指令：本件是 NF-Final 质量报告收口与最终 Gate 审计人读结果；机读真源 `results/final_dod.json`（`nf-final-dod/1`），判据 `desktop/tests/test_final_dod.py`。**pass-with-open-items ≠ 零缺陷**：外部 OPEN 与债务不因收口消失。
> 状态：v1（2026-11-15 · Final Gate）· 依据：§14.3 / §14.4 / §11.2 全 Gate
> 结论：**pass-with-open-items（P0 阻断 = 0）** — NF-Final G0–G5 全部收口。

## 1. Gate 收口状态

| Gate | 名称 | verdict | P0 | 收口件 |
|---|---|---|---|---|
| G0 | 地基冻结 | pass-with-open-items | 0 | `g0_dod.json` |
| G1 | 结构化理解 | pass-with-open-items | 0 | `g1_dod.json` |
| G2 | 生产/装配黄金路径 | pass-with-open-items | 0 | `g2_dod.json` |
| G3 | 治理平面（可选） | pass-with-open-items | 0 | `g3_dod.json` |
| G4 | AI 信任 + 生态导出 | pass-with-open-items | 0 | `g4_dod.json` |
| G5 | 自审计与稳定 | pass-with-open-items | 0 | 本件 |

## 2. 门禁实测（最终）

- `bash verify.sh --checks-only`：**53 条 · PASS=97 · WARN=2 · FAIL=0**（`check1-44/45/46/47/48/49/50/51/52/53`）
- conformance：conformant（**27/27** 契约）；freshness：**4/4**；CQ：**P0=0**（P2/P3 存量如实）；SELF_AUDIT：**P0=0**
- 稳定性：7 条纯管线 × 10 次摘要 **0 mismatch**（非 soak）

## 3. DoD 八条

| 编号 | 判据 | 状态 |
|---|---|---|
| FIN-01 | 全 Gate 收口（P0=0） | pass |
| FIN-02 | 门禁实测 53/PASS=97/WARN=2/FAIL=0 | pass |
| FIN-03 | §14.3/§14.4 DoD 八条对齐 | pass |
| FIN-04 | OPEN 清单完整、带 owner、非阻断 | pass |
| FIN-05 | claims 边界（不声称认证/合规/外验） | pass |
| FIN-06 | 交接完整（BASELINE/RESULTS/台账/复现） | pass |
| FIN-07 | 稳定性证据（0 mismatch，非 soak） | pass |
| FIN-08 | 文档 claims 一致（check53） | pass |

## 4. OPEN（收口不关闭）

- **OPEN-EXTERNAL**：公共日志/外部 witness/离线解包/第三方合规审核未执行。
- **OPEN-TOOLS**：cosign 不在场；TSA/透明日志未执行 → T2+ 不可达。
- **OPEN-PRODUCT**：外部真实生产数据/试点/访谈未执行（M-05/M-06 no-data）。
- **G2-DEBT-01**、**G2-DEBT-02**、**G3-DEBT-01**、**G4-DEBT-01**、**G4-DEBT-02**、**G4-DEBT-03**、**G5-DEBT-01**、**G5-DEBT-02**：见机读件，全部非阻断。

## 5. 复现

```bash
bash verify.sh --checks-only            # 期望 PASS=97 WARN=2 FAIL=0
python -m pytest desktop/tests/test_final_dod.py -q
python -c "import json;d=json.load(open('results/final_dod.json',encoding='utf-8'));print(d['schema'],len(d['gates']))"
```

**未跑**：`bash verify.sh --full`（CI full 档）、外部实测线、长稳 soak——如实记，不写成全绿。
