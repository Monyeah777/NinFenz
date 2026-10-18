# Glama release build（NinFenz Content Gate）

Glama 页面：<https://glama.ai/mcp/servers/Monyeah777/NinFenz>
Score 页面：<https://glama.ai/mcp/servers/Monyeah777/NinFenz/score>
Dockerfile 管理页：<https://glama.ai/mcp/servers/Monyeah777/NinFenz/admin/dockerfile>

仓库侧入口：`Dockerfile`（构建）、`glama.json`（主张维护者 `Monyeah777`；推送后重走一次
Claim 让 Glama 重新读取）、本文件（管理员操作口径）。三者必须在 GitHub 默认分支上，
Glama 只构建远端仓库，不读本地工作区。

## Build spec

仓库根目录已有 `Dockerfile`。若 Admin 页提供 **Use repository Dockerfile**，直接选它；
若要求填 Build steps，留空即可——镜像没有 `pip install` / 编译步骤（运行时只用 Python 标准库）。

CMD arguments：

```json
["python", "scripts/nf.py", "serve"]
```

不要填端口 / `EXPOSE`：传输是 stdio，没有 HTTP 监听。

Environment variables schema：

```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

Placeholder parameters：

```json
{}
```

## Runtime notes

| 项 | 值 |
|---|---|
| Transport | `stdio`（换行分隔 JSON-RPC，UTF-8） |
| Authentication | 无（本地/容器 stdio） |
| Network | 无出站、无入站；只读本仓文件 |
| Entry | `python scripts/nf.py serve`（缺省 = 实时仓库面，无需快照） |
| Protocol | modern `2026-07-28` + legacy `2025-11-25` 双时代 |

## 发布顺序

1. 推送 Dockerfile / glama.json 到 GitHub 默认分支。
2. Glama Admin 页触发 build；构建成功后跑一次 introspection（本文件「Runtime notes」）。
3. 构建测试通过后点 **Make Release**，版本用当前包版本（`1.0.1`）。
4. Release 发布后 Glama 才会给出 Quality / Maintenance 评分；此前显示 Not graded 是正常状态。

本地等价验证（需容器引擎）：

```bash
docker build -t ninfenz-glama .
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"prompts/list"}' \
  | docker run --rm -i ninfenz-glama
```

期望：`initialize` 回 `serverInfo.name = nf-repo-live`；`tools/list` 回 10 个只读工具；
每个工具都有 `title`、四项 `annotations`、`inputSchema`、`outputSchema`
（调用结果同时带 `content` 文本与 `structuredContent`）。

## Quality surface（TDQS）

本仓的工具定义按 Glama 公开的
[Tool Definition Quality Score](https://github.com/glama-ai/tool-definition-quality-score)
重写：一句 purpose（动词 + 资源 + 边界）、when/when-not + 具名替代工具、
`readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` 四项注解、
参数语义（大小写 / 格式 / 默认值 / 上限）、逐字段 `outputSchema`。
改工具描述时请以该 rubric 为验收单，别只改 README。

## TDQS 预评估（人工按 rubric，非 Glama 官方分）

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
`*_ls` 与 `read/search/get` 混用）；overall ≈ **4.3–4.4 → A**（保守下界 ≈ 4.0）。
以上是人工按公开 rubric 的预评估，不是 Glama 官方分；实评以 Score 页面为准。

