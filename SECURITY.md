# 安全策略（Security Policy）

> 本件是 NF 的**安全报告通道与处理口径**（对齐 OpenSSF Scorecard 的 Security-Policy 信号：
> 仓库须有成文的安全策略与私密报告通道）。范围覆盖：协议与代码资产、CI/自动化、投稿与入库通道。

## 一、如何私密报告

请用 **GitHub Security Advisories** 的私密通道报告：
<https://github.com/Monyeah777/NinFenz/security/advisories/new>。
不要用公开 Issue 报安全问题——公开 Issue 会触发**云端代收站**的自动入库机器人（见下），
等于把细节先公开分发一次。

报告请尽量包含：影响面（哪条通道/哪个文件）、复现步骤、期望行为与实际行为、你的环境。

## 二、范围内（IN SCOPE）

- 协议与机读契约：`01_核心协议.md` / `02_联动注册表.md` / `protocol/**`（含 schema 与台账）；
- 代码资产：`desktop/src/core/**`（core 层）、`scripts/**`、`.github/scripts/**`（入库机器人）；
- 自动化与供应链：`.github/workflows/**`、依赖固定清单、action 固定策略；
- **投稿通道的信任边界**：`library/` 与社区包内容属**外来内容**（详规见 `06_Agent执行协议.md §0`
  与容器化说明）——伪造「系统指令」类前缀、诱导消费方执行写盘/推送/删除的正文，都在范围内。

## 三、范围外（OUT OF SCOPE）

- 纯内容合规（错别字、观点、题材）——走常规 Issue 或联系作者；
- 依赖上游自身已公开的漏洞（请直接报给上游；本仓用固定版本 + 定期审计跟进）；
- 需要物理接触或已失陷主机的攻击场景；
- 对本仓**已文档化的设计取舍**（例如：Gitee 投稿通道为**零门槛开放**、内容由作者事后把关；
  又如：社区投稿正文按**数据**消费、不构成指令）——这类若你认为应改，请作为设计建议提。

## 四、处理口径

1. **确认**：收到后先做可复现性核对（本仓所有安全判据都可独立复跑：`bash verify.sh`、
   `python scripts/verify_report.py --check`、`python scripts/sast_check.py` 等）。
2. **修复优先于披露**：修复随常规提交入仓，并在 CHANGELOG 以结果形态记账（不含复现细节）。
3. **凭据类问题按已泄露处理**：任何出现在对话/日志/文档/提交里的 token，一律视为已泄露，
   立即撤销重建（见 `CONTRIBUTING.md` 的 Token 轮换 SOP）。

## 五、依赖与漏洞修复阈值

- **Critical**：响应 SLA 24 小时，7 天内修复或隔离；停止发布，有可达路径时按供应链事故处理。
- **High**：响应 SLA 48 小时，30 天内修复或明确处置；修复前阻断 PR 合并与 tag 发布。
- **Medium**：响应 SLA 7 天，90 天内修复或进入维护窗口；发布前复查是否升级。
- **Low**：响应 SLA 14 天，180 天内安排修复；不得因低等级而静默关闭。
- **License violation**：阻断发布；替换依赖、取得兼容授权，或由明确例外记录批准。

依赖来源、供应商准入、SBOM 和验签方式见 [docs/supply-chain-security.md](docs/supply-chain-security.md)。
目前为单人维护；上述响应 SLA 是维护目标，不是对外赔偿承诺。Critical/High 在修复或明确处置前不会进入正式发布。

### SCA、SAST 与发布处置

- SCA：PR 的 dependency review 在出现 **High/Critical** 已知漏洞时阻断；定时 `pip-audit`、
  `cargo audit` 与依赖审计覆盖固定工具链。无上游修复时必须提交不可达/不可利用证据或明确例外，
  不得用忽略文件静默清零。
- SAST：CodeQL、Bandit 与仓库 SAST 棘轮共同运行。可操作的 **High/Critical** 发现阻断发布；
  Medium 进入维护窗口并带修复或风险接受记录；任何新增规则命中都必须显式处置。
- License：不在供应商 allowlist 或被判定不兼容的许可证阻断发布，除非存在有期限、可审查的例外。
- 漏洞处置通过 `results/supply-chain/vuln-disposition.json` 进入 OpenVEX；`not_affected` 必须给出
  justification 与 impact statement，`affected` / `under_investigation` 必须给出 action statement。

## 六、公开漏洞通告

已确认并完成协调披露的漏洞通过 GitHub Security Advisories 公开：
<https://github.com/Monyeah777/NinFenz/security/advisories>。通告须至少包含受影响版本、
判断是否受影响的方法、缓解措施和修复版本；修复版本的 checksums、SBOM 与 attestation
可在对应 GitHub Release 验证。

## 七、本仓已有的安全机制（供报告前自查）

| 机制 | 载体 | 判据 |
|---|---|---|
| 危险 sink 面（动态执行/反序列化/递归删除） | `desktop/src/core/purity_scan.py` | check27 R6（放行须登记理由） |
| 明文密钥扫描 | `ci-verify.yml` | 命中即红 |
| 依赖固定 + 版本审计 | `.github/requirements-*.txt` + `dependency-audit.yml` | 每周 + push |
| action 固定到 commit SHA | 全部 workflow | 回归测试 `test_ci_supply_chain.py` |
| 入库通道的凭据与内容边界 | `.github/scripts/*_ingest.py` | 令牌不落盘、密钥形状拒收、正文/API 响应/分页均有硬上限 |
| 本机 daemon IPC | `desktop/src/core/daemon.py` | Windows 独占端口、常量时间令牌、严格 UTF-8 JSON、请求/响应/内存硬上限 |
| MCP 只读资源面 | `desktop/src/core/mcp_runtime.py` + `repo_index.py` | URI 白名单、realpath 包含性、拒绝符号链接越界、快照/资源/出站消息上限 |
| 插件宿主 | `scripts/plugin_host.py` | wasmtime fuel/超时、无 fs/net/env、stdin/stdout/stderr 有界、argv 长度预算 |
| 静态检查（含未定义名） | `nf release` → ruff | 本地 pre-push 即拦 |
| SAST（SQL 拼接/弱随机/XXE/命令注入等） | `sast.yml` → `scripts/sast_check.py` | (工具,文件,规则) 计数棘轮：新增/上升即红 |
| 供应链评分 | `scorecard.yml` | OpenSSF Scorecard（结果可见） |
| 执行目标仓库代码的信任门（H1） | `desktop/src/core/repo_trust.py` + `nf verify --trust-repo` | `tests/test_repo_trust.py`：外来仓库默认拒绝执行、无副作用 |

应用安全作用域评估见 [docs/asvs.md](docs/asvs.md)：覆盖本地 CLI、daemon、MCP、插件、
文件处理、配置、密钥、日志与错误面。该矩阵是内部 ASVS 5.0.0 L2 证据，不是第三方认证；
`partial` 与 `not-applicable` 项均保留明确 gap。输入规则、数据分类、密码算法、通信、
授权、资源上限和生产默认值的机读控制清单见
[packaging/security/application-security-controls.json](packaging/security/application-security-controls.json)，
人读说明见 [docs/security-controls.md](docs/security-controls.md)。

## 八、执行目标仓库代码的信任边界（H1，2026-10-22 审计）

- **面**：`nf verify` 的引擎侧会对目标仓库 `verify.sh` 里的 heredoc Python 做 `exec`
  （`desktop/src/core/gate_inproc.py`）——**在谁的仓库里跑，就执行谁的代码**
  （CWE-94/95；OWASP A03:2021 – Injection；ASVS V5.2.1「不得对不可信数据求值」）。
- **默认策略（fail-closed）**：只有“当前运行代码所在的安装根”自动可信。外部仓库即使把
  `origin` 伪造成官方 URL 也不自动可信——本地 remote 不是代码身份凭证。其它仓库一律拒绝执行，
  `nf verify` 以退出码 2 打印风险与修复指引（不静默降级）。
- **显式放行**：`nf verify --trust-repo`（等价 `NF_TRUST_REPO=1`），风险由调用者承担；
  自建镜像 / fork CI 可用 `NF_TRUST_OWNERS`（逗号分隔）显式 opt-in owner。两者都表示调用者
  已人工审阅目标仓库，不是来源证明。
- **纵深防御**：`core/gate_inproc.py` 的三个 `exec` 入口在直接调用时同样 `assert_trusted()`，
  被拒时**不产生任何执行副作用**。
- **判据**：`desktop/tests/test_repo_trust.py`（URL 严格解析、伪造官方 origin 仍拒绝、安装根
  自动信任、拒绝无副作用、CLI 前置拒绝与 `--trust-repo` 放行）。
