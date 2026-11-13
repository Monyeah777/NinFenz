# 服务端点契约（endpoint）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13

## 是什么

`protocol/endpoint_contract.json` 把 NF **已实现**的能力声明成 HTTP 面（机制借鉴
microsoft/ai-chat-protocol 的 API 规格）：`status: proposed`——**服务本体未实现**，本契约只固定形状。

> **复核（2026-11-13）**：契约形状 / 幂等声明 / 边界**复核不变**；补现状数字：**11 个端点**
> （8 个远端 `proposed` + 3 个 `local.*` 已实装，见 [local-api-v0.md](ccos/local-api-v0.md)）、
> **6 条 conventions**（`encoding/errors/streaming/versioning/deprecation/idempotency`）、
> **1 条幂等例外**（`bench.evaluate`，`mode=non-idempotent`、`key=required`）、
> **1 个 SSE 端点**（`assemble.plan`）。见「§现状对照」。

## 怎么用

```bash
python scripts/nf.py endpoint
python scripts/nf.py endpoint --json
```

## 判据（可证，防"纸面能力"）

每个端点的 `maps_to` 必须解析为**当下真实存在**的 CLI 子命令（在 `scripts/nf.py` 的
subparser 注册表内）或 MCP 工具（在 `mcp_runtime.TOOL_DEFS` 内）；`method`/`status` 在词表内；
`streaming: true` 的端点必须声明 SSE 约定；`id` 与 `method+path` 唯一。

## 幂等声明（RFC 9110 §9.2.2）

契约**默认 idempotent**——同请求重放须得同结果且无副作用；例外只在顶层
`idempotency_exceptions` 登记（每条给 `mode` / `key` / `why`）：非幂等端点（如
`bench.evaluate` 会落评测记录）`key=required` 时客户端 MUST 带幂等键、服务端 MUST 据此去重。
判据：例外 id 须在契约内、`mode` 与 `key` 在词表内、`why` 非空、要求幂等键时
`conventions.idempotency` 必须在场。派生面同步标注：`nf interop --kind openapi` 的每个
operation 带 `x-nf-idempotency`。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 本文声明 | 复核结果（读到本行时请重跑） |
|---|---|---|
| 端点总数 | 未写 | **11**（8 远端 proposed + 3 `local.*` 已实装） |
| 顶层状态 | `proposed`（服务未实现） | **不变**（远端面仍是形状声明；本地面另见 local-api-v0） |
| conventions | 未计数 | **6 条**（`encoding/errors/streaming/versioning/deprecation/idempotency`） |
| 幂等例外 | `bench.evaluate` 等 | **恰好 1 条**（`non-idempotent` / `required`） |
| SSE | `streaming: true` 须声明 | **1 个**（`assemble.plan`） |
| 派生面 | openapi 带 `x-nf-idempotency` | **不变**（`core/interop_export.py` 逐 operation 写入） |
| 判据位置 | 未写 | **`test_governance_faces`**（契约面）+ `interop` 导出测试 |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/nf.py endpoint            # 人读表（方法 / 路径 / SSE / 映射）
python scripts/nf.py endpoint --json     # 机读契约全文
python -m pytest desktop/tests/test_governance_faces.py -q
```

- 引用本文时：「契约存在 ≠ 服务存在」= 长期口径；真正实现服务时把 `status` 改成 `implemented` 并补实测记录。
- 端点数量与幂等例外以 `protocol/endpoint_contract.json` 实读为准，不以本文表格为准。

## 边界

契约存在 ≠ 服务存在。真正实现服务时把 `status` 改成 `implemented` 并补实测记录；此前不得对外宣称有服务。

本地 HTTP 面（本机回环、已实装）是**另一件**：`nf serve --http` 的三个 `local.*` 端点，
见 [docs/ccos/local-api-v0.md](ccos/local-api-v0.md)。本契约其余端点仍是远端面的形状声明。
