# 保证案例（ASSURANCE CASE，GSN/CAE）

> ⛔ 操作指令：本件是 NF-Final §16A 保证案例的人读面；机读真源 `results/assurance/CLAIMS.json`（`nf-assurance-claims/1`），RAID 见 `docs/RAID.md`，判据 `desktop/tests/test_assurance_contract.py`。**测试通过不能替代论证**：每条 Argument 必须有 assumption/rebuttal 与真实证据。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §16A（GSN/CAE、ISO/IEC 15026 思想）

## 顶层目标（C）

| Goal | 主张 | 状态 | 关联论证 | 未关缺口 |
|---|---|---|---|---|
| C0 | NF 能在无治理环境下完成规范驱动的生产/装配交付 | partial | A1 / A2 / A3 | OPEN-G1 / OPEN-G2 |
| C1 | NF 的治理平面可独立验证非 NF 产物 | supported | A4 / A5 | — |
| C2 | NF 的 QA 不是自欺（关键不变量可证伪、评测效度有据） | partial | A6 / A7 | OPEN-MUT |
| C3 | NF 可持续/可支持/可合规（工程意义上） | partial | A8 | OPEN-PRODUCT / OPEN-EXTERNAL |

## 论证（A）

| Argument | 主张 | 关键证据 | 状态 |
|---|---|---|---|
| A1 | 生产与治理边界可静态验证（闭包零跨界） | `protocol/independence.json` + `test_independence.py` + `check_independence.py` | supported |
| A2 | Wiki/spec 是单一真源投影 | `protocol/production/wiki-page.schema.json` + `docs/standards/index.md` + `test_schema_reference.py` | partial（OPEN-G1：编译器未建） |
| A3 | 2 个 Agent adapter 同 spec 可移植 | `protocol/production/task.schema.json` + `agent_rules_adapter.py` | open（OPEN-G2：parity 判据未建） |
| A4 | 契约/证据/验证可离线复算（缺锚 exit 2） | `trust/verify.py` + `test_trust_verify.py` + `trust/verify.schema.json` | supported |
| A5 | 签名/时间戳/透明日志复用成熟标准 | `timestamp.py` + `interop_export.py` + `results/interop/intoto.json` + `test_trust_public_anchor.py` | supported |
| A6 | 关键不变量有变异/负例测试 | `test_trust_gate45.py` + `results/production/threat_vectors.json` + `test_production_threat_vectors.py` | partial（OPEN-MUT：全仓 mutation 未测） |
| A7 | 评测预注册 + inter-rater + 反指标 | `protocol/eval_validity.json` + `results/eval/interrater_sample.json` + `test_ai_eval_contract.py` | supported |
| A8 | 跨域盲区（隐私/安全/供应链/法务/AI/可访问性/语言面）有登记与判据 | 各 `protocol/*.json` + 对应 test | partial（OPEN-PRODUCT） |

## 假设、反驳与缺口

- **假设**：AS-01 用户需要规范驱动交付（未验证，owner=product）；AS-02 本地优先足以覆盖目标场景（未验证）。
- **反驳**：RB-01 Spec Kit/OpenSpec 下探（open）；RB-02 DeepWiki/Context7 泛化（mitigated，本仓聚焦产线而非问答）；RB-03 AI 审查形式化（open，靠预注册/反指标/变异自证缓解，外部复核仍属外部操作）。
- **缺口**（全部有 owner，进 RAID）：OPEN-G1（WP-10/11）、OPEN-G2（WP-20）、OPEN-MUT（WP-0H/54）、OPEN-PRODUCT（WP-0A 外部访谈）、OPEN-EXTERNAL（外部提交/见证/语言服务/第三方合规审核）。

## 规则

1. 每个 Argument 必须有 `assumption` 与 `rebuttal`（可被反驳），否则判据红。
2. `supported` 至少 2 件证据且含测试/门禁证据；`partial`/`open`/`accepted-risk` 必须写缺口 id。
3. 缺口必须在 RAID 里 link（一一对应）；「测试通过」不能替代论证。
4. 不声称合规/认证；外部操作不作为本仓能力背书。

## 复核命令

```bash
python -m pytest desktop/tests/test_assurance_contract.py -q
python -c "import json;d=json.load(open('results/assurance/CLAIMS.json',encoding='utf-8'));print(len(d['goals']),len(d['arguments']),len(d['gaps']))"
```
