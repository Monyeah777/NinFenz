# AIGC / 标注证据（WP-43，G4）

> ⛔ 操作指令：本件是 WP-43 AIGC 标注证据的人读说明；机读真源 `protocol/aigc_labeling.json`（`nf-aigc-labeling/1`），判据 `desktop/tests/test_aigc_labeling_contract.py`，实现 `desktop/src/core/aigc_labeling.py`，样例 `results/ai/aigc-label.json`。无标识不默认 human。
> 状态：v1（G4 · 2026-11-15）· 依据：G4 WP-43（AIGC/labeling 证据接入）

## 标识（`nf-aigc-label/1`）

必填：`schema / subject_digest / subject_kind / label / generator / provenance_refs / labeled_at`。

| label | 语义 | 额外要求 |
|---|---|---|
| `ai-generated` | 完全由模型生成 | 绑定模型卡 + 引用 AI 证据面 |
| `ai-assisted` | 人机协作（样例） | 同上 |
| `human` | 人类产出 | 复核 `decision=approve` |

## 绑定与闭合

- `generator.model_digest` == `results/ai/model-card.json` 的 `model_digest`；
- `subject_digest` == 被标注产物 SHA-256（样例：`results/delivery/wiki-module-M06/artifact.md`）；
- `provenance_refs` 只允许 `results/ai/*` 或 `protocol/ai_evidence.json`，且必须全部在场；
- `labeled_at` 固定样例时间（UTC，不读时钟）→ 样例 committed == 实时重算。

## 诚实规则

- **未标注 = 红**（不默认 human）；
- 标识不闭合 / 引用悬空 / human 无 approve = 红；
- 只做仓库内证据面，**不声称符合外部内容标识法规/标准**，不替代人工审核与平台义务。

## 复核命令

```bash
python -c "import sys;sys.path.insert(0,'desktop/src');from core import aigc_labeling as a;a.write_sample('.')"
python -m pytest desktop/tests/test_aigc_labeling_contract.py -q
```
