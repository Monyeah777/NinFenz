# LLMWiki（`nf wiki`，WP-10）

> ⛔ 操作指令：本件是 WP-10 Wiki 编译器的人读说明；生成物在 `wiki/`（禁手改），机读真源是各真源文件；判据 `desktop/tests/test_wiki_compiler_contract.py`；契约 `protocol/production/wiki-page.schema.json`。
> 状态：v1（G1 · 2026-11-14）· 纪律：Wiki 是投影，不是第二真源（WK-01…WK-08）

## 命令

```bash
python scripts/nf.py wiki build --write   # 编译落 wiki/（pages/index/graph/llms.txt/mcp.json）
python scripts/nf.py wiki check           # 完整性/覆盖/陈旧/关系/ID 自检（exit 1 = 红）
python scripts/nf.py wiki get wiki:module:M06
python scripts/nf.py wiki search 管线
python scripts/nf.py wiki related wiki:module:M06
python scripts/nf.py wiki context wiki:pipeline:P00_通用文档生成管线 --budget 1200
```

## 覆盖与真源

| 页面类型 | 真源 | 数量 |
|---|---|---|
| protocol | `protocol/schema/*.schema.json`（9）+ `protocol/production/*.schema.json`（5） | 14 |
| module | `desktop/src/core/registry.json#modules` | 13 |
| pipeline | `03_管线库/*.md` | 3 |
| domain | `community/*/outputs/DOMAIN_SPEC.json` | 100 |
| asset | `05_资产库/` 条目 | 3 |

## 判据（WK-01…WK-08）

- 页面只存 summary + spec_ref + digest + relations + citations，**不复制正文**（`body/content/text` 字段即红，summary ≤240 字符）。
- `check` 用真源现算 digest 比对 committed 页 → 源变即陈旧（改生成物同样红）。
- ID 唯一且 `wiki:` 前缀；relations 目标必须可解析；INDEX/GRAPH/MCP 与 pages 集一致。
- 真源变化后必须 `wiki build --write` 重编译；禁止手改 `wiki/`。

## 已知边界

- `search` 是子串检索（非语义检索/RAG）；`context` 是轻量打包（完整 Context Packer 属 WP-12）。
- 编译物随真源变化由 `wiki check` 判 stale；CI 侧门禁（check43/44）在 WP-13 接入。
