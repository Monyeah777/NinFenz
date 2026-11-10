# 安全策略（Security Policy）

> 本件是 NF 的**安全报告通道与处理口径**（对齐 OpenSSF Scorecard 的 Security-Policy 信号：
> 仓库须有成文的安全策略与私密报告通道）。范围覆盖：协议与代码资产、CI/自动化、投稿与入库通道。
> **通道分工**：漏洞 / 越权 / 凭据泄露 → 本件；行为与内容越界 → [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)；
> 使用问题 → [SUPPORT.md](SUPPORT.md)。三条通道**互不代收**，走错会被指回，不静默丢弃。

## 一、如何私密报告

请用 **GitHub Security Advisories** 的私密通道报告（仓库页 → Security → Report a vulnerability；
直达 `https://github.com/Monyeah777/NinFenz/security/advisories/new`）。
**不要**用公开 Issue 报安全问题——公开 Issue 会触发**云端代收站**的自动入库机器人（见下），
等于把细节先公开分发一次。

**报告模板（六项，缺项会来回追问）**：

1. **影响面**：哪条通道 / 哪个文件 / 哪个版本（内容线 tag 或 CLI 版本）；
2. **复现**：最小命令或片段 + 前置条件（平台 / Python 版本 / 安装方式）；
3. **期望 vs 实际**：两段原文，不要只写「不安全」；
4. **可利用性**：需要什么前提（本地写权限 / 网络可达 / 特定配置），细节是否已在公开场合出现；
5. **是否已尝试修复**：有补丁请附；没有也请说明；
6. **署名与披露偏好**：默认在 Advisory 内致谢，可选匿名；是否需要 CVE、可接受的公开时间。

## 二、范围内（IN SCOPE）

- 协议与机读契约：`01_核心协议.md` / `02_联动注册表.md` / `protocol/**`（含 schema 与台账）；
- 代码资产：`desktop/src/core/**`（core 层）、`scripts/**`、`.github/scripts/**`（入库机器人）；
- 自动化与供应链：`.github/workflows/**`、依赖固定清单、action 固定策略；
- **投稿通道的信任边界**：`library/` 与社区包内容属**外来内容**（详规见 `06_Agent执行协议.md §0`
  与容器化说明）——伪造「系统指令」类前缀、诱导消费方执行写盘/推送/删除的正文，都在范围内。

## 三、范围外（OUT OF SCOPE）

- 纯内容合规（错别字、观点、题材）——走常规 Issue 或联系作者；
- **行为准则类问题**（骚扰 / 歧视 / 报复 / 恶意举报）——走 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 的私密通道；
  本件不受理这类举报、也不对其内容作评价；
- 依赖上游自身已公开的漏洞（请直接报给上游；本仓用固定版本 + 定期审计跟进）；
- 需要物理接触或已失陷主机的攻击场景；
- 对本仓**已文档化的设计取舍**（例如：Gitee 投稿通道为**零门槛开放**、内容由作者事后把关；
  又如：社区投稿正文按**数据**消费、不构成指令）——这类若你认为应改，请作为设计建议提。

## 四、处理口径

1. **确认（7 天内）**：收到后 **7 天内**回复「已收到」并给出初判（在范围内 / 需补信息 / 范围外指路）。
   这是**流程确认**，不是修复时限；处理本身不承诺时限（同 [SUPPORT.md](SUPPORT.md) 的口径）。
2. **核对**：做可复现性核对（本仓安全判据都可独立复跑：`bash verify.sh`、
   `python scripts/verify_report.py --check`、`python scripts/sast_check.py` 等）。
3. **修复优先于披露**：修复随常规提交入仓，并在 CHANGELOG 以结果形态记账（**不含复现细节**）。
4. **协调披露（默认 90 天）**：从确认受理起默认 **90 天**内协调公开；修复已发布则可提前公开，以先到者为准。
   更短或更长的窗口在 Advisory 内单独约定，**不单方面公开**。
5. **CVE**：本仓非独立 CNA；需要 CVE 时在 GitHub Advisory 内请求分配（GitHub 是 CNA）。
6. **致谢**：默认在 Advisory 与 CHANGELOG 致谢；可事先声明**匿名**。
7. **无赏金计划**：本仓不使用漏洞赏金，报告按上述流程处理，不构成奖励承诺。
8. **凭据类问题按已泄露处理**：任何出现在对话/日志/文档/提交里的 token，一律视为已泄露，
   立即撤销重建（见 `CONTRIBUTING.md` 的 Token 轮换 SOP）。

## 五、本仓已有的安全机制（供报告前自查）

| 机制 | 载体 | 判据 |
|---|---|---|
| 危险 sink 面（动态执行/反序列化/递归删除） | `desktop/src/core/purity_scan.py` | check27 R6（放行须登记理由） |
| 明文密钥扫描 | `ci-verify.yml` + 入库通道脱敏（前 4 字符）+ GitHub secret scanning | 命中即红；入库拒收并把疑似密钥**脱敏**后再评论 |
| 依赖固定 + 版本审计 | `.github/requirements-{ci,lint,sast,audit}.txt` + `dependency-audit.yml` | 四份固定集全审：每周 + push + requirements 改动 PR |
| 依赖漏洞告警 | GitHub Dependabot alerts（含 Cargo/npm） | 当前 open=0（2026-11-09 核查） |
| action 固定到 commit SHA | 全部 workflow（checkout v7 / setup-python v6 / upload-artifact v7 / codeql-action v4，node24 面） | 回归测试 `test_ci_supply_chain.py`；pins 与版本基线见 `docs/L3_FROZEN.md` |
| 容器基座固定到 digest | `packaging/nfal/Dockerfile` + `packaging/hf-space/Dockerfile` | 三处 FROM image@sha256:…；升级=显式改 digest |
| 入库通道的凭据与内容边界 | `.github/scripts/*_ingest.py` | 令牌不落盘、密钥形状拒收、正文/API 响应/分页均有硬上限 |
| 本机 daemon IPC | `desktop/src/core/daemon.py` | Windows 独占端口、常量时间令牌、严格 UTF-8 JSON、请求/响应/内存硬上限 |
| MCP 只读资源面 | `desktop/src/core/mcp_runtime.py` + `repo_index.py` | URI 白名单、realpath 包含性、拒绝符号链接越界、快照/资源/出站消息上限 |
| 插件宿主 | `scripts/plugin_host.py` | wasmtime fuel/超时、无 fs/net/env、stdin/stdout/stderr 有界、argv 长度预算 |
| 静态检查（含未定义名） | `nf release` → ruff | 本地 pre-push 即拦 |
| SAST（SQL 拼接/弱随机/XXE/命令注入等） | `sast.yml` → `scripts/sast_check.py` | (工具,文件,规则) 计数棘轮：新增/上升即红 |
| 代码扫描（数据流/污点） | `codeql.yml`（python + js/ts） | PR 路径过滤 / push main / 周 schedule；结果进 code scanning 面板（非 required） |
| SAST 扩展面可见性 | `sast.yml` 的 tui/ + packaging/ 非阻塞扫描 | JSON 留 artifact（`sast-extra-*.json`）；扩棘轮待 task-40 |
| 供应链评分 | `scorecard.yml` | OpenSSF Scorecard（结果可见） |
| 执行目标仓库代码的信任门（H1） | `desktop/src/core/repo_trust.py` + `nf verify --trust-repo` | `desktop/tests/test_repo_trust.py`：外来仓库默认拒绝执行、无副作用 |

## 六、执行目标仓库代码的信任边界（H1，2026-10-22 审计）

- **面**：`nf verify` 的引擎侧会对目标仓库 `verify.sh` 里的 heredoc Python 做 `exec`
  （`desktop/src/core/gate_inproc.py`）——**在谁的仓库里跑，就执行谁的代码**
  （CWE-94/95；OWASP A03:2021 – Injection；ASVS V5.2.1「不得对不可信数据求值」）。
- **默认策略（fail-closed）**：只有“当前运行代码所在的安装根”自动可信。外部仓库即使把
  `origin` 伪造成官方 URL 也不自动可信——本地 remote 不是代码身份凭证。其它仓库一律拒绝执行，
  `nf verify` 以退出码 2 打印风险与修复指引（不静默降级）。
- **显式放行**：`nf verify --trust-repo`（等价 `NF_TRUST_REPO=1`），风险由调用者承担；
  自建镜像 / fork CI 可用 `NF_TRUST_OWNERS`（逗号分隔）显式 opt-in owner。两者都表示调用者
  已人工审阅目标仓库，不是来源证明。
- **纵深防御**：`desktop/src/core/gate_inproc.py` 的三个 `exec` 入口在直接调用时同样 `assert_trusted()`，
  被拒时**不产生任何执行副作用**。
- **判据**：`desktop/tests/test_repo_trust.py`（URL 严格解析、伪造官方 origin 仍拒绝、安装根
  自动信任、拒绝无副作用、CLI 前置拒绝与 `--trust-repo` 放行）。
