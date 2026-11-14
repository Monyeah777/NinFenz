# 指令档机器面路由（driver override）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13

## 是什么

NF 的指令档（组装指令包 / `docs/agent/AI_ROUTING.md` / `docs/ai-menu.md`）头部现在带 **DRIVER OVERRIDE** 块，
真源是 `protocol/driver.json`：**有 MCP 实现就走 MCP；派发失败即停，禁止回退成文本步骤**
（机制借鉴 ACP：静默降级会把"按机器面取件"偷换成"凭记忆组装"，产物不可复现）。

> **复核（2026-11-13）**：三工作流 / 三指令档 / fail-closed 关键词**复核不变**；修一处**判据过度陈述**：
> 原文写「工具名必须与 `mcp_runtime.TOOL_DEFS` **逐名一致**」——实现是**子集**校验（引用名必须在
> 运行时工具集里存在），并非要求两边集合相等：运行时 **12 个**工具，`bindings` 只绑 **8 个** +
> **1 个**提示；若按「逐名一致」理解，TOOL_DEFS 增多反而会被误判成红。见「§现状对照」。

## 怎么用

```bash
python scripts/nf.py driver                     # 列全部工作流与映射
python scripts/nf.py driver assemble            # 解析某工作流该走哪条路
python scripts/nf.py driver --json
```

## 判据（可证）

`bindings.mcp.tools` 与每个 workflow 引用的工具名必须**存在于** `mcp_runtime.TOOL_DEFS`
（子集校验，非集合相等）；提示名同理须存在于 `PROMPT_DEFS`。每个 workflow 必须有**存在的** fallback 文件；
`documents[]` 里的文档必须带 override 块且写明 fail-closed 关键词（`不得回退` / `停止`）。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 本文声明 | 复核结果（读到本行时请重跑） |
|---|---|---|
| 工作流 | assemble / menu / routing | **3 条**（`driver.json: workflows` 三键） |
| 指令档 | 三份文档带 override 块 | **3 份**（组装指令包 v0.2 / AI_ROUTING / ai-menu），块内均含 `DRIVER OVERRIDE` + 关键词 |
| 工具绑定 | `bindings.mcp.tools` | **8 个**（运行时 `TOOL_DEFS` **12 个**，子集校验） |
| 提示绑定 | `bindings.mcp.prompts` | **1 个**（`PROMPT_DEFS`） |
| 判据语义 | 原写「逐名一致」 | **子集**（引用名存在即可；已改正文） |
| 自检 | `nf driver` 全绿 | **`✓ 工作流映射/工具名/fallback/文档声明块全部一致`** |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/nf.py driver            # 自检（工作流/工具名/fallback/文档块）
python scripts/nf.py driver assemble   # 单个工作流的路由解析
python -m pytest desktop/tests/test_ai_routing_contract.py desktop/tests/test_ai_menu_contract.py -q
```

- 引用本文时：「一旦选 MCP 路线，派发失败即停」= 长期口径；工具名以 `nf driver --json` 与 `TOOL_DEFS` 实读为准。

## 边界

本模块只做**路由声明与自检**，不代替使用者实际派发。语义边界只有一条：
**一旦选了 MCP 路线，派发失败即停（不得回退文本步骤）**；fallback 仅适用于「本工作流无映射」或「本会话未启用 MCP 面」。
