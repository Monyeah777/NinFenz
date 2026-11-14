# 09 · 通用块（英文）—— 任何未列出的目录站都能用

```text
Name: NinFenz Content Gate
Tagline: Read-only MCP server for a content contract layer: protocol, modules, pipelines, assets, library.
Description: A read-only MCP server that turns long-form acceptance criteria (protocol specs, modules, pipelines, assets, knowledge library) into agent-callable retrieval tools. 12 read-only tools + 1 prompt (assemble_guide); dual protocol era (2026-07-28 modern / 2025-11-25 legacy); zero third-party deps (Python stdlib); no write paths.
Install: npx -y ninfenz serve
Repo: https://github.com/Monyeah777/NinFenz
Site: https://ninfenz.dev/
Category: content-creation
Tags: mcp, content-contract, spec-driven, verification, knowledge-base, python, llm
License: MIT
```

## 传输配置（stdio）—— 只填 Stdio，另两种留空

我们**只提供 stdio**（本地进程）；Streamable HTTP 与 SSE 未提供 → 表单里留空即可（未配置的方式不会展示在详情页）。

**完整配置（`mcpServers` 形式，直接整段粘）**

```json
{
  "mcpServers": {
    "ninfenz": {
      "command": "npx",
      "args": ["-y", "ninfenz", "serve"]
    }
  }
}
```

**字段式（表单把 command / args 拆开问时）**

| 字段 | 值 |
|---|---|
| 名称 / name | `ninfenz` |
| command | `npx` |
| args | `-y ninfenz serve`（或数组 `["-y","ninfenz","serve"]`） |
| env | 留空（无需任何密钥/变量） |

**备用命令**

- 本地 npm 镜像滞后时：`npx -y --registry https://registry.npmjs.org ninfenz serve`
- 本地检出时：command `python` · args `["scripts/nf.py","serve"]` · cwd 填克隆路径
- Windows 客户端若找不到 `npx`：command 改 `cmd` · args `["/c","npx","-y","ninfenz","serve"]`

**同页常问的其它字段**

| 字段 | 值 |
|---|---|
| 传输 / transport | `stdio` |
| 协议版本 | modern `2026-07-28` + legacy `2025-11-25`（双版本并存） |
| 工具数 / prompts | 12 个只读工具 + 1 个 prompt（`assemble_guide`）；`additionalProperties: false`，参数不合即 `-32602` |
| 是否只读 | 是（无写路径） |


---

## 自检（与材料包同源 · 2026-11-14 复核补）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 字段 | Name / Tagline / Description / Install / Repo / Site / Category / Tags / License **九项齐全** | 上方 `text` 块 |
| 工具面 | **12 只读工具 + 1 prompt**（`assemble_guide`），无写路径 | `desktop/src/core/mcp_runtime.py` |
| 协议 | modern `2026-07-28` + legacy `2025-11-25` | 同上 |
| 传输 | **仅 stdio**（Streamable HTTP / SSE 未提供，表单留空） | `nf serve` 入口 |
| 依赖 | 零第三方（Python 标准库） | `pyproject.toml` 的 `dependencies` 为空 |
| 许可 | MIT | `LICENSE` |
| 中英对偶 | 本件与 `10-generic-zh.md` **传输段逐字相同**、字段块同义不同文 | 判据 `test_generic_blocks_doc_contract` |
| 平台侧 | **平台侧未验**：任何未列出目录站的字段名/限制都以该站为准 | 无法从仓库证明 |

- **通用块的用途**：任何未单独列出的目录站，直接整段粘上方 `text` 块；需要 `mcpServers` JSON 的站，粘「完整配置」块。
- **不钉运行时计数**：本件文案不带 check/PASS/单测条数——对外文案里的快照数字等于过期承诺。
- 中英两份**同义不同文**：改字段值必须两边一起改（`10-generic-zh.md` 是中文版）。
