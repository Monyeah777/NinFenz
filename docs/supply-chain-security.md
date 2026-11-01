# 供应链安全与发布验证

> 最后更新：2026-11-02

本文件是 NinFenz 发布工件、依赖摄取、SBOM、来源证明和漏洞响应的人读入口。机读证据位于
`packaging/supply-chain/`，判据入口为：

```bash
python scripts/supply_chain_policy.py
python scripts/validate_sboms.py packaging/npm/dist/release
```

## 发布工件

正式 npm 工件由 `packaging/npm/tools/build_release.py` 一次产出：

| 工件 | 用途 |
|---|---|
| `ninfenz-<version>.tgz` | 确定性 npm tarball |
| `ninfenz-<version>.cdx.json` | CycloneDX 1.6 SBOM |
| `ninfenz-<version>.spdx3.json` | SPDX 3.0 JSON-LD SBOM |
| `ninfenz-<version>.openvex.json` | 与漏洞处置台账一致的 OpenVEX 0.2.0 文档 |
| `ninfenz-<version>.payload-manifest.json` | 逐文件 SHA-256 与聚合树摘要 |
| `SHA256SUMS` | 所有发布文件的完整性清单 |
| `release-metadata.json` | 源提交、可复现结论、SBOM、VEX 和工件映射 |
| `ninfenz_pyengine-<version>-cp311-*.whl` | 由 Maturin 构建的 PyO3 原生扩展 wheel |
| `wheel-metadata.json` | wheel 源提交、固定 Rust/Maturin/Python 工具链与摘要 |
| `WHEEL-SHA256SUMS` | wheel 与 wheel metadata 的独立完整性清单 |

构建器对同一源树连续构建两次，tarball 或 wheel 字节不同即失败。tar 成员顺序、权限、uid/gid、mtime、
gzip mtime 和 OS 字节均被归一；payload 清单的 `generated_at` 取源提交时间或显式
`SOURCE_DATE_EPOCH`，不读取墙钟。wheel 另以 Rust 1.99.1、Maturin 1.16.0 和 CPython 3.11
固定构建，并在按 digest 固定的 manylinux_2_28 容器内安装到新 venv，再验证
`ABI_VERSION`、SHA-256、反序字节和浮点 repr。

## SLSA v1.2 Build L3、provenance 与 VSA

`.github/workflows/npm-publish.yml` 的 tag/手动发布路径执行：

1. 调用方把全部构建步骤交给同仓 reusable workflow `slsa-build-l3.yml`，调用方不直接构建；
2. reusable workflow 在 GitHub 托管、每次新建的 runner 上从不可变提交构建，禁用 setup/pip
   持久缓存，并以 `--no-cache-dir` 安装固定版本验证器；
3. 两次 npm 构建与两次 Maturin wheel 构建逐字节比较，生成 CycloneDX、SPDX、OpenVEX、
   payload 清单、wheel metadata 与两套 checksums；
4. reusable workflow 内的 `actions/attest-build-provenance` 对两套 tarball、PyO3 wheel、
   双 SBOM、OpenVEX、checksums 与 metadata 生成 `https://slsa.dev/provenance/v1` 来源证明；
5. 独立 `verify` 作业下载发布束、校验 `SHA256SUMS` / `WHEEL-SHA256SUMS`，把签名 workflow 固定为
   `slsa-build-l3.yml`，并核对 source ref、source commit 与 predicate type；
6. `scripts/build_vsa.py` 复核可复现次数、源提交、摘要和必需工件，签发
   `https://slsa.dev/verification_summary/v1` predicate，再由 GitHub OIDC 签署为 VSA；
7. npm、GitHub Packages 与 GitHub Release 作业在发布前再次验证 Build provenance 和 VSA；
   任一验证失败都不能发布。

结论边界：代码与验证策略按 SLSA v1.2 Build L3 组织。SLSA 等级只对真实成功生成并回验
attestation 的某次工件成立；PR dry-run 不产生发布 provenance。Build L3 不要求 hermetic
断网构建，要求的是可信构建控制面、隔离/临时环境、不可伪造 provenance 与无缓存投毒影响。
VSA verifier 是本项目自己的 workflow，不是独立第三方 verifier。

最近一次不发布的 L3 验收运行由
[`slsa-l3-attestation-run.json`](https://github.com/Monyeah777/NinFenz/blob/main/results/supply-chain/slsa-l3-attestation-run.json)
逐项记录：reusable builder 成功生成 provenance，验证作业按 `slsa-build-l3.yml` signer
完成回验，并签发/回验 `verifiedLevels=["SLSA_BUILD_LEVEL_3"]` 的 VSA。该记录同时绑定
npm 主链与 Release evidence 两条独立运行、工作流摘要和发布 subject。

## 消费者验证

下载 Release 工件后，在包含这些文件的目录执行：

```bash
sha256sum -c SHA256SUMS
sha256sum -c WHEEL-SHA256SUMS
python scripts/wheel_release_metadata.py verify --release-dir . --source-commit <commit>
ARTIFACT=ninfenz-<version>.tgz
gh attestation verify "$ARTIFACT" --repo Monyeah777/NinFenz \
  --signer-workflow Monyeah777/NinFenz/.github/workflows/slsa-build-l3.yml \
  --deny-self-hosted-runners \
  --predicate-type https://slsa.dev/provenance/v1

# Custom VSA predicate type: download all bundles, then verify locally.
gh attestation download "$ARTIFACT" --repo Monyeah777/NinFenz --limit 30
DIGEST=$(sha256sum "$ARTIFACT" | cut -d ' ' -f1)
gh attestation verify "$ARTIFACT" --repo Monyeah777/NinFenz \
  --bundle "sha256:$DIGEST.jsonl" \
  --signer-workflow Monyeah777/NinFenz/.github/workflows/npm-publish.yml \
  --deny-self-hosted-runners \
  --predicate-type https://slsa.dev/verification_summary/v1
```

成功输出必须把 subject digest 绑定到同一次 GitHub Actions 构建，Build provenance 的签发
身份来自 reusable builder，VSA 的签发身份来自调用方验证 workflow。GitHub API 只接受 Build
provenance 作为服务端 predicate 过滤参数；VSA 的
自定义 predicate 先下载 bundle 再做本地密码学校验。对双 tarball、双 SBOM、OpenVEX、
checksums 和 metadata 应逐一验证；摘要相同但没有有效 attestation，不等于来源已经认证。

npm registry 自身也会保存 npm provenance。可在包页面查看，或通过公开 registry 的
provenance API 核验；GitHub attestation 与 npm provenance 是两条独立验证面。

## VEX 与漏洞处置

漏洞处置台账是 `results/supply-chain/vuln-disposition.json`，生成物是
`results/supply-chain/ninfenz.openvex.json`：

```bash
python scripts/generate_vex.py --check
python scripts/generate_vex.py --write
python scripts/generate_vex.py --json
```

改动处置台账后必须先 `--write`，再让 `--check` 与 `scripts/supply_chain_policy.py` 全绿。
`not_affected` 缺 justification / impact、`affected` / `under_investigation` 缺 action、非法状态
或过期 VEX 都会 fail-closed。发布构建会把 VEX 写入 tarball 同级的发布束、`SHA256SUMS` 和
`release-metadata.json`，并纳入 provenance / VSA subject。

## 运行时 EOL 门禁

`packaging/supply-chain/eol-support.json` 是 Python、Node 与固定容器镜像的支持窗口真源。
`python scripts/eol_policy.py` 会从根与 PyO3 的 `requires-python`、npm `engines.node`、
Dockerfile 与 GitHub Actions 工作流中提取实际声明，拒绝：

- 未登记在矩阵中的 Python、Node 或容器运行时版本；
- 已经超过 EOL 日期的版本；
- 未固定 digest 的 Docker 基础镜像；
- 超过复核期限或 `requires-python` 下限包含已 EOL 版本的清单。

矩阵只覆盖仓库控制的工具链与运行镜像，不把未扫描的传递依赖解释成“无 EOL 风险”。

## 依赖与供应商准入

依赖只能从 `packaging/supply-chain/package-sources.json` 声明的 HTTPS 源进入。运行工件当前
不安装第三方 Node 依赖；Python 核心走标准库，PyYAML 仅为可选增强；Rust 与 CI 工具链由锁文件
或精确版本固定。

`packaging/supply-chain/suppliers.json` 记录供应商、版本、许可证、来源、批准决定和复查期限。
新增直接发布依赖时必须同时更新供应商登记、SBOM 组件与依赖关系；未登记或许可证不在 allowlist
即失败。

更新规则：

- Dependabot 每周检查 GitHub Actions、pip、npm、cargo 与容器输入；
- PR 的 dependency-review 阻断 high/critical 已知漏洞；
- `pip-audit`、`cargo audit` 和 OSV 类扫描在定时任务中覆盖新披露漏洞；
- 上游停止维护、无安全更新或出现恶意发布时，供应商决定改为 `restricted` 或 `prohibited`，
  修复前不得发布。

## 凭据、OIDC 与轮换

- 正式发布优先使用 GitHub OIDC 短期身份：build provenance 与 VSA 通过 `id-token: write` 签署，
  npm trusted publishing 在可用时使用 OIDC，GitHub Packages 使用 job 级 `GITHUB_TOKEN`。
- PAT、npm token 与 registry 凭据不得硬编码、写入仓库或出现在命令行日志；需要 secret 时只放在
  GitHub protected environment / repository secret，并由 workflow 权限最小化。
- 任何 token 一旦进入对话、日志、提交或文档，按已泄露处理：立即撤销、重建、检查审计日志，
  重新运行受影响发布；旧凭据不得继续使用。
- 发布 workflow 的 actions 必须固定到 40 位 commit SHA；升级由 Dependabot 或人工审查提交，
  不接受浮动 tag。发布 workflow 改动、registry 变更、维护者权限变更或新 builder 接入都触发
  威胁模型复核。

## 威胁模型

| 威胁 | 信任边界 | 控制 |
|---|---|---|
| dependency confusion | 公共 registry → CI | 精确 registry、锁文件、精确版本、PR 审查 |
| 上游包被替换 | registry → 构建 | lock checksum、SBOM、Dependabot、漏洞审计 |
| 构建脚本执行恶意代码 | 源码/依赖 → runner | `npm install --ignore-scripts`、构建器无第三方依赖、checkout 不持久化凭据 |
| tarball 被替换 | runner → Release/npm | 双构建摘要、SHA256SUMS、OIDC attestation、消费者验签 |
| SBOM 与发布物脱节 | 构建产物 → SBOM | SBOM 从同一 payload 清单和 tarball 摘要派生 |
| 维护者账号被接管 | 账号 → main/release | MFA、Code Owners、ruleset、required status、受保护 tag |
| 不可复现的时间/环境噪声 | 环境 → 工件 | `SOURCE_DATE_EPOCH`、固定 mtime/mode/uid/gid、固定工具链 |

机读版本见 `results/supply-chain/threat-model.json`，覆盖 7 条 STRIDE 威胁、资产、actor、信任边界、
控制与残余风险。

## 测试环境与发布检查

- PR / push：workflow policy、供应链证据、VEX、SBOM、release artifact、action SHA 固定、
  dependency review、SAST 和离线单测。
- PR 发布 workflow 只做 dry-run，不签发 provenance / VSA，不发布 registry 或 GitHub Release。
- tag `v1.*` 或显式 `workflow_dispatch`：执行双构建、checksums、双 SBOM、OpenVEX、provenance、
  VSA 与发布前双重复核。
- 深度验证：`python scripts/verify_tests.py --jobs 4`；CI 按 job 分片，避免并发写同一 npm payload
  暂存目录。未能联网或 SBOM 验证器未安装时，测试必须显式 skip 或由 CI 固定清单补齐，不得伪造绿。

## 漏洞与事故响应

漏洞报告只走 [GitHub Security Advisories](https://github.com/Monyeah777/NinFenz/security/advisories/new)。
确认后按 `SECURITY.md` 的优先级修复；修复版本携带新的 SBOM、checksums 和 attestation。
对已知恶意版本，维护者停止发布、撤销受影响分发、在 GitHub Advisory 公布受影响版本与修复版本，
并把供应商登记改为 `prohibited` 或 `restricted`，直到替代版本通过验证。

## 标准证据边界

OSPS Baseline L1/L2、L3 与 S2C2F L1/L2 的逐项证据见
`packaging/supply-chain/osps-l1-l2.json`、`packaging/supply-chain/osps-l3.json` 和
`packaging/supply-chain/s2c2f-l1-l2.json`；共覆盖 65 条活动 OSPS 控制项（2 条已退役 ID 不计）。
其中 `platform-managed` 项依赖 GitHub 仓库设置，`external-manual` 项依赖账号安全设置，
`partial`/`not-applicable` 项保留明确 gap；这些状态不是“认证通过”的同义词。

NIST SSDF v1.1 的 19 条实践、42 条任务证据见
`packaging/security/ssdf-800-218-v1.1.json`，使用说明见 [ssdf.md](ssdf.md)。当前实践层
11 条为 `enforced`、8 条为 `external-manual`；任务层 30 条为 `enforced`、12 条为
`external-manual`，没有 `partial`。官方表 URL、SHA-256 与任务标题均被门禁校验；
组织职责不会被自动化证据冒充为人工事实。
