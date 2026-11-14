# 同行差分（PEER DIFF，§4A R5）

> ⛔ 操作指令：本件是 §4A R5 同行差分的人读结果；机读真源 `results/reverse/peers.json`（`nf-reverse-peers/1`），判据 `desktop/tests/test_reverse_peers.py`。**只作机制层借鉴，不作质量背书**（STRATEGY §3）；未做外部测评，不声称优/劣；每条影响必须落到本仓件或明确 G1/G3 决策。
> 状态：v1（2026-11-14 · G0 §4A R5）· 前置：`CONTRACT_MAP.md`（R1）…`FAILURE_ARCHAEOLOGY.md`（R4）

## 1. 对照矩阵

| 编号 | 同行/标准 | 证明什么 | 不覆盖什么 | 接口模型 | 可借用 | 结论 |
|---|---|---|---|---|---|---|
| P-01 | Spec Kit | 意图→spec→plan→tasks 分阶段可评审 | 无可执行 contract/task schema、无产物验收 | Markdown + 目录约定 | 阶段分解与 spec 先行 | adapt |
| P-02 | OpenSpec | 变更先行 + 规格与实现对齐可审计 | 无产物证据/签名/断网复算 | 变更提案 + 规范 + 归档 | 改动必附规格差异 | adapt |
| P-03 | DeepWiki/GitMCP/Context7 | 仓库→可检索上下文 | 不保证页面=真源投影/无 digest/无生成物纪律 | 检索 API/MCP | 「页面是投影」+ MCP 接口形态 | avoid-build |
| P-04 | ODCS/datacontract-cli | 数据契约字段/质量规则/版本化 + CLI 校验 | 不覆盖内容生产装配与证据链 | YAML/JSON 契约 + CLI | 质量规则字段化/版本化 | adapt |
| P-05 | in-toto/Sigstore/CycloneDX | 声明链/签名与透明日志/SBOM 生态兼容 | 缺锚不可判定口径、T0–T4、离线策略 | DSSE/envelope/BOM | DSSE、锚、BOM 字段映射 | adopt |
| P-06 | OPA/Cedar | 策略即代码、可独立求值 | 不绑定证据链与产物 | Rego/Cedar + 判定 API | 策略外置 + 判定可复算 | adapt |

## 2. 影响设计的结论（DoD：≥1 条影响最终设计）

| 编号 | 目标 Gate | 决策 | 理由 |
|---|---|---|---|
| D-PD-01 | G1 | 不造交互式 spec IDE；借 Spec Kit 生命周期分段，但 spec/task 必须可执行 schema（nf-spec/1、nf-task/1）并由编译判据验收 | 文档约定不可机检；NF 差异化是可验收契约 |
| D-PD-02 | G1 | 不造通用 wiki 引擎；页面强制 spec_ref + digest + 新鲜度判据（WP-10） | 通用 wiki 会变第二真源；可复算优先 |
| D-PD-03 | G3 | 证据/策略只借 in-toto/DSSE/OPA 接口形态（envelope/policy schema），运行时适配器隔离、缺锚显式降级 | core-only 与 T0–T4 诚实口径优先 |

## 3. 借/不造边界

- **借**：生命周期分段（P-01/02）、投影+检索接口（P-03）、质量规则字段化（P-04）、DSSE/锚/BOM（P-05）、策略外置（P-06）。
- **不造**：交互式 spec IDE、通用 wiki 引擎、Rego/Cedar 求值器、签名/透明日志运行时；全部以 schema/适配器表达。
- **不做**：以同行热度或外部项目作为立项/质量论据（STRATEGY §3 明令禁止）。

## 4. 复核命令

```bash
python -m pytest desktop/tests/test_reverse_peers.py -q
python -c "import json;d=json.load(open('results/reverse/peers.json',encoding='utf-8'));print(len(d['peers']),len(d['design_decisions']))"
```

## 5. 交接（R6）

- R6 把 D-PD-01…03 与 R1 G-01…G-05、R3 C-01…C-03、R4 R4-01…09 一起转成机检不变量/反例；不能测的标 `UNOBSERVABLE`。
