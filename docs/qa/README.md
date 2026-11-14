# 分层 QA（docs/qa/，§13A.2 L0–L20）

> ⛔ 操作指令：本目录是 §13A.2 分层 QA 的人读索引；机读真源 `results/qa/layers.json`（`nf-qa-layers/1`），生成器 `core/layer_reports.py`，判据 `desktop/tests/test_layer_reports.py`。未做的层如实 `partial`（不写成 covered）。
> 状态：v1（2026-11-15 · G5 收口补件）

| 层 | 名称 | 状态（机读件为准） |
|---|---|---|
| L0 | 真源/契约 | covered（assertions + 契约 schema） |
| L1 | LLMWiki | covered（`results/wiki-report.json`） |
| L2 | Spec Compiler | covered（`results/spec-report.json`） |
| L3 | Context Packer | partial（测试在；缺 context-report.json） |
| L4–L9 | Adapter/Assembly/Output/Delivery/Governance/AI | covered（各自 report/记录件） |
| L10–L11 | 安全/隐私、运维/恢复 | partial（红队矩阵、故障注入/长稳未系统化） |
| L12 | 文档/上手 | covered（docs-claims） |
| L13–L14 | 生态/标准、隐私/法务 | covered（interop/AIBOM、privacy/legal） |
| L15 | 可靠性/事件/BCP | partial（IR/BCP 演练记录未系统化） |
| L16–L18 | A11y/i18n、产品、开源治理 | L16/L18 covered；L17 partial（访谈/试点外部 OPEN） |
| L19–L20 | 商业/支持、伦理/保证 | L20 covered；L19 partial（定价/SLA 未外部验证） |

复算：`python -c "import sys;sys.path.insert(0,'desktop/src');from core import layer_reports as l;l.write('.')"` → `python -m pytest desktop/tests/test_layer_reports.py -q`

边界：映射是内部证据索引，不是认证；partial 项保持 partial，外部 OPEN 不因收口关闭。
