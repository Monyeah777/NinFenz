# NinFenz Content Gate · 三个目录的提交教程

> 目标：把 **NinFenz Content Gate** 提交到
> 1. **GitHub 官方 MCP Registry**（`registry.modelcontextprotocol.io`）
> 2. **Awesome MCP Servers**（`punkpeye/awesome-mcp-servers`）
> 3. **AgentSkillsHub**（`agentskillshub.dev`）
>
> 本文件只做这三站；其它目录见 [DIRECTORIES.md](DIRECTORIES.md)。
> 最后更新：2026-10-19

---

## 0. 先看当前状态（避免重复提交）

| 项目 | 当前值 |
|---|---|
| 官方 Registry 名称 | `io.github.Monyeah777/ninfenz` |
| 当前仓库发布版本 | **1.1.0（`packaging/mcp/server.json`）** |
| npm 包 | `ninfenz@1.1.0`，包内已有 `mcpName` |
| 展示名 | **NinFenz Content Gate** |
| 工具面 | **12 个只读工具 + 1 个 prompt**，无写路径 |
| 安装（零安装） | `npx -y ninfenz serve` |
| 安装（有检出） | `python scripts/nf.py serve` |
| 仓库 | https://github.com/Monyeah777/NinFenz |
| 站点 | https://ninfenz.dev/ |
| 许可 | AGPL-3.0-only 或商业（协议文本 CC BY 4.0） |

**先判断你要做哪一种：**

- **只是让目录里有这个 server**：先查询 Registry 当前版本；若已是 `1.1.0`，直接做第 2、3 节，否则先按 1.8 发布当前版本。
- **要让 Registry / npm 用户拿到最新代码**：需要先发新的 npm 版本（例如 `1.0.2`），再更新 `server.json` 并重新 `mcp-publisher publish`；见 1.8。
- **三站都没有提交过**：按第 1 → 2 → 3 节顺序做。

---

## 1. GitHub 官方 MCP Registry

官方文档：

- Quickstart：https://modelcontextprotocol.io/registry/quickstart
- 认证：https://modelcontextprotocol.io/registry/authentication
- Registry：https://registry.modelcontextprotocol.io/

> Registry 目前是 **preview**，可能发生 breaking change 或数据重置；以官方文档为准。

### 1.1 它是怎么校验的

Registry **只存元数据，不存包**。它要求：

1. npm 包里必须有 `mcpName`，且值等于 `server.json` 的 `name`；
2. `server.json` 的 `version` 与 `packages[0].version` 必须等于**已发布的 npm 版本**；
3. GitHub 登录时，`name` 必须是 `io.github.<你的 GitHub 用户名>/<服务名>` 形式。

本仓已经满足：

```json
// packaging/npm/package.json（节选）
{
  "name": "ninfenz",
  "version": "1.1.0",
  "mcpName": "io.github.Monyeah777/ninfenz"
}
```

```json
// packaging/mcp/server.json（节选）
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.Monyeah777/ninfenz",
  "version": "1.1.0",
  "packages": [
    {
      "registryType": "npm",
      "identifier": "ninfenz",
      "version": "1.1.0",
      "transport": { "type": "stdio" }
    }
  ]
}
```

三处版本必须**同值**。历史坑：只改 `server.json`、不改 npm 包，Registry 会去查旧版本并报
`missing 'mcpName' field`。

### 1.2 Windows 安装 `mcp-publisher`

官方 PowerShell 写法：

```powershell
$arch = if ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq "Arm64") { "arm64" } else { "amd64" }
Invoke-WebRequest -Uri "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_windows_$arch.tar.gz" -OutFile "mcp-publisher.tar.gz"
tar xf mcp-publisher.tar.gz mcp-publisher.exe
```

把 `mcp-publisher.exe` 放到一个 PATH 目录，或直接在当前目录用 `.\mcp-publisher.exe`。验证：

```powershell
.\mcp-publisher.exe --help
```

macOS / Linux / Homebrew 见官方 Quickstart 的 Step 3。

### 1.3 进入 `server.json` 所在目录

```powershell
cd packaging\mcp
```

`mcp-publisher` 默认读取当前目录的 `server.json`。本仓的文件在
[packaging/mcp/server.json](server.json)。

### 1.4 登录（GitHub 设备码）

```powershell
.\mcp-publisher.exe login github
```

终端会打印类似：

```text
To authenticate, please:
1. Go to: https://github.com/login/device
2. Enter code: ABCD-1234
3. Authorize this application
```

在浏览器打开链接、输入设备码、授权。成功后终端显示：

```text
Successfully authenticated!
✓ Successfully logged in
```

> 认证方式决定命名空间：GitHub 登录 → `name` 必须以 `io.github.<你的用户名>/` 开头。
> 本仓已与仓库属主 `Monyeah777` 一致。

### 1.5 发布

```powershell
.\mcp-publisher.exe publish
```

成功时类似：

```text
Publishing to https://registry.modelcontextprotocol.io...
✓ Successfully published
✓ Server io.github.Monyeah777/ninfenz version 1.1.0
```

### 1.6 验证

```powershell
curl.exe -sS "https://registry.modelcontextprotocol.io/v0.1/servers?search=NinFenz"
```

应能看到 `io.github.Monyeah777/ninfenz`、`version`、`packages` 等元数据。
当前仓库发布版本是 `1.1.0`；这条查询应返回当前 Registry 记录的版本，提交前以其实际结果为准。

> 搜索对大小写敏感；用 `NinFenz` 或 `Monyeah777`，不要只搜小写 `ninfenz`（历史上会漏）。

### 1.7 常见错误

| 报错 | 原因 | 处理 |
|---|---|---|
| `missing 'mcpName' field` | npm 包没有 `mcpName`，或 Registry 查的是旧版本 | 确认 npm 包里 `mcpName` 存在，且 `server.json` 版本 = npm 已发布版本 |
| `Registry validation failed for package` | 包类型/版本/字段不合法 | 对照官方 `server.json` schema，先确认 npm 包已发布 |
| `You do not have permission to publish this server` | 登录账号与 `io.github.<user>` 不匹配 | 用仓库属主 GitHub 账号登录，或改 `name` |
| `Invalid or expired Registry JWT token` | 登录过期 | 重新 `login github` |
| 发布成功但搜不到 | 搜索词大小写 / 传播延迟 | 用 `search=NinFenz`，等几分钟再查 |

### 1.8 发布新版本（需要最新代码时）

只有当你希望 Registry 指向**新的 npm 包**时才做这一节。

1. 同步改三处版本（示例 `1.0.2`）：
   - `packaging/npm/package.json` → `version`
   - `packaging/mcp/server.json` → `version`
   - `packaging/mcp/server.json` → `packages[0].version`
2. 发布 npm：
   - 推荐走仓库的 `npm-publish` workflow（带 provenance）；
   - 或本地 `cd packaging/npm && npm publish --access public`。
3. 确认 npm 已生效：

   ```powershell
   npm view ninfenz version
   ```

4. 回到 `packaging/mcp`，重新 `mcp-publisher publish`。
5. 用 1.6 的查询确认新版本。

> 版本号必须严格递增；不要用同一个版本重复 publish。

---

## 2. Awesome MCP Servers

仓库：https://github.com/punkpeye/awesome-mcp-servers
投稿规则：https://github.com/punkpeye/awesome-mcp-servers/blob/main/CONTRIBUTING.md

### 2.1 适合放在哪个分类

选 **Knowledge & Memory**（内容契约、模块、管线、资产、馆藏都属于“可检索的知识底座”）。

如果维护者认为更偏开发工具，备选 **Developer Tools**；不要同时开两个 PR。

### 2.2 准备一整行

当前列表的图例：

- `🐍` Python
- `🏠` Local Service
- `🍎` macOS / `🪟` Windows / `🐧` Linux

复制这一行：

```markdown
- [Monyeah777/NinFenz](https://github.com/Monyeah777/NinFenz) [![Monyeah777/NinFenz MCP server](https://glama.ai/mcp/servers/Monyeah777/NinFenz/badges/score.svg)](https://glama.ai/mcp/servers/Monyeah777/NinFenz) 🐍 🏠 🍎 🪟 🐧 - Content contract layer as a read-only MCP server: protocol specs, modules, pipelines, assets, and the knowledge library for long-form content; 12 read-only tools plus an assembly prompt, Python stdlib only, no write paths.
```

不想带 Glama 徽章也可以删掉中间那段 `[![...]]`，只保留：

```markdown
- [Monyeah777/NinFenz](https://github.com/Monyeah777/NinFenz) 🐍 🏠 🍎 🪟 🐧 - Content contract layer as a read-only MCP server: protocol specs, modules, pipelines, assets, and the knowledge library for long-form content; 12 read-only tools plus an assembly prompt, Python stdlib only, no write paths.
```

### 2.3 网页操作（最省事）

1. 打开 https://github.com/punkpeye/awesome-mcp-servers/edit/main/README.md
2. GitHub 会自动 fork；
3. 在 **Knowledge & Memory** 区找 `N` 段（例如 `NicolasPrimeau/artel` 附近），插入上面那一行；
4. 保持一行一个 server，不要动其它行；
5. `Commit changes` → `Propose changes` → 创建 PR。

分类内的严格字母序不是硬门槛；如果维护者要求，按 `NinFenz` 放到 `N` 段即可。

### 2.4 PR 标题与正文

标题：

```text
Add NinFenz Content Gate MCP server 🤖🤖🤖
```

> `🤖🤖🤖` 是 CONTRIBUTING 里的 **agent PR 快速通道**标记；你是人工提交可省略，用了也不影响内容审核。

正文模板：

```markdown
## What

Adds **NinFenz Content Gate**, a read-only MCP server for a content contract layer:
protocol specs, modules, pipelines, assets, and the knowledge library.

## Why it fits Knowledge & Memory

Agents can discover and retrieve the contract, module, pipeline, asset, and library
records they need before writing long-form content. The server exposes 12 read-only
tools plus one assembly prompt; there are no write paths.

## Verification

- Repo: https://github.com/Monyeah777/NinFenz
- npm: https://www.npmjs.com/package/ninfenz
- Official Registry: `io.github.Monyeah777/ninfenz`
- Install: `npx -y ninfenz serve`
- Python stdlib only; no third-party runtime dependencies
- 12 read-only tools + 1 prompt (`assemble_guide`)
```

### 2.5 提交后

- 等维护者合并；通常几小时到几天；
- 如果要求改分类/措辞，按 review 改，不要新开 PR；
- 合并后打开 README 确认行已出现。

---

## 3. AgentSkillsHub

提交页：https://agentskillshub.dev/submit/

它是**人工审核**的目录；提交免费，但不保证收录，也没有承诺审核时限。

### 3.1 表单怎么填

| 字段 | 填什么 |
|---|---|
| **GitHub Repository URL** | `https://github.com/Monyeah777/NinFenz` |
| **Primary Category** | **Development**（备选：Productivity） |
| **Maintainer Email** | 你能收信的邮箱（只用于审核联系，不必公开） |
| 确认框 | 勾选：仓库公开，且你有权提交 |

表单说明：

- 公开 GitHub 仓库必填；
- Agent Skill 要 `SKILL.md`；**MCP server 只要有解释清楚的 `README.md`**；
- 不要填 API key / secret；
- 提交不等于安全认证。

本仓的 `README.md` 已经包含安装、工具面、协议版本、无写路径说明；不需要额外造 `SKILL.md`。

### 3.2 建议附在备注/描述里的英文块

如果表单有额外说明框，粘贴：

```text
NinFenz Content Gate is a read-only MCP server that exposes a content contract layer
to agents: protocol specs, modules, pipelines, assets, and the knowledge library.

- 12 read-only tools + 1 prompt (assemble_guide)
- stdio; modern 2026-07-28 and legacy 2025-11-25 protocol eras
- Python standard library only; no write paths
- Install: npx -y ninfenz serve
- Repo: https://github.com/Monyeah777/NinFenz
- Site: https://ninfenz.dev/
```

### 3.3 提交后

- 人工审核，通常以天/周计；
- 审核可能要求补 README、安装说明或安全说明；
- 收录后可在站内搜 `NinFenz` / `ninfenz` 复核；
- 如果被拒，先看拒绝理由，不要重复提交同一仓库。

---

## 4. 三站通用材料包（复制即用）

### 4.1 英文一句话

```text
Read-only MCP server for a content contract layer: protocol specs, modules,
pipelines, assets, and the knowledge library.
```

### 4.2 中文一句话

```text
只读 MCP 服务器：把长内容的验收标准（协议 / 模块 / 管线 / 资产 / 馆藏）变成
agent 可调用的检索与取件工具面。
```

### 4.3 英文完整描述

```text
NinFenz Content Gate — a read-only MCP server that exposes a content contract layer
to agents: protocol specs, modules, pipelines, assets, and the knowledge library.

12 read-only tools + 1 prompt (assemble_guide); dual protocol era (modern 2026-07-28 /
legacy 2025-11-25); zero third-party runtime dependencies (Python stdlib); no write paths.

Install: npx -y ninfenz serve
Repo: https://github.com/Monyeah777/NinFenz
Site: https://ninfenz.dev/
```

### 4.4 安装命令

```bash
npx -y ninfenz serve
```

有检出时：

```bash
python scripts/nf.py serve
```

### 4.5 关键链接

| 用途 | 链接 |
|---|---|
| 仓库 | https://github.com/Monyeah777/NinFenz |
| npm | https://www.npmjs.com/package/ninfenz |
| 站点 | https://ninfenz.dev/ |
| 安装说明 | https://github.com/Monyeah777/NinFenz/blob/main/llms-install.md |
| 官方 Registry 查询 | https://registry.modelcontextprotocol.io/v0.1/servers?search=NinFenz |
| Glama | https://glama.ai/mcp/servers/Monyeah777/NinFenz |

---

## 5. 提交前自检

在仓库根跑：

```bash
python -m pytest desktop/tests/test_mcp_packaging.py desktop/tests/test_mcp_runtime.py -q
python scripts/nf.py conformance
```

期望：

```text
MCP tests: passed
conformance: 27/27
```

再确认：

- [ ] npm 包 `ninfenz` 可安装：`npx -y ninfenz serve`
- [ ] `packaging/mcp/server.json` 的版本与 npm 已发布版本一致
- [ ] `package.json` 里有 `mcpName: io.github.Monyeah777/ninfenz`
- [ ] 官方 Registry 查询能搜到 `1.1.0`（若只是更新目录，以查询到的实际版本为准）
- [ ] README / `llms-install.md` 没有过期工具名（当前 12 工具）
- [ ] 不把 API key、token、邮箱密码写进任何提交内容

---

## 6. 推荐执行顺序

```text
1. 官方 Registry（先确认是否已有 1.1.0；不一致时按 1.8 发布当前版本）
2. Awesome MCP Servers（一个 PR，收益最大）
3. AgentSkillsHub（表单，人工审核）
```

三站互不阻塞；官方 Registry 是“机读真源”，Awesome / AgentSkillsHub 是“人找入口”。

---

## 7. 一句话总结

- **官方 Registry**：`mcp-publisher` + GitHub 设备码，`name`/`mcpName`/npm 版本三处同值。
- **Awesome MCP Servers**：README 加一行，分类 Knowledge & Memory，PR 标题可带 `🤖🤖🤖`。
- **AgentSkillsHub**：公开仓库 + README，表单填 Development 分类和维护者邮箱，人工审核。

三份材料都已经在上面的复制块里；剩下的是浏览器登录和点提交。
