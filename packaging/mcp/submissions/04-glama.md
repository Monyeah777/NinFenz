# 04 · Glama —— 认领/提交文案

> 入口：<https://glama.ai/mcp/servers?query=ninfenz> （先搜；有条目就 Claim，没有就提交仓库地址）

**仓库地址（填这一条即可）**：<https://github.com/Monyeah777/NinFenz>

**若需要描述**：

**名称 / Name**：NinFenz Content Gate
**一句话 / One-liner（EN）**：Read-only MCP server for a content contract layer: protocol, modules, pipelines, assets, library.
**一句话 / One-liner（ZH）**：给任何 AI agent 一个可校验的内容规范与资产底座——先查契约，再落笔。
**描述 / Description**：只读 MCP 服务器：把长内容的验收标准（协议 / 模块 / 管线 / 资产 / 馆藏）变成 agent 可调用的检索与取件工具面。12 个只读工具 + 1 个 prompt（assemble_guide）；支持 modern 2026-07-28 与 legacy 2025-11-25 双协议；零第三方依赖（Python 标准库）；无写路径。
**仓库 / Repo**：<https://github.com/Monyeah777/NinFenz>
**站点 / Site**：<https://ninfenz.dev/>
**安装 / Install**：`npx -y ninfenz serve`
**类目 / Category**：content-creation（备选 developer-tools / knowledge-management）
**标签 / Tags**：mcp, content-contract, spec-driven, verification, knowledge-base, python, llm
**许可 / License**：MIT
**图标 / Icon**：packaging/mcp/assets/icon-400.png（400×400 PNG）

## 仓库侧已备（2026-10-18）

| 文件 | 作用 |
| --- | --- |
| `Dockerfile` | Glama 构建 + stdio 启动（非 root、无 pip install、`CMD` = `python scripts/nf.py serve`） |
| `glama.json` | 主张维护者 `Monyeah777`（Claim 时读取） |
| `GLAMA.md` | Admin 页 Build steps / CMD arguments / env schema 的逐步口径 |
| `desktop/src/core/mcp_runtime.py` | 12 个工具的 TDQS 定义面：title + 四项 annotations + 逐字段 outputSchema |

这些文件必须在 GitHub 默认分支上 Glama 才会构建；本地工作区不会被读取。
