# AI 证据链（WP-40，G4）

> ⛔ 操作指令：本件是 WP-40 AI 证据链的人读说明；机读真源 `protocol/ai_evidence.json`（`nf-ai-evidence/1`），判据 `desktop/tests/test_ai_evidence_contract.py`，实现 `desktop/src/core/ai_evidence.py`，样例件 `results/ai/{model-card,lineage,human-review}.json`。缺一即 PENDING/拒收，不冒充通过。
> 状态：v1（G4 · 2026-11-15）· 依据：G4 WP-40（model card/eval/lineage/human review）

## 三件套与绑定

| 工件 | 契约 | 绑定规则 |
|---|---|---|
| 模型卡 | `nf-model-card/1` | 必填 model_id/model_digest/provider/eval_protocol/issued_at；`eval_protocol.protocol_digest` == `sha256(protocol/eval_validity.json)` 实时摘要（协议一改旧证据失效） |
| 上下文血缘 | `nf-context-lineage/1` | `model_card_digest` == **模型身份摘要**（model_digest+eval_protocol）；segments prev/head/lineage_digest 连续可复算 |
| 人类复核 | `nf-human-review/1` | `subject_kind=card`、`subject_digest` == 整卡摘要、`decision=approve`、`reviewer.kind=human`、ISO-8601 时间 |

## 状态（`state()`）

`PENDING`（缺卡/缺复核）→ `APPROVED`（三件 + 绑定全过）｜`REJECTED`/`ESCALATED`（decision）｜`INVALID`（结构/绑定坏）。**PENDING 永不等于通过。**

## 拒收码

`AI-CARD-MISSING` / `AI-CARD-INVALID` / `AI-EVAL-DIGEST-MISMATCH` / `AI-LINEAGE-BROKEN` / `AI-REVIEW-MISSING` / `AI-REVIEW-NOT-APPROVED`。

## 边界

- 本件只判证据链结构与绑定；**模型能力/质量不作保证**，不声称任何外部模型/供应商合规。
- 复核的 DSSE 信封验签由 check46 / trust `human_review` 判据覆盖，本件不重复造签名面。
- 样例件固定时间戳、确定性生成；committed == 实时重算由判据守。
