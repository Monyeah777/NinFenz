# 06 · 魔搭 ModelScope MCP 广场 —— 中文表单

> 入口：https://modelscope.cn/mcp （需要魔搭账号）

**名称**：NinFenz Content Gate（宁封子内容闸门）
**一句话**：给任何 AI agent 一个可校验的内容规范与资产底座——先查契约，再落笔。
**描述**：只读 MCP 服务器：把长内容的验收标准（协议 / 模块 / 管线 / 资产 / 馆藏）变成 agent 可调用的检索与取件工具面。12 个只读工具 + 1 个 prompt；支持 modern 2026-07-28 与 legacy 2025-11-25 双协议；零第三方依赖（Python 标准库）；无写路径。
**仓库**：https://github.com/Monyeah777/NinFenz
**站点（官方唯一入口）**：https://ninfenz.dev/
**安装命令**：`npx -y ninfenz serve`
**类目**：内容创作 / 开发者工具
**标签**：MCP、内容契约、规范驱动、可验证、知识库、Python、大模型
**许可**：MIT
**图标**：packaging/mcp/assets/icon-400.png

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

## 字段自检（与材料包同源 · 2026-11-14 复核补）

| 字段 | 本文件的值 | 真源 |
|---|---|---|
| 名称 | NinFenz Content Gate（宁封子内容闸门） | `SUBMIT.md §4` / `DIRECTORIES.md §1` |
| 仓库 | `https://github.com/Monyeah777/NinFenz` | 同上 |
| 站点 | `https://ninfenz.dev/` | 同上 |
| 安装 | `npx -y ninfenz serve` | 同上（零安装路径） |
| 工具面 | 12 只读工具 + 1 prompt（`assemble_guide`），无写路径 | `desktop/src/core/mcp_runtime.py` |
| 传输 | **仅 stdio**（Streamable HTTP / SSE 未提供） | 运行时入口 `nf serve` |
| 图标 | `packaging/mcp/assets/icon-400.png`（**真实 400×400**，读 IHDR） | `assets/README.md` |
| 许可 | MIT | `LICENSE` |

- **平台侧未验**：魔搭的类目词表、表单字段名、审核要求以页面为准；收录与否不可从仓库证明。
- **中文口径**：本件的「一句话 / 描述」是中文站专用措辞，与英文件**同义不同文**；改材料包时两边都要看一眼。
- **传输只填 stdio**：表单里 HTTP/SSE 留空即可——多填一个未支持的传输等于虚假声明。
- **不钉运行时计数**：描述文案不带 check/PASS/单测条数。
