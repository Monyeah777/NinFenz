# AI 治理（AI GOVERNANCE）

> ⛔ 操作指令：本件是 AI 面影响评估/模型风险/监管映射的人读面；机读真源 `protocol/ai_governance.json`（`nf-ai-governance/1`），判据 `desktop/tests/test_ai_eval_contract.py`。改风险/映射必须同步真源，否则判据红。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §3A D06（BL-02）
> 纪律：本仓是 AI 辅助的内容生产/装配系统，不是 AI 平台；**只做机制对照（mechanism-alignment），不声称合规/认证**。

## 范围与不做什么

- 目的：AI 辅助的长内容生产/装配（协议/模块/资产/管线/域包 → LLMWiki → 任务 → 装配 → 交付）。
- 受影响方：使用工具的用户、内容读者、仓库维护者。
- 不做：模型训练、通用 Agent 监控/取证、托管 GRC/SaaS；不对具体使用场景判定监管风险等级。

## 影响评估（四项标准）

| 编号 | 问题 | 本仓回答 | 证据 |
|---|---|---|---|
| IA-01 | 是否处理特殊类别个人数据？ | 本仓不主动处理；用户写进内容资产时风险回到用户侧 | `PRIVACY.md` |
| IA-02 | 是否有自动化决策影响个人权益？ | 否：产出内容不直接决定个人权益；交付前有人类复核闸门 | `desktop/src/core/trust/human_review.py` |
| IA-03 | 是否有实质人工监督？ | 是：人类复核须签名，未签=PENDING（不冒充通过） | `protocol/trust/human-review.schema.json` |
| IA-04 | 是否有可追溯的模型/评测证据？ | 是：模型卡绑定模型摘要；替换使旧证据失效 | `desktop/src/core/trust/model_card.py` |

- **人类监督**：human-in-the-loop；AI 不能签署。
- **透明度**：AIGC 标识证据可接入（labeling）。
- **救济**：证据不足时显式待定（PENDING），不写成通过。

## 模型风险登记

| 编号 | 风险 | 类别 | 概率 | 影响 | 缓解 | 状态 |
|---|---|---|---|---|---|---|
| MR-01 | 模型替换后旧证据仍被当作有效 | map | medium | high | 模型卡绑定模型摘要；替换→MODEL-REPLACED | enforced |
| MR-02 | 人类复核被伪造或未签冒充通过 | govern | medium | high | 签名复核；PENDING≠通过；AI 不能签署 | enforced |
| MR-03 | 评测自嗨/Goodhart | measure | high | medium | 预注册+反指标+inter-rater+两份报告不合并 | partial（G0 收口：`docs/eval/EVAL_PROTOCOL.md`） |
| MR-04 | 提示词/上下文注入导致越权或角色升级 | manage | medium | high | 外部材料按数据处理+注入预算+角色隔离（G1 落地运行时） | partial（G1） |
| MR-05 | 监管映射被写成合规结论 | govern | medium | medium | claim 只允许 mechanism-alignment/not-claimed | enforced |

## 监管映射（机制对照，不构成合规结论）

| 框架 | 条款 | 本仓控制 | claim |
|---|---|---|---|
| NIST AI RMF 1.0 | GOVERN / MAP / MEASURE / MANAGE | AI 治理件 + 模型风险登记 + 效度协议 | mechanism-alignment |
| ISO/IEC 42001:2023 | AI 管理体系要求 | 模型卡/人类复核/证据链（机制对照） | mechanism-alignment |
| ISO/IEC 23894:2023 | AI 风险管理过程 | 模型风险登记（概率/影响/缓解/证据/owner/状态） | mechanism-alignment |
| ISO/IEC 5338:2023 | AI 系统生命周期过程 | 生产/装配流程与验收（spec→task→assembly→output） | mechanism-alignment |
| EU AI Act（一般义务对照） | 透明度 / 人工监督 | AIGC 标识证据 + 人类复核签名（不判定风险等级） | mechanism-alignment |
| SR 11-7（模型风险管理） | 模型验证 / 持续监控 | 预注册评测协议 + 效度威胁检查 + 模型卡绑定 | mechanism-alignment |

## 声明边界

- 不声称合规、认证、高风险系统合格或不可抵赖；映射只说明机制对照，不构成法律意见。
- `partial`/`planned` 项就是未完成的控制面（机读里有 planned_gate），不作为对外保证。

## 复核命令

```bash
python -m pytest desktop/tests/test_ai_eval_contract.py -q
python -m pytest desktop/tests/test_trust_model_card.py desktop/tests/test_trust_human_review.py -q
```
