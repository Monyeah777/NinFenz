# 41 波C C8 · MCP transport 扩展评估（streamable HTTP / SSE）

> 范围：在 stdio（当时现状）之外评估 streamable HTTP / SSE 远程装载通道；产出 = 评估文档 + 试点结论（做/不做 + 依据）。

> **状态：2026-09-08 评估快照 + 2026-11-13 结论复评**——原结论「暂不做、回冻结」针对**公网/远程** streamable HTTP 与 SSE，**该结论仍然成立**；但「本地 HTTP 面」已作为独立小步落地（`nf serve --http`，只绑回环、纯读端点 + ingress 策略），不等于本次评估的远程通道（见「结论复评」段）。协议基线原文指向 33_v2.2.0_A5 报告，该计划文档已于 2026-10 移出公开仓（本地归档）；现行协议事实真源 = `docs/mcp.md` + `protocol/endpoint_contract.json`。

## 一、现状与基线

- 现役通道（2026-09-08 口径）：`desktop/src/core/mcp_runtime.py` stdio transport——换行分隔 UTF-8 JSON-RPC，逐行读写，`resources/list` + `resources/read` 只读面（C2 最小安全层：白名单 uri、无 tools/prompts 写路径）。
  > 现行口径（2026-11-13）：默认 `nf serve` = stdio 实时仓库面（无需快照）；只读能力面已扩为 resources + **12 只读 tools** + **1 prompt**（C7 后续）；另有**本地 HTTP 面** `nf serve --http`（127.0.0.1，`GET /api/health` + `POST /api/verify` + `POST /api/check`，纯读、无客户端可控路径）+ ingress 策略（`nf-ingress-policy/1`：token/工具白名单/限流/同意，见 `desktop/src/core/mcp_ingress.py`）。**stdio 仍是默认消费面**；公网/远程 streamable HTTP 与 SSE 仍未实现。
- 协议事实（2025-11-25 schema）：stdio 与 streamable HTTP 均为受支持 transport；streamable HTTP 用 JSON-RPC over HTTP（POST + SSE 响应流），需服务端监听端口。
- 消费方假设：作者本机 agent 会话经 stdio 拉起 `nf serve`；真实远程客户端（Claude Desktop 类）尚未回填 E3 实测。

## 二、扩展差距评估

streamable HTTP / SSE 相比 stdio 的新增面：

| 维度 | 差距 | 说明 |
|---|---|---|
| 服务形态 | 从子进程 stdio 到长驻 HTTP 服务 | 需端口监听、生命周期管理、多会话并发 |
| 安全面 | 网络暴露 | 只读 resources 也需鉴权/白名单/绑定策略；与 C2「只读最小面」叠加后攻击面变大 |
| 能力收益 | 远程装载 | 当前能力表 = resources 只读 + 未来 C7 tools/prompts 只读——远程消费方尚无真实需求回填 |
| 运维 | 部署 | 需托管进程/反代/TLS；基础层零第三方依赖红线内无现成 web 栈 |

## 三、试点结论：暂不做（回冻结）

**结论：不做 streamable HTTP / SSE 试点**，理由：

1. **无消费方**：E3 标准 MCP 客户端实测未回填前，远程 transport 的收益无人消费（按需装配哲学：不产没人消费的东西）。
2. **安全优先**：远程 transport 必须叠加鉴权/白名单/端口治理——在 E3 回填、确有远程装载需求前，网络面引入的风险大于收益。
3. **路径清晰**：stdio 已覆盖作者本机 agent 消费场景；后续如需远程，评估项已列于此文档，可随 E3 回填后重启。

回冻结条件：E3 标准 MCP 客户端实测回填 **且** 出现真实远程装载需求 → 重启本评估并试点 streamable HTTP（先 tools/prompts 只读面，不引入写路径）。

## 结论复评（2026-11-13）

- **原结论仍成立**：本次评估的对象是**公网/远程** streamable HTTP 与 SSE 远程装载通道——两者至今未实现，回冻结条件（E3 回填 + 真实远程需求）仍未满足（E3 状态见 `docs/mcp.md` 状态行，仍为待用户侧回填）。
- **新增的本地 HTTP 面 ≠ 本评估的远程通道**：`nf serve --http` 只绑 **127.0.0.1**、端点纯读（health/verify/check）、引入 `nf-ingress-policy/1` 闸门（token 白名单/工具白名单/限流/同意）；它服务「本机工具调用」而非「远程客户端装载」。故「不做远程 transport 试点」的**风险判断未变**，但第一段「现状」需按现行口径读（见上）。
- **不变的红线**：不引入写路径；不因评估文档过时就把「回环 HTTP 面」误读成「远程通道已开放」。

## 复现与引用口径

```bash
python scripts/nf.py serve --help    # 现行入口：--http（回环）/ --port / --ingress-policy（nf-ingress-policy/1）
```

- 复核现状：`--http` 帮助文本（回环 + 纯读端点）/ `desktop/src/core/mcp_ingress.py`（闸门实现）/ `desktop/tests/test_mcp_ingress.py`（判据）/ `docs/mcp.md`（E3 状态）。
- 引用本文时：**结论 = 不回冻结重启远程 transport**；「现状」段请以现行命令与 `docs/mcp.md` 为准，勿把本文当作现行能力清单。
