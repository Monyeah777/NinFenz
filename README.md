# NinFenz · 文档生成工坊（规范驱动）<sub>Spec-driven documentation workshop</sub>

[![REUSE compliant v3.3](https://img.shields.io/badge/REUSE-compliant%20v3.3-brightgreen)](https://reuse.software/spec/) [![License: AGPL-3.0-only or Commercial](https://img.shields.io/badge/license-AGPL--3.0--only%20%7C%20Commercial-blue)](LICENSING.md)

<!-- nf:locales -->
<p align="center">
  <strong><a href="README.md">简体中文</a></strong> · <a href="README.en.md">English</a> · <a href="README.ja.md">日本语</a>
</p>

<p align="left">
  <a href="https://github.com/Monyeah777/NinFenz/actions/workflows/ci-verify.yml"><img src="https://github.com/Monyeah777/NinFenz/actions/workflows/ci-verify.yml/badge.svg" alt="ci-verify 门禁" height="20"></a>
  <a href="https://glama.ai/mcp/servers/Monyeah777/NinFenz/score"><img src="https://glama.ai/mcp/servers/Monyeah777/NinFenz/badges/score.svg" alt="Glama code quality score AAA" height="20"></a>
  <a href="https://github.com/punkpeye/awesome-mcp-servers"><img src="https://img.shields.io/badge/Awesome_MCP_Servers-listed-2ea44f?logo=github&amp;logoColor=white" alt="已收录于 Awesome MCP Servers" height="20"></a>
</p>

> **唯一官方仓库**：https://github.com/Monyeah777/NinFenz ｜ npm `ninfenz` ｜ GitHub Packages `@monyeah777/ninfenz`
> 其他账号下的同名仓库均为**未经授权的镜像快照**，不代表本项目，也不接受 Issue/PR。

**站点（线上）**：https://ninfenz.dev · 机器入口 [llms.txt](https://raw.githubusercontent.com/Monyeah777/NinFenz/main/llms.txt)

**NF 终端（TUI）演示** —— 全屏人机入口（纯标准库）；菜单与动作是 `nf` CLI 真命令的受控调用方。
键位按顶尖终端约定：`Tab` 切面板、`↑↓` 在当前面板内移动、`/` 过滤、`?` 看键位。

![NF 终端 TUI 演示（框线不依赖读者字体）](site/assets/demo.gif)

<details>
<summary>演示帧文本 —— 与 `--demo` 渲染器逐字一致，便于检索/复制</summary>

```
┌ NF TUI v1.0.0 · NinFenz 内容契约层 ──────────────────────────────────────────────────────────┐
│仓库 NinFenz · 能力区 9                                           焦点 动作 · 就绪（0 项待办）│
├────────────────────────┬─────────────────────────────────────────────────────────────────────┤
│  能力区 1/9            │▍ 动作 · 环境自检（2）                                               │
│▸ 0 环境自检（2）       │❯ 只读体检   nf doctor                                               │
│  1 一键演示世界（1）   │  体检（机器面）                                                     │
│  2 需求 → 装配计划（2）│                                                                     │
│  3 全链生产（2）       ├─────────────────────────────────────────────────────────────────────┤
│  4 校验与体检（4）     │  输出 · 1-3/3 · 已跟随                                              │
│  5 货架与资产（4）     │❯ nf doctor   （退出码 0 · 0.42s）                                   │
│  6 管线与模块（4）     │环境自检：Python 3.11 · 仓库在场 · 模块 13 · 管线 3                  │
│  7 帮助与命令面（2）   │✔ 只读体检通过：无缺件 / 无越界 / 无非确定性输出                     │
│  8 写盘表单（13）      │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
│                        │                                                                     │
├────────────────────────┴─────────────────────────────────────────────────────────────────────┤
│ Tab 切面板 · ↑↓ 移动 · / 过滤 · Enter 运行 · ? 帮助 · q 退出                                 │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

</details>

`python tui/nf.py` 进全屏界面；`--selftest` 跑安全自检，`--demo` 打印上面这帧，`--exec "nf doctor"` 是脚本面
（无 TTY 亦可：`--list-actions --json` 给 agent 列动作与退出码）。命令在后台线程跑，运行中 `Ctrl-C` 只取消该命令；
路径参数过仓库包含性判据、写盘需键入 `yes` 确认、密钥只从环境变量读并遮蔽显示。细节见 `tui/README.md`。

> 双许可（分层）· 代码 AGPL-3.0-only 或商业许可 · 协议文本 CC BY 4.0 · 见 `LICENSING.md`

NF 是内容契约层——定义“AI 稳定产出长内容”的协议、质量与资产标准；协议本身域中立、模型无关。

**别名与检索词**：NF · NinFenz · 宁封子 · 内容契约层（content contract layer）· 规范驱动的内容工厂 · 长内容生成协议 · 装配式内容生产 · 模块/管线/资产 · 质量门禁 · 域包 · MCP 接入。

**不是什么**：不是模型、不是提示词模板集、不是某厂商 SDK——协议本体域中立、模型无关；MCP 只是可对接的连接协议之一。

`bash verify.sh`（当前基线见下方生成区「质量凭证」行） · `python scripts/nf.py --version`

## ⚡ 如果你是 AI / Agent

- 这是什么：规范驱动的文档工厂，装模块/管线/资产 → 校验 → 输出。
- 入口链：`docs/agent/AGENT_START.md`（开工）→ `docs/agent/AI_ROUTING.md`（选线）→ `docs/meta/DEEP_DIVE.md`（懂得深）。
- 机器凭证：`bash verify.sh`（当前基线见下方生成区的「质量凭证」行，由 `nf stats --write` 写入）；机器入口清单见 `llms.txt`；语言面见 `README.en.md` · `README.ja.md`（三面的机读事实与语言切换行由 check34 的语言面扫描断言一致；注册表 = `protocol/locales.json`）。
- 要懂 NF 为什么这样设计：读 [docs/meta/DEEP_DIVE.md](docs/meta/DEEP_DIVE.md)。

## 快速开始

作者/开发者，5 分钟：第一跳照 [`docs/quickstart.md`](docs/quickstart.md) 的 6 步逐条复制粘贴；想一条命令自检用 `bash scripts/quickstart_check.sh`（判据：退出码 0 · 墙钟 ≤ 300 秒 · 文档步数 == 脚本步数）。

1. `bash verify.sh`
2. `python scripts/nf.py shell`（交互终端：端壳退役后的人机入口，见 `docs/terminal.md`）
3. `python scripts/nf.py demo`
4. `python scripts/nf.py --help`
5. `python scripts/nf.py doctor`
6. `python scripts/nf.py completion bash`

> **安全边界（`nf verify` 会执行目标仓库自带的门禁脚本）**：`nf verify` 的引擎会在**本进程内**
> 执行当前仓库 `verify.sh` 里的内嵌 Python（CWE-94 执行面）。故只有**当前运行代码所在的
> 安装根**自动可信；外部仓库即使伪造官方 `origin` 也默认**拒绝执行**（退出码 2 并给修复
> 指引）。确需执行须显式 `nf verify --trust-repo`（风险自担）；fork/镜像可用
> `NF_TRUST_OWNERS` 显式 opt-in。只读体检请用 `bash verify.sh`，或先人工审阅该仓库的
> `verify.sh`。详见 [SECURITY.md](SECURITY.md)。

AI 装配：

1. 读 `docs/agent/AGENT_START.md`
2. 读 `docs/agent/agent_组装指令包_v0.2.md`
3. 按需取 01/02/06/07 与 community 包
4. 组装完整版并过 `##7` 自检
5. `nf assemble "<需求>" --build --dest <目录>`（组装式命令：直接产「完整版」单文件）
6. `nf assemble "<需求>" --check <out.md>`

### 常见问题（FAQ）

- **NF 是什么？** 内容契约层：把「AI 稳定产出长内容」定义成协议 + 质量门 + 资产标准，使产出可装载、可质检、可复现。
- **NF 是 MCP 服务器吗？** 不是必须。协议与资产都是纯文本，克隆或直链即可装载；`nf serve` 才额外提供 MCP 接入面。
- **支持哪些模型？** 模型无关：任何能读文本的 AI 都能按协议装配与装载，不绑定某家模型或某个连接协议。
- **必须联网吗？** 不必。仓库本身就是 markdown 源件；`bash verify.sh` 只读本地，可离线跑。
- **产出怎么判合格？** 判据只来自内部链：verify 门禁（静态可核）+ 五维纵深自评 + 真实战例；外部评价不作为质量背书。
- **怎么引用？** 代码层 AGPL-3.0-only（或商业许可），协议文本 CC BY 4.0；引用请注明来源，边界见 `LICENSING.md`，机读元数据见 `CITATION.cff`。
- **出口与合规？** 密码学只走标准库 + 外部 `ssh-keygen`（不自制算法）；出口管制读法见 `docs/EXPORT.md`。

## 能力与资产

<!-- nf:stats:begin -->
**官方核心**：13 模块 · 3 管线（P00 / P01 / P90） · 核心协议件 01–07
**社区规模**：111 登记包 · 363 资产档 · 101 概念图 · 100 域包/1200 细分 · 标准目录 370 条（可达 332 / 不可达 38 · 机构 194 · 206 条依赖边） · 标准绑定 1200 条
**质量凭证**：verify v2.30 · check1-42 · PASS=76（`bash verify.sh` 单入口；期望基线取自 `quality_baseline.EXPECTED_*`） · 馆藏 3 件

分层：data 148 · eng 38 · form 29 · gov 71 · iface 84 （按标准目录 layer）

> 本区由 `python scripts/nf.py stats --write` 生成，禁止手改；口径与实算真源见 `protocol/repo_stats.json`。
<!-- nf:stats:end -->

## 协议链与文档导航

| 层 | 入口 |
|---|---|
| 方向 | `STRATEGY.md` |
| 协议 | `01_核心协议.md` · `02_联动注册表.md` · `06_Agent执行协议.md` · `07_官方核心出厂与社区预设导航.md` · `protocol/WORLD_MODEL.md` |
| 库 | `03_管线库/` · `04_模块库/` · `05_资产库/` |
| 社区 | `community/README.md` · `community/模板制作指令包.md` |
| AI | `docs/agent/AGENT_START.md` · `docs/agent/AI_ROUTING.md` · `docs/meta/DEEP_DIVE.md` |
| 工具 | `docs/mcp.md` · `docs/terminal.md` · `docs/layers.md` · `docs/release.md` · `scripts/nf.py` · `tui/nf.py` · `verify.sh` |
| 接入面 | `integrations/README.md`（MCP / LSP / CLI / TUI / 图书馆 / Skill / npm / Rust / .NET / A2A） |
| 馆 | `library/INDEX.md` · `docs/agent/ROUTES.md` |

## 版本

现在安装就是 **`ninfenz` 1.1.0**（npm 正式源已发布，`mcpName` 已与官方 MCP Registry 对齐）：

```bash
npm i -g ninfenz@latest --registry https://registry.npmjs.org   # 装或升级（避开滞后镜像）
nf --version             # 看当前版本
nf stats                 # 看门禁与仓库状态
```

同一份代码里有三条版本线，各自独立升：

| 线 | 当前 | 这条线管什么 |
|---|---|---|
| **内容与协议** | **v2.30.0** | 文档模板、领域包、规范本身 —— 决定「能生成什么」 |
| **命令行工具** | **1.1.0** | `nf` 命令 / npm 包 / MCP 服务 —— 决定「怎么用」 |
| **质量门禁** | 见 `nf stats` | 仓库自检通过情况 —— 决定「有没有改坏」 |

当前门禁发布为 **v2.30.0**；逐版变更、证据与发布说明以 `CHANGELOG.md`
和 GitHub Releases 为准，不在 README 复制易漂移的版本流水。

发版规则：内容线使用 `v2.x` 标签；CLI 线独立按语义版本编号；
每次发版同步写 `CHANGELOG.md`，tag 只打在**带功能的那次提交**上。

