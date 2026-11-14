# G1 DoD 收口审计（G1 DOD · QG1）

> ⛔ 操作指令：本件是 G1（LLMWiki + Spec）收口审计人读结果；机读真源 `results/g1_dod.json`（`nf-g1-dod/1`），判据 `desktop/tests/test_g1_dod.py`。**pass-with-open-items ≠ 零缺陷**：开发性债务与外部 OPEN 显式挂账；P0 阻断=0 才允许进 G2。
> 状态：v1（2026-11-14 · G1 收口）· 依据：§14.3 / §11.2 G1 / §13A QG1 / §13A L3
> 结论：**pass-with-open-items（P0 阻断 = 0）** → 下一 Gate：G2。

## 1. §14.3 DoD（8 条）

| 编号 | 判据 | 状态 | 证据 |
|---|---|---|---|
| DOD-01 | FR/NFR 正/反测试（WK-01…08） | pass | wiki/spec/packer 三套判据 + verify.sh |
| DOD-02 | 旧基线能红、新基线全绿（变异自证） | pass | 三套判据的变异用例 + BASELINE |
| DOD-03 | 冻结链按序执行并解释 diff | pass | receipt_chain/conformance/approvals/RECEIPTS |
| DOD-04 | .NET/Rust 面同步（如涉及） | **n/a** | G1 未改引擎；dotnet BLOCKED 如实记 |
| DOD-05 | 文档/ADR/keyword 索引更新 | pass | docs/wiki.md/spec-compiler.md/context-packer.md |
| DOD-06 | SELF_AUDIT P0=0 | pass | `results/trust/SELF_AUDIT.json`（stop.p0=0） |
| DOD-07 | 无未登记 OPEN/TODO 关键路径 | pass-with-open | OPEN-PRODUCT/OPEN-EXTERNAL 挂账 |
| DOD-08 | 交接报告完整 | pass | BASELINE + RESULTS + 台账 |

## 2. §11.2 G1 交付物（G1-ART：WP-10…13 全绿）

| WP | 交付 | 状态 |
|---|---|---|
| WP-10 | Wiki 编译器（133 页/五命令/三入口/陈旧判据） | ✅ |
| WP-11 | Spec Compiler（intent→spec→task；确定性/拒绝未知/无环） | ✅ |
| WP-12 | Context Packer（角色/预算/引用/抗注入） | ✅ |
| WP-13 | check43/44 接入 verify（49 条 · PASS=89）+ 派生面重生成 | ✅ |

## 3. QG1（Wiki + Spec）

| 编号 | 判据 | 结果 |
|---|---|---|
| QG1-01 | Wiki 覆盖（module 13 / pipeline 3 / domain 100 / protocol 14 / asset 3 = **133 页**） | pass |
| QG1-02 | ID 唯一且 `wiki:` 前缀 | pass |
| QG1-03 | relations 全部可解析；INDEX/GRAPH 一致 | pass |
| QG1-04 | 页面过 `nf-wiki-page/1`；spec/task 过 `nf-spec/1`/`nf-task/1` | pass |
| QG1-05 | 陈旧：真源现算 digest，check43 在 verify.sh 实跑 | pass |
| QG1-06 | 引用：每页 citations 非空；context pack `citation_rate=100%` | pass |
| QG1-07 | Spec 编译确定（同 intent 逐字节）+ 拒绝未知（check44 实跑） | pass |
| QG1-L3 | Context Packer：citation 100% / 超预算率 0 / 注入可检出 / 角色升级=0 | pass |

## 4. OPEN（不阻断 G1）

- **OPEN-PRODUCT / OPEN-EXTERNAL**：外部操作（访谈/试点/公共日志/外部见证/语言服务/第三方合规审核）未执行。
- **G1-DEBT-01**：check44 只覆盖样本 intent；真实 intent 集与更多 kind 组合在 G2 扩面。
- **G1-DEBT-02**：Context Packer 报告按需生成，无固定 `context-report.json`（避免 Wiki 真源变化造成陈旧件）。

## 5. 复核命令

```bash
bash verify.sh --checks-only          # 期望 PASS=89 WARN=2 FAIL=0（含 check43/44）
python -m pytest desktop/tests/test_g1_dod.py -q
python -c "import json;d=json.load(open('results/g1_dod.json',encoding='utf-8'));print(d['verdict'],d['p0_blockers'])"
```
