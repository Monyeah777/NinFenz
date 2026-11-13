# 10 · 通用块（中文）—— 任何中文目录站都能用

```text
名称：NinFenz Content Gate（宁封子内容闸门）
一句话：给任何 AI agent 一个可校验的内容规范与资产底座——先查契约，再落笔。
描述：只读 MCP 服务器：把长内容的验收标准（协议 / 模块 / 管线 / 资产 / 馆藏）变成 agent 可调用的检索与取件工具面。12 个只读工具 + 1 个 prompt（assemble_guide）；modern 2026-07-28 与 legacy 2025-11-25 双协议；零第三方依赖（Python 标准库）；无写路径。
安装：npx -y ninfenz serve
仓库：https://github.com/Monyeah777/NinFenz
站点：https://ninfenz.dev/
类目：内容创作
标签：MCP、内容契约、规范驱动、可验证、知识库、Python、大模型
许可：MIT
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
| 中文字段 | 名称 / 一句话 / 描述 / 安装 / 仓库 / 站点 / 类目 / 标签 / 许可 **九项齐全** | 上方 `text` 块 |
| 工具面 | **12 个只读工具 + 1 个 prompt**（`assemble_guide`），无写路径 | `desktop/src/core/mcp_runtime.py` |
| 协议 | modern `2026-07-28` + legacy `2025-11-25`（双版本并存） | 同上 |
| 传输 | **仅 stdio**（Streamable HTTP 与 SSE 未提供，表单留空） | `nf serve` 入口 |
| 依赖 | 零第三方依赖（Python 标准库） | `pyproject.toml` 的 `dependencies` 为空 |
| 许可 | MIT | `LICENSE` |
| 中英对偶 | 本件与 `09-generic-en.md` **传输段逐字相同**、字段块同义不同文 | 判据 `test_generic_blocks_doc_contract` |
| 平台侧 | **平台侧未验**：中文目录站的字段名/类目词表/限制都以该站为准 | 无法从仓库证明 |

- **通用块的用途**：任何未单独列出的**中文**目录站，直接整段粘上方 `text` 块；需要 `mcpServers` JSON 的站，粘「完整配置」块。
- **不钉运行时计数**：本件文案不带 check/PASS/单测条数——对外文案里的快照数字等于过期承诺。
- 中英两份**同义不同文**：改字段值必须两边一起改（`09-generic-en.md` 是英文版）；**类目**在英文站填 `content-creation`、中文站填「内容创作」，不要混用。
