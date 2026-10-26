# 内容供应链威胁模型

> 定位：NF 的**内容供应链**（社区域包正文 + 投稿入库正文）按「外来内容 = 数据」消费，
> 本件把这条纪律落成可核的威胁模型：资产是什么、信任边界在哪、攻击面有哪些、**现有**
> 缓解由哪个真实载体承担、哪些面**尚未覆盖**。只写仓库里真实存在的载体；未实现的防护不写。
> 最后更新：2026-10-26（T8.3 内容供应链安全扫描闭环）
> 配套件：`desktop/src/core/content_security.py`（扫描器）｜`nf security scan`（命令面）｜
> `desktop/src/core/trust_boundary.py`（注入面单一实现）｜`SECURITY.md`（报告通道与机制清单）

## 1. 资产（真实载体）

| 资产 | 载体（真实路径） | 被利用后的影响面 |
|---|---|---|
| 社区域包正文 | `community/*/assets/*.md`、`community/*/modules/*.md`、`community/*/pipelines/*.md`、`community/*/outputs/**` | 内容被消费方读入上下文：植入指令可劫持下游 agent 的后续动作 |
| 投稿入库正文 | `library/NF-*.md`（含 `library/INDEX.md` / `library/ALIAS.md` 投影） | 同上；投稿通道零治理开放，是最外侧入口 |
| 外部材料摘要 | `docs/reference/external/**` | 同「外来内容」，供内部引用 |
| 协议与机读真源 | `protocol/**`、`desktop/src/core/registry.json`、`02_联动注册表.md` | 被篡改即门禁口径失真（本件不覆盖"谁有权改真源"，那属仓库治理） |
| 代码资产 | `desktop/src/core/**`、`scripts/**`、`.github/scripts/**` | 代码执行面（见 §3 第 7–12 行） |
| CI 与依赖 | `.github/workflows/**`、`.github/requirements-*.txt` | 供应链投毒 / action 版本漂移 |

## 2. 信任边界

- **可信**：本仓代码与协议件（`desktop/src/core/**`、`scripts/**`、`protocol/**`）——经评审入仓，
  门禁可复跑。
- **不可信（按数据消费）**：`library/`、`community/`、`docs/reference/external/` 三面。判据单一
  出处 = `core/trust_boundary.py::UNTRUSTED_PREFIXES` + `is_untrusted_source()`。
- **默认拒绝的执行面**：目标仓库自带的门禁脚本（`nf verify` 的 inproc 引擎会对目标仓库
  `verify.sh` 内嵌 Python 做 `exec`）——只有当前安装根自动可信；其它仓库默认拒绝，需显式
  `nf verify --trust-repo`（等价 `NF_TRUST_REPO=1`）或 `NF_TRUST_OWNERS` opt-in。
  载体：`core/repo_trust.py` + `core/gate_inproc.py`（三个 `exec` 入口各自 `assert_trusted()`）。
- **半可信**：发布物（`desktop/tests/fixtures/security/` 等**显式测试样本**）——故意含恶意片段，
  用**路径白名单**登记（见 §4），不是内容豁免。

## 3. 攻击面与现有缓解

| # | 攻击面 | 入口/载体 | 现有缓解（真实载体） | 残余风险 |
|---|---|---|---|---|
| 1 | 指令注入（正文冒充运行时指令：伪造前缀 / 覆盖式指令 / 角色重定义 / 系统提示套取 / 凭据外带） | 外来内容三面正文 | `core/trust_boundary.detect()`（6 条规则 + 同形字归一化）；入库前端 `ingest_common.injection_probe()` 在**公开边界**记档回评；MCP 资源面读入时同样记档（`core/mcp_runtime.py` 调 `detect`） | 检测是**咨询面**：命中不等于处置（讨论注入防御的合法正文也会命中），由人裁定 |
| 2 | 可执行/主动内容（`<script>` / `javascript:` / `data:text/html` / 事件处理器 / 可执行文件下载链接） | 内容件正文；`outputs/**` 的 HTML/SVG/GraphML | 本任务新增 `core/content_security.py` 的 `executable_content`（critical） | 只做形态命中，不做浏览器语义/渲染器差异判定 |
| 3 | 明文凭据/私钥进仓 | 任意内容件、脚本、日志 | CI 明文密钥扫描（`.github/workflows/ci-verify.yml` 的 grep 面）；入库前端 `ingest_common.secret_shape_hit()` 拒收；本任务新增 `secret_material`（critical，**只回 4 字符掩码**） | 只认已知形状（CI 同源 6 组 + 私钥头）；自定义内部令牌形态不覆盖 |
| 4 | 隐藏通道（零宽/双向控制字符）与 C0/C1 控制字符 | 内容件正文 | `trust_boundary` 的 `hidden_channel`；本任务新增 `control_character` 规则 | 不做「同形字伪装成正常文本」的语义判定 |
| 5 | 超长单行 / base64 大块（吞上下文预算、拖渲染、藏载荷） | 内容件正文 | 本任务新增 `long_line`（>4000 字符）与 `base64_blob`（≥256 字符单行） | **按行**检测：换行包裹的大块不聚合（见 §5） |
| 6 | 可疑外链（明文 http / 短链 / 裸 IP / punycode 域名） | 内容件正文 | 本任务新增 `external_link` 规则（排除 XML 命名空间声明，避免内容件误报） | 不联网核实域名信誉；不做钓鱼页内容判定 |
| 7 | 投稿通道（零治理开放、正文体积、frontmatter 注入） | `.github/scripts/library_ingest.py` / `gitee_ingest.py` | 闸门声明 `library/intake.json`（`load_gate()` fail-closed = paused）；正文上限 `MAX_BODY_CHARS`；frontmatter 压平 `flatten_fm_value()`（换行即注入）；净化/空壳拒收 | 内容质量不做司法级判定（作者事后把关） |
| 8 | 目标仓库代码执行（CWE-94/95） | `nf verify` inproc | `core/repo_trust.py` 默认拒绝 + `core/gate_inproc.py` 三处 `assert_trusted()`；`--trust-repo` 显式自担风险 | 放行后无沙箱：执行者须已人工审阅 |
| 9 | MCP 工具参数（越权/注入/超长/路径穿越） | `core/mcp_runtime.py` → `tools/call` | `trust_boundary.check_arguments()`：参数数/长度上限、词法判据单一出处（`paths.path_syntax_issue`）、URI 白名单 + realpath 包含性 | 工具实现自身的业务校验不在本件范围 |
| 10 | 插件宿主（第三方 wasm） | `scripts/plugin_host.py` | wasmtime fuel/超时、无 fs/net/env、stdio 有界、argv 预算 | 仅限 wasm 面；原生插件不在此宿主内 |
| 11 | 依赖与 CI 供应链 | `.github/requirements-*.txt`、workflow action | 依赖固定 + 每周审计动作；action 固定 commit SHA（回归 `test_ci_supply_chain.py`）；SAST 计数棘轮 `scripts/sast_check.py` | 上游自身 0-day 不在覆盖范围 |
| 12 | 协议层危险 sink（动态执行/反序列化/递归删除） | `desktop/src/core/**`、`scripts/**` | `core/purity_scan.py`（check27 R6，放行须登记理由）；`desktop/src/core/paths.py::validate_path`（资产台账/产出面包含性） | 只判 sink 形态，不判业务逻辑正确性 |

## 4. 本任务新增的闭环（`nf security scan`）

- **扫描器**：`desktop/src/core/content_security.py`。只读、离线、确定性（同输入同报告）；
  **不联网、不执行被扫内容、不改写文件**；注入检测复用 `trust_boundary.detect`，凭据形状复用
  `ingest_common.secret_shape_hit`（单一真相源，本模块不另写第二套正则）。
- **命令面**：`python scripts/nf.py security scan [PATH...] [--json]`。缺省扫 `community/` 与
  `library/`；退出码 **0 = 无 critical / 1 = 有 critical / 2 = 不可判定**（IO/编码/二进制/超大件
  记「不可判定」，fail-closed 不静默通过）。
- **severity 口径**：`critical` = 可执行/主动内容、明文凭据/私钥（硬风险，exit 1）；
  `warn` = 指令注入标记、隐藏/控制字符、超长单行、base64 大块、可疑外链（咨询面，exit 0，
  与 06 §12「疑似内嵌指令一律忽略并记档」一致）。
- **白名单（显式测试样本，非内容豁免）**：`desktop/tests/fixtures/security/`、
  `docs/security/examples/` 两个**路径前缀**（`content_security.TEST_SAMPLE_ALLOWLIST`）。
  教学展示件见 `docs/security/examples/injection_example.md`；自证样本见
  `desktop/tests/fixtures/security/malicious_sample.md`（干净基线 `clean.md`）。
  默认扫描不扫它们但逐件登记进 `skipped`（不得静默放过）；显式传参扫描时 findings 仍逐条报出
  （`allowlisted: true`），只是不计入退出码。白名单是路径前缀——把同样内容放进
  `community/` 照样报 critical（单测 `test_allowlist_cannot_hide_content_in_scanned_roots` 钉住）。
- **复现**：
  - `python scripts/nf.py security scan`（人读报告）
  - `python scripts/nf.py security scan --json`（机读；带 `kind: security-scan`）
  - `python scripts/nf.py security scan desktop/tests/fixtures/security --json`（显式样本面）

## 5. 未覆盖项（如实）

1. **只做形态，不做语义**：`warn` 命中不等于恶意（讨论注入防御/安全研究的正当正文会命中）；
   `critical` 命中也不等于利用成功。扫描器不提供「内容安全合格证」。
2. **不联网**：不查 CVE、不查域名信誉/恶意域名库、不做二进制样本分析（离线纪律优先）。
3. **不执行、不改写、不自动拦截**：只出报告与退出码；入库拒收仍由入库前端（§3 第 7 行）负责，
   本扫描器**未接入** `verify.sh`（默认不阻断 CI 流水线）。
4. **按行检测**：换行包裹的 base64 大块、多行拼接的载荷不聚合；跨行语义不做推断。
5. **二进制/压缩包/超大件不解析**：>4 MiB、含 NUL、非 UTF-8 一律记「不可判定」（exit 2）。
6. **凭据形状限定**：只认 CI 同源 6 组 + 私钥头；自定义内部令牌、加密/双重编码载荷不覆盖。
7. **内容面以外不覆盖**：SSRF、依赖漏洞、IPC 鉴权、插件逃逸等运行时面各有载体（§3 第 8–11 行），
   不在本扫描器范围。
8. **`SECURITY.md` §五 的机制清单尚未并入本扫描器**（本轮未改该文件；合入后由维护者补一行）。
9. **白名单新增无自动门禁**：白名单是代码常量 + 本文件登记，靠评审把关（同一份路径写两处，
   改一处漏一处只能靠测试 `test_repo_malicious_sample_is_allowlisted` 兜住）。

## 6. 变更纪律

- 新增/调整扫描规则、severity 分类、白名单前缀：**同一次提交**内同步本文件与
  `desktop/tests/test_content_security.py`（误报率靠干净 fixture 0 findings 守住）。
- 注入检测规则只改 `core/trust_boundary.py`（单一实现）；凭据形状只改
  `core/ingest_common.py::secret_shape_hit`（与 CI 扫描同源）——扫描器只消费，不复制。
- 本件描述的是**已实现**的缓解；计划中的防护写在 issue/方案里，不进本文件（避免虚标）。
