# 关键词与扩展口（WP-52，G5）

> ⛔ 操作指令：本件是 §17 关键词贴片与 §18 扩展/创新口的人读索引；机读真源 `protocol/keywords.json`（`nf-keywords/1`），检查器 `nf keywords --check`（= verify check57），判据 `desktop/tests/test_keywords_contract.py`。索引整理不关闭任何 OPEN 项，也不是认证/合规声明。
> 状态：v1（G5 · 2026-11-15）· 依据：§17（标签/关键词索引/中英对照）+ §18（扩展与创新口）

## 标签（DOMAIN-KIND 形式）

`[PR]` 生产/装配 · `[WK]` Wiki/规范 · `[GV]` 治理 · `[AI]` AI 信任 · `[IN]` 独立性 · `[TAG]` 关键词/扩展 ·
`[SCHEMA]` 数据契约 · `[API]` CLI/MCP/CI · `[THREAT-*]` 威胁 · `[GATE]` 门禁 · `[ADR]` 决策 ·
`[EXT-*]` 扩展点 · `[OPEN-*]` 创新口 · `[HONESTY]` 声明边界。

规则：标签必须在本表定义；用到的标签未在册 = 孤儿标签（`nf keywords --check` 红）；每段/函数 ≤3 标签。

## 关键词索引与中英对照

`protocol/keywords.json` 的 `keyword_index`（tag→keywords/owner/status）与 `synonyms`（CN/EN 最小术语集：
生产装配/assembly、规范/spec、契约/contract、治理/governance、证据/evidence、信任等级/trust level、
不可抵赖/non-repudiation——后者仅 T3+ 可声称）。

## 扩展与创新口（§18）

| ID | 方向 | 接口 | 状态 |
|---|---|---|---|
| OPEN-ZK | 选择性披露 | EXT-10 | open |
| OPEN-PQ | 后量子 | EXT-01 | open |
| OPEN-FED | 跨组织联邦 | EXT-03/04 | open |
| OPEN-AIBOM | AI BOM（CycloneDX/SPDX） | EXT-06 | **closed**（`results/ai/aibom.*.json`） |
| OPEN-AGENT-AUTH | Agent 授权 | entity/policy | open |
| OPEN-HUMAN | 人类复核凭证 | nf-human-review/1 | **partial**（schema+实现在场） |
| OPEN-REG | 监管映射 | policy/docs | open（不声称合规） |
| OPEN-REVOCATION | 撤销/状态 | EXT-04 | **partial**（`core/revocations.py`） |
| OPEN-WITNESS | 见证分裂/阈值 | EXT-03 | open |
| OPEN-PRIVACY | 可验证脱敏 | EXT-10 | open |
| OPEN-VERIFIER-WASM | 浏览器/边缘验证 | EXT-09 | open |
| OPEN-ARCHIVE | WORM/归档 | EXT-08 | open（不声称法规） |

`open` 必须有 owner+interface；`closed` 必须有在场证据——**不得静默关闭**。

## 复核命令

```bash
python scripts/nf.py keywords --check
python -m pytest desktop/tests/test_keywords_contract.py -q
```
