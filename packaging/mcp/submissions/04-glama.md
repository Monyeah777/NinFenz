# 04 · Glama —— 认领/提交文案

> 入口：https://glama.ai/mcp/servers?query=ninfenz （先搜；有条目就 Claim，没有就提交仓库地址）

**仓库地址（填这一条即可）**：https://github.com/Monyeah777/NinFenz

**若需要描述**：

**名称 / Name**：NinFenz Content Gate
**一句话 / One-liner（EN）**：AI output assurance MCP server: versioned contracts, deterministic release gates and reproducible evidence.
**一句话 / One-liner（ZH）**：面向 AI 输出的证据门禁：版本化契约、确定性发布门禁与可复现证据。
**描述 / Description**：本地优先的 MCP 服务器：把 AI 文档的验收要求变成 agent 可检索的协议、模块、管线、资产与馆藏，并通过 CLI/CI 执行确定性门禁、规则级证据和可复现报告。12 个只读工具 + 1 个 prompt（assemble_guide）；支持 modern 2026-07-28 与 legacy 2025-11-25 双协议；零第三方依赖（Python 标准库）；MCP 服务面本身无写路径。
**仓库 / Repo**：https://github.com/Monyeah777/NinFenz
**站点 / Site**：https://ninfenz.dev/
**安装 / Install**：`npx -y ninfenz serve`
**类目 / Category**：content-creation（备选 developer-tools / knowledge-management）
**标签 / Tags**：mcp, content-contract, spec-driven, verification, knowledge-base, python, llm
**许可 / License**：AGPL-3.0-only or Commercial
**图标 / Icon**：packaging/mcp/assets/icon-400.png（400×400 PNG）

## 仓库侧已备（2026-10-18）

| 文件 | 作用 |
|---|---|
| `Dockerfile` | Glama 构建 + stdio 启动（非 root、无 pip install、`CMD` = `python scripts/nf.py serve`） |
| `glama.json` | 主张维护者 `Monyeah777`（Claim 时读取） |
| `GLAMA.md` | Admin 页 Build steps / CMD arguments / env schema 的逐步口径 |
| `desktop/src/core/mcp_runtime.py` | 12 个工具的 TDQS 定义面：title + 四项 annotations + 逐字段 outputSchema |

这些文件必须在 GitHub 默认分支上 Glama 才会构建；本地工作区不会被读取。
