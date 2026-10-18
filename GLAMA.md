# Glama 上架详细教程（NinFenz Content Gate）

> 适用对象：仓库维护者。目标是把 GitHub 上的 MCP 服务变成 Glama 可构建、可自省、可评分的
> Listing，并拿到 Quality A。
>
> 相关页面：
> - Listing：<https://glama.ai/mcp/servers/Monyeah777/NinFenz>
> - Score：<https://glama.ai/mcp/servers/Monyeah777/NinFenz/score>
> - Dockerfile 管理页：<https://glama.ai/mcp/servers/Monyeah777/NinFenz/admin/dockerfile>
> - Schema（自省结果）：<https://glama.ai/mcp/servers/Monyeah777/NinFenz/schema>

## 0. 先看清现状（2026-10-18）

| 项 | 状态 | 说明 |
|---|---|---|
| Claim | ✅ 已认领 | 页面显示 `author:claimed` / “claimed by its maintainer” |
| License | ✅ **A** | 仓库根 `LICENSE` 是 MIT；Glama 自动识别 |
| Quality | ⏳ **Not graded** | 还没有成功构建 + 自省，TDQS 没有输入 |
| Maintenance | ⏳ **Not graded** | 还没有 Release |
| Schema 页 | “No tools / 未自省” | 原因同上 |

**根因不是 README，也不是描述文案，而是：Glama 只构建 GitHub 默认分支；默认分支上没有
根 `Dockerfile`，它就无法启动服务、拿不到 `tools/list`，因此 Quality 无法评分。**

本仓已补齐：

| 文件 | 作用 |
|---|---|
| `Dockerfile` | Glama 的构建入口；stdio 启动、非 root、零 `pip install` |
| `glama.json` | 主张维护者 `Monyeah777`；Claim 流程读取 |
| `GLAMA.md` | 本教程 |
| `desktop/src/core/mcp_runtime.py` | 10 个工具的 TDQS 定义面 |
| `.dockerignore` | 缩小构建上下文；不破坏 `Dockerfile.crosscheck` |
| `README.md` / `README.en.md` / `README.ja.md` | Glama card / score 徽章 |
| `docs/mcp.md` | MCP 接入 + 容器一节 |
| `protocol/mcp_package.json` | 只读面红线：10 工具 + 1 prompt，和运行时逐名一致 |

> 关键纪律：Glama 不读本地工作区。所有文件必须先在 GitHub 默认分支上。

## 1. 前置条件

1. 对 `github.com/Monyeah777/NinFenz` 有 write/admin 权限。
2. 用该 GitHub 账号登录 Glama（OAuth）。
3. 确认默认分支是 `main`（本仓是）。
4. 本地可选：装 Docker，用于在推送前复现 Glama 的构建/启动；不装也能用
   `python scripts/nf.py serve` 做协议级自检。

## 2. 本地先过一遍（推送前）

### 2.1 仓库自检

```bash
python scripts/nf.py doctor
python scripts/nf.py stats --check
```

MCP 相关单测（不需要 Docker）：

```bash
python -m pytest \
  desktop/tests/test_mcp_runtime.py \
  desktop/tests/test_mcp_packaging.py \
  desktop/tests/test_mcp_live_e2e.py \
  desktop/tests/test_serve_default.py \
  desktop/tests/test_mcp_trust_meta.py \
  desktop/tests/test_mcp_write_freedom.py \
  -q
```

### 2.2 协议级冒烟（最接近 Glama 的自省）

不装 Docker 也能跑。直接向 stdin 喂四帧：

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"prompts/list"}' \
  | python scripts/nf.py serve
```

期望（stdout 只有 JSON-RPC，启动横幅在 stderr）：

- 第 1 帧：`serverInfo.name = nf-repo-live`；`instructions` 有内容；
- 第 2 帧：`tools` 10 个，每个都有 `title` / `annotations` / `inputSchema` / `outputSchema`；
- 第 3 帧：`prompts` 1 个，`assemble_guide`。

### 2.3 Docker 冒烟（有 Docker 时）

```bash
docker build -t ninfenz-glama .
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"resources/list"}' \
  | docker run --rm -i ninfenz-glama
```

`docker build` 应很快完成：镜像没有 `pip install`、没有编译，只 `COPY` 只读面文件。

## 3. Claim（认领）

Listing 已经认领；本节用于新环境或重新主张时。

1. 用维护者 GitHub 账号登录 <https://glama.ai>。
2. 打开 <https://glama.ai/mcp/servers?query=ninfenz>。
3. 有条目就点 **Claim**；没有就提交仓库地址 `https://github.com/Monyeah777/NinFenz`。
4. 仓库根必须有 `glama.json`：

   ```json
   {
     "$schema": "https://glama.ai/mcp/schemas/server.json",
     "maintainers": ["Monyeah777"]
   }
   ```

5. 改了 `glama.json` 后要**重新走一次 Claim**，Glama 才会重新读取。
6. 个人账号下的仓库通常可以直接用 GitHub OAuth 关联；组织仓库必须用 `glama.json`。

## 4. Dockerfile 管理页（最关键的一步）

打开 <https://glama.ai/mcp/servers/Monyeah777/NinFenz/admin/dockerfile>。

页面字段的名称可能随 Glama 版本变化，按语义对应即可：

| 字段 | 填什么 |
|---|---|
| Dockerfile | 优先选 **Use repository Dockerfile**；仓库根已有 `Dockerfile` |
| Build steps | **留空**。没有 `pip install` / 编译步骤；标准库即可运行 |
| CMD arguments | `["python", "scripts/nf.py", "serve"]` |
| Environment variables schema | `{"type":"object","properties":{},"required":[]}` |
| Placeholder parameters | `{}` |
| Transport | `stdio` |
| Port | **不要填**；没有 HTTP 监听 / 没有 `EXPOSE` |

若页面只让填“命令参数”的逐行表单，就填：

```text
python
scripts/nf.py
serve
```

**不要把 `mcp-proxy` / `uv` / `pip install` 写进 CMD。** 本服务就是 Python 标准库的 stdio
进程；多一层代理只会多一个故障点。

### Dockerfile 设计要点（为什么这样写）

- `FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534c5767af9ea65f6ce`：
  满足 `requires-python >= 3.11`，镜像小；基座按 digest 钉（与 `Dockerfile.crosscheck` 同一
  `PY_BASE`，check41 要求）。
- 非 root（UID 10001）：服务只读仓库文件，不需要 root。
- 显式 `COPY` 而不是 `COPY . .`：镜像只带 `scripts/`、`desktop/src/`、03/04/05、
  `community/`、`library/`、`patterns/`、`protocol/`、`docs/`、根 md；
  构建上下文小，运行时契约可审计。
- `ENV PYTHONUTF8=1 / LANG=C.UTF-8`：仓库路径与标题含中文，固定 UTF-8。
- `PYTHONDONTWRITEBYTECODE=1`：只读文件系统下不写 `__pycache__`。
- `CMD ["python", "scripts/nf.py", "serve"]`：exec 形式，stdout 只输出 JSON-RPC；
  `serve` 默认走**实时仓库面**，不需要先产快照。
- 没有 `EXPOSE`、没有入口 HTTP 服务、没有出站网络。

## 5. 触发构建与自省

在 Admin 页保存 Dockerfile 配置后，Glama 会：

1. 克隆默认分支；
2. 在 Firecracker microVM 里 `docker build`；
3. 启动容器，走 stdio；
4. 依次发 `initialize`、`tools/list`、`resources/list`、`prompts/list`；
5. 记录 schema、annotations、instructions，并计算 TDQS。

构建成功后，Schema 页应从 “No tools” 变成：

| 项 | 期望 |
|---|---|
| Tools | 10 个：`pipeline_ls` `spec_ls` `registry_query` `library_search` `library_read` `pattern_read` `knowledge_order` `module_read` `pipeline_read` `asset_get` |
| Prompts | 1 个：`assemble_guide` |
| Resources | `nf://repo/...` 实时资源，首屏 20 条 + `nextCursor` |
| Instructions | 只读内容服务的自述（英文 + 中文） |
| Capabilities | resources / tools / prompts |

### 常见失败与定位

| 现象 | 常见原因 | 处理 |
|---|---|---|
| Build 失败 | 根目录没有 `Dockerfile`；COPY 路径写错；基础镜像拉取失败 | 确认默认分支有 `Dockerfile`；逐个核对 `COPY` 源路径存在 |
| Build 成功但 “No tools” | CMD 起的是 CLI 而不是 `serve`；stdout 被启动日志污染 | CMD 必须是 `python scripts/nf.py serve`；启动横幅只能走 stderr |
| 自省超时 | 进程没进入 stdio 循环；等 stdin 时被别的输出阻塞 | 本地用 2.2 的四帧冒烟复现；stdout 只允许 JSON-RPC |
| 工具数不对 | 改过 `TOOL_DEFS` 但没同步 `protocol/mcp_package.json` | 跑 `test_mcp_packaging` / `test_declared_tools_match_handlers` |
| `module_read` 的 `has_machine_contract` 为 false | 镜像没装 PyYAML（本仓有意保持 stdlib-only） | 这是已知降级：正文仍完整返回；要该字段为 true 可在 Dockerfile 加 `pip install pyyaml==6.0.3`，代价是构建期网络依赖 |
| 权限错误 | 容器以非 root 运行，但文件不可读 | `COPY --chown=10001:10001` 已处理；确认 `.dockerignore` 没排除运行时要读的目录 |
| `useradd: not found` | 极简基础镜像缺 `passwd` | 改用数字 `USER 10001:10001`，或安装 `passwd` |

## 6. Make Release

构建测试通过后：

1. 点 **Make Release**。
2. 版本用当前包版本：`1.0.1`（见 `pyproject.toml`）。
3. 发布说明写清楚：只读 MCP 服务、10 工具 + 1 prompt、modern/legacy 双协议、零依赖。
4. 发布。

**Release 之前 Quality / Maintenance 显示 Not graded 是正常的。** 发布后 Glama 才会把
TDQS 结果和维保状态挂到 Listing 上。

## 7. 评分标准与预评估

Glama Listing 上有三个独立等级：

| 等级 | 来源 | 本仓现状 |
|---|---|---|
| License | 仓库许可证 | A（MIT） |
| Quality | TDQS 总体分 | 待构建后实评；预评估 A |
| Maintenance | 仓库活跃度 / Release / 响应 | 待 Release 后实评 |

Quality 的算法（公开 rubric）：

```text
每个工具：TDQS = 25%Purpose + 20%Usage + 20%Behavior + 15%Params + 10%Conciseness + 10%Completeness
descriptionQuality = 0.6 × mean(TDQS) + 0.4 × min(TDQS)
coherence = (disambiguation + naming + toolCount + completeness) / 4
overall = 0.7 × descriptionQuality + 0.3 × coherence
A ≥ 3.5，B ≥ 3.0，C ≥ 2.0，D ≥ 1.0
```

本仓 10 个工具的人工预评估：

| 工具 | Purpose 25% | Usage 20% | Behavior 20% | Params 15% | Conciseness 10% | Completeness 10% | 估算 TDQS |
|---|---|---|---|---|---|---|---|
| pipeline_ls | 5 | 5 | 4 | 4 | 4 | 4 | 4.5 |
| spec_ls | 5 | 5 | 4 | 4 | 4 | 4 | 4.5 |
| registry_query | 5 | 5 | 4 | 4 | 4 | 4 | 4.5 |
| library_search | 5 | 5 | 4 | 4 | 3 | 4 | 4.4 |
| library_read | 5 | 5 | 4 | 4 | 4 | 4 | 4.5 |
| pattern_read | 5 | 5 | 4 | 4 | 4 | 4 | 4.5 |
| knowledge_order | 4 | 5 | 4 | 4 | 4 | 4 | 4.2 |
| module_read | 5 | 5 | 4 | 4 | 4 | 4 | 4.5 |
| pipeline_read | 5 | 5 | 4 | 4 | 4 | 4 | 4.5 |
| asset_get | 5 | 5 | 5 | 4 | 3 | 4 | 4.6 |

估算：descriptionQuality ≈ 4.4（A）；coherence ≈ 4.0–4.5（naming 是唯一弱项：
`*_ls` 与 `read/search/get` 混用）；**overall ≈ 4.3–4.4 → A**（保守下界 ≈ 4.0）。
以上是人工按公开 rubric 的预评估，不是 Glama 官方分；实评以 Score 页面为准。

### 想从 A 再往上推，优先做什么

1. **Behavior Transparency**：描述里写 annotations 无法表达的行为（错误 vs 空结果、
   是否缓存、扫描成本、上限），不要重复“只读/无网络”。
2. **Parameter Semantics**：参数格式、大小写、默认值、上限、示例；schema 覆盖率已 100%，
   描述要补的是“schema 没说的语义”。
3. **Coherence 的 naming**：统一 `<resource>_<verb>` 的 verb（`ls` vs `read/search/get`）；
   但改名会破坏兼容性，需单独评估。
4. **Completeness**：当前通过 `resources/list type=module|asset|pattern` 提供枚举路径；
   若愿意扩工具面，可评估 `module_ls` / `asset_ls`，但要同步 `protocol/mcp_package.json`
   与“10 工具 + 1 prompt”红线。

## 8. 发布后的维护

- 每次向默认分支 push 都会触发 Glama 重新构建/自省/评分；改工具描述就会改 TDQS。
- 保持 `Dockerfile` 在默认分支、保持 `CMD` 可启动；删除/改名会被判为构建失败。
- 版本发布后同步更新 `pyproject.toml` / `CHANGELOG.md`，再在 Glama 做新 Release。
- README 的 Glama 徽章：

  ```markdown
  [![Glama MCP server](https://glama.ai/mcp/servers/Monyeah777/NinFenz/badges/card.svg)](https://glama.ai/mcp/servers/Monyeah777/NinFenz)
  [![Glama quality score](https://glama.ai/mcp/servers/Monyeah777/NinFenz/badges/score.svg)](https://glama.ai/mcp/servers/Monyeah777/NinFenz/score)
  ```

## 9. 提交文案（可直接粘贴）

| 字段 | 值 |
|---|---|
| Name | NinFenz Content Gate |
| One-liner (EN) | Read-only MCP server for a content contract layer: protocol, modules, pipelines, assets, library. |
| One-liner (ZH) | 给任何 AI agent 一个可校验的内容规范与资产底座——先查契约，再落笔。 |
| Description | 只读 MCP 服务器：把长内容的验收标准（协议 / 模块 / 管线 / 资产 / 馆藏）变成 agent 可调用的检索与取件工具面。10 个只读工具 + 1 个 prompt（assemble_guide）；支持 modern 2026-07-28 与 legacy 2025-11-25 双协议；零第三方依赖（Python 标准库）；无写路径。 |
| Repo | https://github.com/Monyeah777/NinFenz |
| Site | https://ninfenz.dev/ |
| Install | `npx -y ninfenz serve`（或容器：`docker build -t ninfenz-glama . && docker run --rm -i ninfenz-glama`） |
| Category | content-creation（备选 developer-tools / knowledge-management） |
| Tags | mcp, content-contract, spec-driven, verification, knowledge-base, python, llm |
| License | MIT |
| Icon | `packaging/mcp/assets/icon-400.png`（400×400 PNG） |

## 10. 排障速查（按症状）

1. **Listing 一直是 Not graded**：先看默认分支有没有 `Dockerfile`；再看 Admin 页有没有
   触发 build；最后看 schema 页是否 “No tools”。
2. **构建成功但 schema 为空**：本地用 2.2 的四帧复现；stdout 混入日志是最常见原因。
3. **工具有缺**：`python -m pytest desktop/tests/test_mcp_packaging.py -q`；
   工具面必须与 `protocol/mcp_package.json` 逐名一致。
4. **分数比预评估低**：打开 Score 页看六维 justification；优先补 Behavior / Params
   两个最容易掉分的维度，不要靠加长描述。
5. **改了描述分数没变**：Glama 按 `inputHash` 增量评分；确认 push 到了默认分支，
   并在 Admin 页重新 build/release。

## 附录 A：Glama 会用到的协议帧

```text
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"glama","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"resources/list"}
{"jsonrpc":"2.0","id":4,"method":"prompts/list"}
```

modern 路径（2026-07-28）也可以：

```text
{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28"}}}
```

## 附录 B：官方参考

- Glama 索引方法：<https://glama.ai/mcp/methodology>
- TDQS 规范与 rubric：<https://github.com/glama-ai/tool-definition-quality-score>
- TDQS 评分说明：<https://glama.ai/blog/2026-04-03-tool-definition-quality-score-tdqs>
- `glama.json` 说明：<https://glama.ai/blog/2025-07-08-what-is-glamajson>
- Glama MCP 目录 API：<https://glama.ai/mcp/reference>
