# 01 · awesome-mcp-servers —— 要粘的那一行

> 用途：打开 https://github.com/punkpeye/awesome-mcp-servers/edit/main/README.md （会自动 fork），在 **Knowledge & Memory** 分类的 `N` 段插入下面这一行，然后 Commit → Propose changes 建 PR。

## 整行（复制这一整行）

```markdown
- [Monyeah777/NinFenz](https://github.com/Monyeah777/NinFenz) [![Monyeah777/NinFenz MCP server](https://glama.ai/mcp/servers/Monyeah777/NinFenz/badges/score.svg)](https://glama.ai/mcp/servers/Monyeah777/NinFenz) 🐍 🏠 🍎 🪟 🐧 - Content contract layer as a read-only MCP server: protocol specs, modules, pipelines, assets, and the knowledge library for long-form content; 12 read-only tools plus an assembly prompt, Python stdlib only, no write paths.
```

不带 Glama 徽章的版本：

```markdown
- [Monyeah777/NinFenz](https://github.com/Monyeah777/NinFenz) 🐍 🏠 🍎 🪟 🐧 - Content contract layer as a read-only MCP server: protocol specs, modules, pipelines, assets, and the knowledge library for long-form content; 12 read-only tools plus an assembly prompt, Python stdlib only, no write paths.
```

## PR 标题（复制）

```text
Add NinFenz Content Gate MCP server 🤖🤖🤖
```

> 末尾的 `🤖🤖🤖` 是该列表官方 CONTRIBUTING 里的 **agent PR 快速合并通道**标记；人工提交可省略。
> 图例：`🐍` = Python；`🏠` = Local Service；`🍎 🪟 🐧` = macOS / Windows / Linux。


---

## 同源自检（与 §1 材料包一致 · 2026-11-14 复核补）

> 下面 6 项是**唯一真源**（`packaging/mcp/SUBMIT.md §4` / `DIRECTORIES.md §1`）的投影；改材料包必须同步改本文件与其余 `0X-*.md` 提交件。

| 项 | 值 | 出处 |
|---|---|---|
| 展示名 | **NinFenz Content Gate** | 材料包 §1 |
| 仓库 | `https://github.com/Monyeah777/NinFenz` | 同上 |
| 站点 | `https://ninfenz.dev/` | 同上 |
| 安装 | `npx -y ninfenz serve`（零安装）/ `python scripts/nf.py serve`（有检出） | 同上 |
| 工具面 | **12 只读工具 + 1 prompt**，**无写路径** | `desktop/src/core/mcp_runtime.py` |
| 运行期依赖 | **零第三方**（Python 标准库） | `pyproject.toml` 的 `dependencies` 为空 |

- 本文件是**逐字可粘件**：改动上面 6 项时，10 份 `0X-*.md` 必须同批更新，否则目录间描述会互相矛盾。
- 「`🐍`/`🏠`/`🍎🪟🐧` 图例」以 awesome-mcp-servers 的 CONTRIBUTING 为准；图例变更不影响正文。
