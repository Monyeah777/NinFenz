# NinFenz 仓库地图

本文只负责导航，不复制版本、门禁或发布状态。涉及运行时行为的断言，必须回到代码、测试、`verify.sh`、Git 提交和不可变标签核实。

## 四个治理角色

| 角色 | 唯一入口 | 职责 |
|---|---|---|
| 规则宪法 | [`AGENTS.md`](../AGENTS.md) · [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Agent 行为、贡献流程、分支与 PR 门禁 |
| 方向与质量 | [`STRATEGY.md`](../STRATEGY.md) | 产品方向、质量准绳和非目标 |
| 当前状态 | [`docs/meta/ROADMAP.md`](meta/ROADMAP.md) | 当前版本边界、健康状态和待决事项 |
| 历史 | [`decisions/INDEX.md`](../decisions/INDEX.md) · [`CHANGELOG.md`](../CHANGELOG.md) | 长期决策、删除理由和已发布变更 |

## 按任务查找

| 需要完成 | 去哪里 | 用什么核实 |
|---|---|---|
| 5 分钟安装与首次运行 | [`docs/quickstart.md`](quickstart.md) | `bash scripts/quickstart_check.sh` |
| 给 AI/Agent 接入任务 | [`docs/agent/AGENT_START.md`](agent/AGENT_START.md) → [`docs/agent/AI_ROUTING.md`](agent/AI_ROUTING.md) | `verify.sh`、相关测试 |
| 修改协议或机器契约 | [`protocol/README.md`](../protocol/README.md) · `01`–`07` 协议件 | `bash verify.sh` |
| 修改 CLI 或核心代码 | [`desktop/`](../desktop/) · [`scripts/`](../scripts/) | `cd desktop && python3 -m unittest discover -s tests -q` |
| 查 MCP、终端、LSP 等接入面 | [`docs/mcp.md`](mcp.md) · [`docs/terminal.md`](terminal.md) · [`docs/lsp.md`](lsp.md) · [`integrations/README.md`](../integrations/README.md) | 对应客户端 proof 与门禁测试 |
| 查安全边界和报告渠道 | [`SECURITY.md`](../SECURITY.md) · [`docs/security-controls.md`](security-controls.md) | 安全测试、审计结果、GitHub Security |
| 查供应链与发布证据 | [`docs/release.md`](release.md) · [`docs/supply-chain-security.md`](supply-chain-security.md) | GitHub Release、attestation、`verify.sh` |
| 查社区领域包 | [`community/README.md`](../community/README.md) | 包内 `protocol.yaml`、登记表和门禁 |
| 查内容库与投稿 | [`library/INDEX.md`](../library/INDEX.md) | `library/intake.json` 与入库门禁 |
| 查未发布变更 | [`changes/README.md`](../changes/README.md) | 每个变更的 `type:` / `surface:` / `note:` |
| 查长期决策和移除原因 | [`decisions/INDEX.md`](../decisions/INDEX.md) | ADR 正文及其替代关系 |
| 查发布历史 | [`CHANGELOG.md`](../CHANGELOG.md) | Git 标签与 GitHub Release |

## 新增根目录文件前

根目录只保留产品入口、治理入口、构建入口和必须保持兼容的协议入口。临时消息、日志、一次性审计中间件、实验快照和交接草稿应放在内部目录或本地档案，不新增到根目录。

新增根目录文件时，PR 必须说明：

1. 为什么现有入口不能承载该内容；
2. 它属于规则、导航、状态、历史、构建还是协议中的哪一类；
3. 谁会在什么场景读取它；
4. 如何验证它不会与现有权威入口重复或漂移。
