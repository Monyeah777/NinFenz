# NF 接入面（integrations）

> 本目录是 NF **接入面**的机检真源：每个接入面一个子目录 + `integration.json`（字段与词表见 `protocol/schema/integration.schema.json`）。
> 下表为生成区，由 `core/integrations.py::render_index` 渲染；check38 的 `integrations` 子扫描**逐字对账**（手改即红）。

<!-- nf:integrations:begin -->
| id | 面 | 类型 | 状态 | 版本 | 责任方 | 入口 | 文档 |
|---|---|---|---|---|---|---|---|
| a2a-card | A2A Agent Card 出口 | export | proposed | 0.1.0 | @Monyeah777 | results/interop/a2a.json | docs/interop-thirdparty.md |
| agent-skill | Agent Skill 出口 | package | active | 1.0.0 | @Monyeah777 | skills/ninfenz/SKILL.md | skills/ninfenz/SKILL.md |
| agents-rules | 项目规则出口（AGENTS / CLAUDE） | export | active | 1.0.0 | @Monyeah777 | python scripts/nf.py run --fmt agents | docs/agent/agent_组装指令包_v0.2.md |
| ccv3-export | CCV3 角色卡出口 | export | active | 1.0.0 | @Monyeah777 | python scripts/nf.py run --fmt ccv3 | docs/output-forms.md |
| cli | 命令行入口（nf） | cli | active | 1.0.0 | @Monyeah777 | python scripts/nf.py --help | docs/terminal.md |
| dotnet-engine | .NET 引擎线（Nf.Engine） | library | active | 1.0.0 | @Monyeah777 | dotnet build engine/dotnet/src/Nf.Engine/Nf.Engine.csproj | engine/dotnet/README.md |
| library-raw | 云图书馆 raw 取件面 | collection | active | 1.0.0 | @Monyeah777 | library/INDEX.md | docs/agent/ROUTES.md |
| lsp | 编辑器接入（nf lsp） | editor | active | 2.7.0 | @Monyeah777 | python scripts/nf.py lsp | docs/lsp.md |
| mcp | MCP 服务面（nf serve） | server | active | 1.4.0 | @Monyeah777 | python scripts/nf.py serve | docs/mcp.md |
| npm-launcher | npm 一键启动器 | package | active | 1.0.0 | @Monyeah777 | npx ninfenz | packaging/npm/README.md |
| rust-fastlane | Rust 只读快线（nf-rs） | cli | active | 1.0.0 | @Monyeah777 | cargo run --release --manifest-path engine/rust/Cargo.toml | engine/rust/README.md |
| site | 文档站点（人 + 机器入口） | export | proposed | 1.1.0 | @Monyeah777 | site/index.html | site/README.md |
| tui | 终端 TUI（tui/nf.py） | cli | active | 1.0.0 | @Monyeah777 | python tui/nf.py --selftest | tui/README.md |
| wasm-plugin | 微内核 wasm 插件面（P5） | library | active | 0.1.0 | @Monyeah777 | python scripts/plugin_promote.py --json | engine/wasm/README.md |
<!-- nf:integrations:end -->

## 字段口径

| 字段 | 含义 |
|---|---|
| `kind` | `server` / `client` / `cli` / `library` / `editor` / `package` / `export` / `collection`（封闭词表） |
| `status` | `active` / `proposed` / `deprecated`（封闭词表；`proposed` 表示契约在场、本体未实现） |
| `tier` | `core` / `community`（分层目录：官方核心面 vs 社区面） |
| `version` | SemVer（该接入面自己的版本，不随仓库版本漂） |
| `codeowner` | 责任方（与 Home Assistant manifest 的 `codeowners` 同义） |
| `requires` | 运行时/工具链前置（自由字符串，如 `python>=3.11`） |
| `entry` | 可跑入口（`command`）或路径锚（`path`）——判据要求其引用的件**真实在场** |
| `docs` / `evidence` | 人读文档与实现证据件；任一路径不在场即 FAIL |

## 边界（不宣称）

- 本目录只声明**接入面与入口**，不声明其外部互操作已通过实测（外部实测线封存，见 `results/docs_external-validation-v2.7.md`）。
- `status=active` 表示「件在场且判据绿」，不等于「已被外部客户端装载验证过」。

> **复核（2026-11-14）**：生成区、字段口径与「不宣称」边界**复核不变**；补「§现状对照」把可核规模与词表使用情况写清（此前读者只能自己数），并补「§复现与引用口径」。

## 现状对照（2026-11-14 · 以 `core/integrations.py` 与 schema 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 接入面总数 | **14** | `core/integrations.check()` 的 `stats.count`（== 下表行数） |
| 状态分布 | **active 12 · proposed 2**（`site` / `a2a-card`） | 各 `integration.json` 的 `status` |
| 已用 kind | **7 类**：cli / collection / editor / export / library / package / server | 同上，去重 |
| 词表 kind | **8 类**（上列 7 类 + `client`，**当前无接入面使用**） | `protocol/schema/integration.schema.json` 的 `enum` |
| 词表 status | **3 值**：active / proposed / deprecated（`deprecated` 当前未使用） | 同上 |
| 词表 tier | **2 值**：core / community | 同上 |
| 生成/校验 | 生成区由 `render_index()` 渲染；`check()` 返回零缺口；check38 子扫描**逐字对账** | `verify.sh` 的 check38 `integrations` 子扫描 |

> 本表只作「当时 → 现行」导航；数字与词表以 `integration.json` 与 schema 实读为准。

## 复现与引用口径

```text
python -c "import sys;sys.path.insert(0,'desktop/src');from core import integrations as i;print(i.check('.')[0] or 'zero issues')"   # 零缺口自检（check38 同语义）
python -m pytest desktop/tests/test_publish_boundary.py -q   # 公开面边界（若涉及）
```

- **没有** `nf integrations` 子命令：校验入口是 check38 的 `integrations` 子扫描（`bash verify.sh --checks-only` 会跑），别去找不存在的命令。
- 引用本目录时：「接入面与入口声明」≠「外部互操作已实测」——`status=active` 只表示件在场且判据绿。
