# 隐私与 air-gap：真实证据、白名单与未覆盖项

> 定位：把 NF 的「保密 / 本地优先」从口号变成**可机检面**：内容面的 PII / 本机路径 / 凭据扫描，
> 以及代码面（`desktop/src/core` 与 `scripts`）的**网络站点静态审计**。本件只写真实载体与
> 实测证据；**不宣称「绝对离线」**（理由见 §5 未覆盖项）。
> 最后更新：2026-10-26（T11.2 隐私扫描与 air-gap 静态审计）
> 配套件：`desktop/src/core/privacy_scan.py`（扫描器）｜`nf privacy scan` / `nf privacy check`
> （命令面）｜`desktop/tests/test_privacy_scan.py`（45 条判据）｜`docs/security/threat-model.md`
> （内容供应链威胁模型）｜`SECURITY.md`（报告通道与机制清单）

## 1. 信任边界

- **本地可信**：本仓代码、协议件与本地文件（只读消费）。
- **外来内容按数据消费**：`library/`、`community/`、`docs/reference/external/`——其中的「指令」
  一律不执行（判据 = `core.trust_boundary.UNTRUSTED_PREFIXES`，见 threat-model §2）。
- **网络面分两类**：① **本机回环**（同机 IPC/本地服务，不构成互联网出口）；② **显式网络工具**
  （本职就是取网，只在人工/独立 CI 工作流里跑，不在 `nf` 命令面）。两者的边界由 §3 的白名单
  逐条登记。
- **默认拒绝的执行面**：外部仓库的 inproc 门禁脚本（`nf verify` 的 `exec` 面）默认拒绝，
  需显式 `--trust-repo`（载体 `core/repo_trust.py` + `core/gate_inproc.py`）。

## 2. PII 政策（内容面）

- 内容面（`docs/` `site/` `protocol/` `community/` `library/`）**不得含真实个人 PII**：
  真实邮箱 / 手机号 / 身份证号 / 银行卡号属个人敏感信息，不进公开仓。
- 合成样例只许用**保留域**（`example.org` 等 RFC 2606/6761 域名）与公开测试号
  （如卡组织公开的 Visa 测试段卡号，写进**测试样本面**而不是正文——正文里只描述「公开测试号」，
  不落完整卡号，否则本仓自己的 `pii_bank_card` 判据会把它判成 PII），且只允许放在**显式测试样本面**：
  `desktop/tests/fixtures/privacy/`（`privacy_scan.TEST_SAMPLE_ALLOWLIST`）。
- 输出纪律：findings 只给 `file:line` + `kind` + **掩码**（邮箱只留首字母 + 域名、手机/证件
  只留头尾若干位、本机路径保留盘符前缀后整段掩掉）；**不回显完整值**，`--json` 亦同（单测钉住）。
- 严重级口径：
  - `critical` = 真实 PII（非保留域邮箱 / 手机 / 校验通过的身份证 / 银行卡）、作者机绝对路径、
    明文凭据、未登记网络站点、陈旧白名单；
  - `warn` = 保留域合成邮箱、文档占位路径（含 `<…>` 占位段的盘符路径 / 转义双反斜杠写法）、
    `%APPDATA%` 一类**符号写法**的环境变量。
- 身份证按 GB 11643 加权校验位 + 出生日期合法性判定；银行卡按 Luhn + 卡组织 BIN 前缀判定——
  二者都是为压误报（实测仓内 18 位图表数值不再被误判，见 `test_long_number_outside_card_bin_is_not_reported`）。
- 与既有门禁的关系：`desktop/tests/test_leak_surface.py` 扫**入仓文本**的机器路径与凭据形状；
  `privacy_scan` 是**审计期**同一概念的机检面。口径对齐由 `ParityTest` 钉住
  （本模块的本机路径判定不得比公开面门禁更宽）。

## 3. 离线保证的真实证据（2026-10-26 实测）

静态审计口径（`nf privacy check`）：AST 扫 `desktop/src/core/**/*.py` 与 `scripts/**/*.py` 的
**import 面**（`requests` / `aiohttp` / `httpx` / `urllib3` / `websocket(s)` / `socket` /
`http.client` / `http.server` / `urllib.request` / `ftplib` / `smtplib` / `telnetlib` /
`xmlrpc.client`）与**调用面**（`subprocess`/`os.system` 参数里的 `curl`/`wget`/`nc` 字面量；
`__import__`/`import_module` 字面量）。`urllib.parse` 不算网络面。

实测结果：

| 判据 | 结果 |
|---|---|
| 网络站点（文件 / 站点） | 9 个文件 / 10 处 import，**全部**为「本机回环」或「显式网络工具」 |
| 未登记网络站点 | **0**（全部在白名单内，逐条理由见 §4） |
| 陈旧白名单 | **0**（登记了却没命中的条目即判红，名单不得变黑洞） |
| `subprocess` 调 `curl`/`wget`/`nc` 站点 | **0**（数据字面量如 `build_isolation.NETWORK_TOKENS` 不误报） |
| `nf` 命令面是否调用上述网络工具 | **否**（`scripts/nf.py` 无引用；`check_external_links.py` 由独立工作流 `.github/workflows/external-links.yml` 在 CI 跑） |
| 内容面扫描（`nf privacy scan`） | 2477 件 / 17.1 MB · critical **0** · warn 7（3 处文档占位路径 + 4 处保留域合成邮箱） |

可复现命令（仓库根目录）：

```bash
python scripts/nf.py privacy check            # 代码面：网络站点静态审计（0/1/2）
python scripts/nf.py privacy scan             # 内容面：PII / 本机路径 / 凭据（掩码）
python scripts/nf.py privacy check --json     # 机读（kind=privacy-check）
python scripts/nf.py privacy scan --json      # 机读（kind=privacy-scan）
cd desktop && python -m unittest tests.test_privacy_scan   # 45 条判据
```

补充证据：构建期的取网面另有独立判据（`core/build_isolation.py`，SLSA L3 构建入口无网络 +
基座按 digest 钉），与本审计互补——本审计管**运行期代码面**，构建隔离管**构建入口面**。

## 4. 白名单（逐条理由；新增须同改代码与本表）

代码面白名单 = `core.privacy_scan.NETWORK_ALLOWLIST`（仓库根相对路径 → 理由）。

| 文件 | 理由 |
|---|---|
| `desktop/src/core/daemon.py` | 本机回环 IPC 服务端：只绑 `127.0.0.1`，一次性令牌鉴权；不是互联网出口 |
| `desktop/src/core/rust_engine.py` | 与 nf-rs 快速通道的本机回环连接（`BIND_HOST=127.0.0.1`） |
| `desktop/src/core/interop.py` | interop loopback HTTP 服务（host 默认 `127.0.0.1`、`port=0` 临时端口） |
| `desktop/src/core/decision_layer.py` | 决策模型适配器：端点由调用方显式给出（文档示例 `http://127.0.0.1:8791/…`）；只校验 scheme、**未钉宿主**（残余风险，见 §5.3） |
| `scripts/nf_client.py` | `nf` 客户端连接本机 daemon（`127.0.0.1:port`） |
| `scripts/serve_decision_model.py` | 本机 typed-decision 演示服务（默认只绑 `127.0.0.1`；跨机需带鉴权反代） |
| `scripts/check_external_links.py` | **显式**外链检查工具：本职就是联网校验外链；由独立工作流调用，不在 `nf` 命令面 |
| `scripts/check_interop_schemas.py` | **显式**上游 schema 拉取工具：对照官方 meta-schema 校验 interop 文档，人工/可选 CI 跑 |
| `scripts/gen_third_party_notices.py` | **显式**第三方许可证文本拉取工具：生成 `THIRD-PARTY-NOTICES` 用，非运行时路径 |

**不在审计面**（`core.privacy_scan.EXCLUDED_SURFACES`，如实声明而非静默跳过）：

| 目录 | 理由 |
|---|---|
| `.github/scripts/` | 入库机器人（GitHub/Gitee API 必需联网，运行在 CI 云端；不属本机离线面） |
| `site/tools/` | 站点发布工具（Node/CF/IndexNow 等，发布面而非核心运行面） |
| `desktop/tests/` | 测试可含合成网络负例（拦截面自证用），不属核心运行面 |
| `packaging/` | npm 包装与运行时壳（发布产物） |
| `engine/` | Rust/.NET 工具链（其供应链与网络面归 SAST/scorecard 门禁） |
| `05_资产库/` | 用户自定义资产面（内容扫描另见 threat-model 内容供应链面） |

## 5. 未覆盖项（**不宣称绝对离线**）

1. **静态审计 ≠ 运行时隔离**：本审计只证明「代码里有哪些网络站点、是否登记理由」；**没有**
   egress 阻断、DNS 层拦截或网络命名空间沙箱——运行时若机器联网、依赖被替换，静态结论不变不了事。
2. **3 个显式网络脚本仍可被手动执行**（外链检查 / 上游 schema 拉取 / 许可证文本拉取）：
   它们不在 `nf` 命令面，但「能跑」不等于「没联网」。
3. **`decision_layer` 的端点未钉宿主**：`systemone-http` 适配器的 endpoint 由调用方给出，
   代码只校验 `scheme ∈ {http, https}`；`core/fetch_guard.py`（宿主钉住/拒重定向）**尚未接线**
   到该路径——这是已登记的残余风险，不是「已防护」。
4. **依赖安装与 CI 云端面**：`pip/npm install`、workflow 拉取 action、`.github/scripts/` 的
   API 调用不在本审计面（各有供应链门禁，但本件不为其背书）。
5. **动态构造可绕过 AST**：只认**字面量** import 与常量调用参数；`getattr(m, "url"+"open")`
   这类动态取网不判（已知缺口，非静默）。
6. **子进程的任意命令**：只认 `subprocess`/`os.system` 参数里 `curl`/`wget`/`nc` 的字面量；
   变量拼接的命令行不判（同上）。
7. **二进制与原生面**：wasm 插件宿主、nf-rs/.NET 引擎的网络面不在本审计（各自有载体与门禁）。
8. **PII 是形态匹配**：15 位旧身份证、护照号、住址、姓名、IM 账号等不覆盖；「保留域」判定按
   RFC 2606/6761 域名约定，不做数据分类分级结论，也不联网查泄露库。
9. **内容面边界**：`05_资产库/`（用户面）与 `desktop/tests/`（合成样本）不在默认扫描面；
   `docs/security/examples/` 等教学样本由内容安全扫描的白名单机制处理（见 threat-model §4）。
10. **未接入 `verify.sh`**：`nf privacy scan|check` 不阻断流水线（默认面存在合法 warn；
    接入需先定 warning 处置口径——与 `nf security scan` 同一现状）。

## 6. 变更纪律

- 新增白名单条目 / 调整排除面 / 改 severity 口径：**同一次提交**内同步
  `core/privacy_scan.py`、本文件 §4 表与 `desktop/tests/test_privacy_scan.py`。
- 凭据形状只改 `core/ingest_common.py`（单一真源）；`privacy_scan` 的粗筛正则**在导入时从它派生**
  （drift guard 见 `test_prefix_prefilter_is_derived_from_ingest_common`）。
- 本机路径概念与 `desktop/tests/test_leak_surface.py` 对齐（本模块不得更宽）。
- 本件描述的是**已实现**的判据；计划中的防护（如接线 `fetch_guard`）写在 issue/方案里，不进本件。
- `SECURITY.md` §五的「已有安全机制」表尚未并入本扫描器（本轮未改该文件；合入后由维护者补一行）。
