# 08 · mcpmarket.com —— 短表单

> 入口：https://mcpmarket.com/ （提交入口在页脚）

**名称 / Name**：NinFenz Content Gate
**一句话 / One-liner（EN）**：Read-only MCP server for a content contract layer: protocol, modules, pipelines, assets, library.
**一句话 / One-liner（ZH）**：给任何 AI agent 一个可校验的内容规范与资产底座——先查契约，再落笔。
**描述 / Description**：只读 MCP 服务器：把长内容的验收标准（协议 / 模块 / 管线 / 资产 / 馆藏）变成 agent 可调用的检索与取件工具面。12 个只读工具 + 1 个 prompt（assemble_guide）；支持 modern 2026-07-28 与 legacy 2025-11-25 双协议；零第三方依赖（Python 标准库）；无写路径。
**仓库 / Repo**：https://github.com/Monyeah777/NinFenz
**站点 / Site**：https://ninfenz.dev/
**安装 / Install**：`npx -y ninfenz serve`
**类目 / Category**：content-creation（备选 developer-tools / knowledge-management）
**标签 / Tags**：mcp, content-contract, spec-driven, verification, knowledge-base, python, llm
**许可 / License**：MIT
**图标 / Icon**：packaging/mcp/assets/icon-400.png（400×400 PNG）


---

## 字段自检（与材料包同源 · 2026-11-14 复核补）

| 字段 | 本文件的值 | 真源 |
|---|---|---|
| 名称 | NinFenz Content Gate | `SUBMIT.md §4` / `DIRECTORIES.md §1` |
| 仓库 | `https://github.com/Monyeah777/NinFenz` | 同上 |
| 站点 | `https://ninfenz.dev/` | 同上 |
| 安装 | `npx -y ninfenz serve` | 同上（零安装路径） |
| 工具面 | 12 只读工具 + 1 prompt（`assemble_guide`），无写路径 | `desktop/src/core/mcp_runtime.py` |
| 依赖 | 零第三方（Python 标准库） | `pyproject.toml` 的 `dependencies` 为空 |
| 图标 | `packaging/mcp/assets/icon-400.png`（**真实 400×400**，读 IHDR） | `assets/README.md` |
| 许可 | MIT | `LICENSE` |

- **短表单族对偶**：本件与 `07-mcpservers-org.md` 的**字段正文逐字相同**（判据 `test_short_form_submission_doc_contract` 会逐行比对）；只有标题与入口不同。改一处必须两处一起改。
- **平台侧未验**：mcpmarket 的提交入口在页脚、字段名以页面为准；收录与否不可从仓库证明。
- **不钉运行时计数**：描述文案不带 check/PASS/单测条数。
- 该站无审核 SLA；提交后不催、不重复投。
