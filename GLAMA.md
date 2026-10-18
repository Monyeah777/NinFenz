# Glama 上架一步一步教程（NinFenz Content Gate）

> 更新时间：2026-10-18
> 你现在的页面状态：**Discovery/Profile 33% · TDQS 未评分 · Repository Not Ready · No releases · No tools**
>
> 先用三句话看懂：
>
> 1. **33% 不是 MCP 质量分**，是“资料完整度 / 搜索曝光”分；不挡 A。
> 2. **Quality 现在未评分**，因为 Glama 还没成功构建并启动过这个服务；构建入口是 Dockerfile 页。
> 3. 仓库侧文件已经全部写好并推到 GitHub；剩下 **4 个需要登录 Glama 的按钮**只能由你点
>    （我没有你的 Glama OAuth 会话，无法代点）。下面把每个按钮、每个字段写清楚。

## 0. 你截图里的每一项是什么意思

| 页面文字 | 真实含义 | 现在要不要处理 |
|---|---|---|
| `score 33%` / `TDQS` | 33% 是 **Discovery / Profile completion**；TDQS 是工具定义质量分，**未构建就没有分** | 先不用管 33%，先做构建 |
| `GitHub Badge` | Glama 给的 README 徽章；本仓 README 已加 card + score 徽章 | 已完成 |
| `Repository: Monyeah777/NinFenz` | 关联的 GitHub 仓库；创建后不能改 | 已完成 |
| `Repository Not Ready` | Glama 还没有拿到这个仓库的 commit 数据 | **第 1 步要处理** |
| `Auto-Release` | 每次 GitHub Release 自动构建/发布；没有 Release 时不会做事 | 首次发布后再考虑 |
| `Releases: No releases yet` | 指 **Glama Release**，不是 GitHub Release | 第 4 步创建 |
| `No Glama release` 说明 | Glama 给的官方操作顺序：Claim → Dockerfile 页 → Build → Make Release | 按本文做 |
| `Discovery score 33%` | 资料完整度 + 曝光，不是 Quality | 构建完再做第 7 节 |
| `No recent usage` | 最近 30 天没有工具调用统计 | 可选：用 Try in Browser 产生一次 |
| `No related servers` | 没有填相关服务器 | 可选：第 8 节 |

## 1. 先做这 4 步（大约 5–10 分钟）

> 顺序不能反：**Sync Repository → Dockerfile Build → Make Release → 验收**。

1. **Sync Repository**：Admin → Repository 页点 **Sync repository / Refresh**，等 commit 数据出现。
2. **Dockerfile 页**：选仓库 Dockerfile；Build steps 留空；CMD 填 `["python","scripts/nf.py","serve"]`；
   env schema 填空对象；点 **Deploy**（有的页面叫 **Build**）。
3. 构建测试成功后：点 **Make Release**（或 **Create Release**），版本填 `1.0.1`，发布。
4. 打开 Schema / Score 页验收：应有 10 个工具、1 个 prompt；Quality 开始评分。

如果你只想记一条：**先去 Repository 页点 Sync，再去 Dockerfile 页点 Deploy，成功后再点 Make Release。**

## 2. 第 1 步：Repository Sync（解决 Repository Not Ready）

页面提示原文：

> The repository is linked but commit data is not yet available. This usually resolves
> shortly after adding the server. Please sync the repository from the Repository page and refresh.

操作：

1. 打开 <https://glama.ai/mcp/servers/Monyeah777/NinFenz/admin>。
2. 找 **Repository** 标签（通常在 Admin 页顶部；地址一般是
   <https://glama.ai/mcp/servers/Monyeah777/NinFenz/admin/repository>）。
3. 点 **Sync repository**；如果按钮叫 **Refresh** / **Sync**，点它。
4. 等 1–2 分钟，刷新页面。
5. 期望：`Repository Not Ready` 消失，能看到最新 commit（当前应为 `ebdb54e7` 或更新）。

如果点了 Sync 仍然 Not Ready：

- 等 10–30 分钟再刷新（Glama 的克隆/索引是异步的）；
- 确认 GitHub 仓库是公开的、默认分支是 `main`；
- 再不行就发邮件到 `support@glama.ai`，标题写
  `Repository sync stuck for Monyeah777/NinFenz`，正文附 Listing URL 和当前 commit
  `ebdb54e7e1090bcbe7f9d443460d0458eda1e0ef`。

> 为什么必须先做这步：Glama 后续的 Build/Release 都基于它拿到的 commit 数据；
> commit 数据没同步时，构建可能拿到旧树或直接失败。

## 3. 第 2 步：Dockerfile Admin 页（最关键）

打开：

<https://glama.ai/mcp/servers/Monyeah777/NinFenz/admin/dockerfile>

### 3.1 选择 Dockerfile

优先找 **Use repository Dockerfile** / **Use repo Dockerfile**，选中它。
仓库根已经有最终版：[Dockerfile](Dockerfile)；原始文件：
<https://raw.githubusercontent.com/Monyeah777/NinFenz/main/Dockerfile>。

如果页面只给一个文本框让你粘贴 Dockerfile，就打开上面的 raw 链接，全选复制粘贴。

### 3.2 各字段怎么填

页面字段名可能随 Glama 版本略有差异，按语义对应：

| 字段 | 填什么 | 说明 |
|---|---|---|
| Dockerfile | Use repository Dockerfile | 仓库根已有 |
| Build steps | **留空** | 没有 `pip install`、没有编译；标准库直接跑 |
| CMD arguments | `["python", "scripts/nf.py", "serve"]` | 如果页面是逐行表单，就填三行：`python` / `scripts/nf.py` / `serve` |
| Environment variables schema | `{"type":"object","properties":{},"required":[]}` | 本服务不需要任何环境变量 |
| Placeholder parameters | `{}` | 没有占位参数 |
| Transport | `stdio` | 不是 HTTP / SSE |
| Port | **不填** | 没有端口，没有 `EXPOSE` |
| Auto-Release | 首次先关 | 等第一次 Release 成功后再开 |

> 不要把 `pip install`、`uv`、`mcp-proxy` 写进 CMD。这个镜像就是 Python 标准库的
> stdio 进程；多一层代理只会多一个故障点。

### 3.3 为什么这个 Dockerfile 能过

- 基座 `python:3.11-slim@sha256:e88e9763...`：满足 `requires-python >= 3.11`，且按 digest 钉版
  （仓库 check41 要求）；
- 非 root（UID 10001）；只读仓库文件；
- 只 `COPY` 运行时真正会打开的文件：`scripts/`、`desktop/src/`、03/04/05、`community/`、
  `library/`、`patterns/`、`protocol/`、`docs/`、根 md；
- `PYTHONUTF8=1` / `LANG=C.UTF-8`：中文路径不乱码；
- `CMD ["python", "scripts/nf.py", "serve"]`：exec 形式，stdout 只输出 JSON-RPC；
- 无端口、无出站网络、无 `pip install`。

## 4. 第 3 步：Deploy / Build（构建测试）

填完字段后点页面底部的：

- **Deploy**（Glama 官方博客用的词），或
- **Build**（你的页面文案），或
- **Build & Release**（如果它把两步合并；首次建议分开，先 Build 成功再 Release）。

构建过程会发生什么：

1. Glama 在 Firecracker microVM 里 `docker build`；
2. 启动容器；
3. 发 `initialize` → `tools/list` → `resources/list` → `prompts/list`；
4. 记录工具 schema、annotations、instructions，并计算 TDQS；
5. 结果出现在 Schema 页。

期望结果：

| 项 | 期望 |
|---|---|
| Build 状态 | Success / 绿色 |
| Tools | 10 个：`pipeline_ls` `spec_ls` `registry_query` `library_search` `library_read` `pattern_read` `knowledge_order` `module_read` `pipeline_read` `asset_get` |
| Prompts | 1 个：`assemble_guide` |
| Resources | `nf://repo/...`，首屏 20 条 + `nextCursor` |
| Instructions | 只读内容服务的自述 |
| Capabilities | resources / tools / prompts |

### Build 失败的常见原因

| 日志/现象 | 原因 | 处理 |
|---|---|---|
| 找不到 Dockerfile | Admin 没选 Use repository Dockerfile | 重新选；确认 GitHub 默认分支有 `Dockerfile` |
| COPY 失败 | `.dockerignore` 排除了运行时要读的目录 | 检查 `.dockerignore`；本仓已保留 03/04/05/community/library/patterns/protocol/docs |
| Build 成功但 No tools | CMD 起的是 CLI 而不是 `serve`；stdout 被日志污染 | CMD 必须是 `python scripts/nf.py serve`；启动横幅只允许走 stderr |
| 启动即退出 | CMD 写成了 `nf.py` 的其他子命令 | 改回 `serve` |
| 权限错误 | 非 root 读不到文件 | `COPY --chown=10001:10001` 已处理；确认没有额外挂载/权限覆盖 |
| `useradd: not found` | 极简基座缺 `passwd` | 换数字 `USER 10001:10001`，或安装 `passwd` |
| 自省超时 | 进程没进入 stdio 循环 | 本地用第 6 节四帧复现；stdout 只允许 JSON-RPC |

## 5. 第 4 步：Make Release（创建 Glama Release）

构建测试成功后：

1. 在测试列表里点 **Make Release**；
   如果进了测试详情页，点 **Create Release**。
2. 版本填 **`1.0.1`**（与 `pyproject.toml` 一致）。
3. Changelog 可填：

   ```text
   Read-only MCP server for the NinFenz content contract layer: 10 read-only tools + 1 prompt,
   dual protocol (modern 2026-07-28 + legacy 2025-11-25), stdlib-only, no write path.
   ```

4. 点 **Create & Publish Release**。

如果页面只有 **Build & Release**：

- 点它，Glama 会构建并自动选版本发布；
- 发布后在 Releases 里确认版本是 `1.0.1`，不是别的版本。

发布后：

- `Releases` 不再显示 “No releases yet”；
- Quality / Maintenance 开始评分；
- 用户可以部署这个服务；
- Glama 会对镜像跑安全扫描。

## 6. 验收：确认工具和评分

### 6.1 Schema 页

<https://glama.ai/mcp/servers/Monyeah777/NinFenz/schema>

期望从 “No tools” 变成：

- Tools：10 个（名单见上表）；
- Prompts：1 个；
- Resources：`nf://repo/...`；
- Instructions：有内容；
- Server Configuration：No arguments（本服务不需要 env）。

### 6.2 Score 页

<https://glama.ai/mcp/servers/Monyeah777/NinFenz/score>

- Quality 从 `Not graded` 变成 A/B/C/D；
- 点开每个工具可以看到六维分和 justification；
- 本仓预评估 overall ≈ 4.3–4.4 → **A**。

### 6.3 本地四帧复现（不依赖 Glama）

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"prompts/list"}' \
  | python scripts/nf.py serve
```

期望：`serverInfo.name = nf-repo-live`；`tools` 10 个；`prompts` 1 个。

## 7. 33% 是什么，怎么提高

你看到的 **33%** 是 **Profile completion / Discovery score**，不是 TDQS 质量分。它影响搜索排名，
不影响“能不能拿到 Quality A”。

提高它，按优先级：

1. **Sync Repository**（本教程第 1 步）——commit 数据没有时，资料分上不去。
2. **Build + Release**（第 3–5 步）——没有 Glama Release，资料完整度天然缺一大块。
3. **补全 Profile**：名称、描述、one-liner、分类、标签、License、图标、主页、仓库、
   安装说明、README；本仓的提交文案见第 11 节。
4. **Add related servers**：在 Admin/Related Servers 里加 2–3 个真实相关的服务
   （例如 MCP 规范、内容/知识管理类），不要乱加。
5. **Try in Browser**：在 Listing 页点一次，产生初始 usage；`No recent usage` 会消失。
6. **保持活跃**：后续 commit / GitHub Release 会触发重扫；README 徽章已经加好。

> 33% 不会挡 A；但把上面几项补齐，Discovery 分会明显上去。

## 8. Auto-Release、GitHub Badge、Usage、Related Servers

### Auto-Release

- 含义：每次 GitHub Release 自动构建并发布一个新的 Glama Release。
- 现在没 Release，所以它不会做事；**首次发布成功后再开**。
- 开启后，每次 GitHub Release 记得版本号要递增。

### GitHub Badge

页面会给一段 Markdown；本仓 README 已经放了：

```markdown
[![Glama MCP server](https://glama.ai/mcp/servers/Monyeah777/NinFenz/badges/card.svg)](https://glama.ai/mcp/servers/Monyeah777/NinFenz)
[![Glama quality score](https://glama.ai/mcp/servers/Monyeah777/NinFenz/badges/score.svg)](https://glama.ai/mcp/servers/Monyeah777/NinFenz/score)
```

### No recent usage

- 不是上架阻塞项；`Try in Browser` 或真实用户调用后会出现统计。
- 不要为了数字刷调用；Glama 看的是实际使用。

### No related servers

- 在 Admin → Related Servers（或 Listing 的 Related Servers 页）添加；
- 只加真实相关的，别加不相关的凑数。

## 9. 评分标准与预评估

Glama Listing 三个等级：

| 等级 | 来源 | 本仓现状 |
|---|---|---|
| License | 仓库许可证 | A（MIT） |
| Quality | TDQS 总体分 | 构建后实评；预评估 A |
| Maintenance | 活跃度 / Release / 响应 | Release 后实评 |

Quality 算法（公开 rubric）：

```text
每个工具：25%Purpose + 20%Usage + 20%Behavior + 15%Params + 10%Conciseness + 10%Completeness
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
以 Glama 实评为准。

### 分数偏低时优先改什么

1. **Behavior Transparency**：写 annotations 无法表达的行为（错误 vs 空结果、是否缓存、
   扫描成本、返回上限），不要重复“只读/无网络”。
2. **Parameter Semantics**：参数格式、大小写、默认值、上限、示例；schema 覆盖率已 100%，
   描述补的是“schema 没说的语义”。
3. **Coherence naming**：统一 `<resource>_<verb>`；但改名会破坏兼容性，需单独评估。

## 10. 排障：按你现在的页面文字查

| 页面文字 | 处理 |
|---|---|
| `Repository Not Ready` | 第 1 步 Admin → Repository → Sync；等 10–30 分钟；仍不行邮件 support |
| `score 33%` | 第 7 节的资料完整度清单；不是质量分 |
| `No releases yet` | 第 5 步 Make Release（必须先 Build 成功） |
| `Auto-Release ... hasn't shipped a release` | 同上；首次发布后再开 Auto-Release |
| `No tools` | Build 没跑、CMD 不是 `serve`、或 stdout 混入日志；看第 4 节 |
| `No recent usage` | 可选：Try in Browser |
| `No related servers` | 可选：第 8 节 |
| `TDQS` 未评分 | 构建成功并 Release 后自动评分 |

## 11. 提交文案（可直接粘贴）

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

## 12. 我已经做完的 vs 你只需要点的

### 仓库侧（已完成并推到 GitHub `main`）

- 根 `Dockerfile`：非 root、digest 钉版、stdio、零 pip；
- `glama.json`：维护者 `Monyeah777`；
- `GLAMA.md`：本教程；
- `desktop/src/core/mcp_runtime.py`：10 工具 title / 四项 annotations / outputSchema /
  structuredContent / TDQS 描述；
- `.dockerignore`、README 徽章、`docs/mcp.md` 容器节、英文/日文译件、conformance 报告。

### Glama 侧（需要你登录后点）

| 操作 | 在哪 |
|---|---|
| Sync repository | Admin → Repository |
| Build / Deploy | Admin → Dockerfile |
| Make Release / Create Release | Build 成功后的测试列表 |
| 补 Profile / Related Servers / Try in Browser | Admin / Listing 页 |

> 我没有你的 Glama OAuth 登录态，无法替你点这四个按钮；所有需要填的值都在上面。

## 13. 对 Glama Coherence 4.3 的逐条答复

Glama 当前实评（2026-10-18）：**descriptionQuality 4.5 · coherence 4.3 · overall 4.4 → A**。
coherence 的四条反馈与处理如下：

| 反馈 | 处理 |
|---|---|
| 多数工具针对明显不同的资源；描述交叉引用替代方案 | 保留；每个工具都写明“何时用 / 何时改用哪个工具” |
| `spec_ls` 与 `registry_query` 的协议包元数据轻微重叠 | `spec_ls` 描述已明确为**权威协议包目录**；`registry_query` 明确为**模块查询**，协议命中只是 secondary lookup。行为不变（跨语言契约，避免 Rust/.NET 双实现漂移） |
| `pipeline_ls` / `pipeline_read` 是标准列表/读取对，但可能混淆 | `pipeline_ls` 只返回 path/title 元数据；`pipeline_read` 返回全文；两者描述互相指向 |
| 命名基本一致，但 `asset_get` 用 `_get`，其他读取用 `_read` | `asset_get` 是核心协议**资产五接口**的规范名（`asset_get/query/match/roll/register`），MCP 工具直接沿用；`title` 写为 “Read asset”。改名会同时破坏 Python/Rust/.NET 三套实现和 189 处协议/内容引用，收益仅 naming 一档，故保留并在描述里说明 |
| 模式/资产没有独立 list 工具，枚举依赖 `resources/list` | 这是**有意的两段式**：`resources/list type=pattern|asset` 负责枚举，`pattern_read` / `asset_get` 负责取正文；描述已写明“canonical enumeration path”，避免 agent 找不到枚举路径 |

> 结论：overall 4.4 已经是 A；上述描述边界修改会在 Glama 下次重建后重新评分，
> 主要提升 disambiguation / completeness，naming 仍可能停在 4。若一定要把 naming 推到 5，
> 需要单独做一次跨语言 API 迁移（Python + Rust + .NET + 协议表 + 文档），不建议在 A 已达成时做。

## 附录：官方参考

- Listing：<https://glama.ai/mcp/servers/Monyeah777/NinFenz>
- Score：<https://glama.ai/mcp/servers/Monyeah777/NinFenz/score>
- Schema：<https://glama.ai/mcp/servers/Monyeah777/NinFenz/schema>
- Dockerfile 管理页：<https://glama.ai/mcp/servers/Monyeah777/NinFenz/admin/dockerfile>
- Glama 发布教程：<https://glama.ai/blog/2026-03-15-how-to-make-a-release>
- Glama 索引方法：<https://glama.ai/mcp/methodology>
- TDQS 规范：<https://github.com/glama-ai/tool-definition-quality-score>
- `glama.json` 说明：<https://glama.ai/blog/2025-07-08-what-is-glamajson>
