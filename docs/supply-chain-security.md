# 供应链安全与发布验证

> 最后更新：2026-10-26

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
| `ninfenz-<version>.payload-manifest.json` | 逐文件 SHA-256 与聚合树摘要 |
| `SHA256SUMS` | 所有发布文件的完整性清单 |
| `release-metadata.json` | 源提交、可复现结论、SBOM 和工件映射 |

构建器对同一源树连续构建两次，tarball 字节不同即失败。tar 成员顺序、权限、uid/gid、mtime、
gzip mtime 和 OS 字节均被归一；payload 清单的 `generated_at` 取源提交时间或显式
`SOURCE_DATE_EPOCH`，不读取墙钟。

## SLSA Build L2 流水线

`.github/workflows/npm-publish.yml` 的 tag/手动发布路径执行：

1. GitHub 托管 runner 从不可变提交构建；
2. 两次构建逐字节比较；
3. 生成 CycloneDX、SPDX、payload 清单与 checksums；
4. 使用 GitHub OIDC 的 `actions/attest-build-provenance` 对 tarball 与 SBOM 生成签名来源证明；
5. 只有 build 与 attest 都成功，才允许发布 npm 和上传 GitHub Release 资产。

结论边界：**流水线具备 Build L2 所需的托管构建和认证来源证明；在真实 tag 或手动 attest
运行成功之前，仓库不声称已经取得某次发布的 SLSA 等级证明。**

## 消费者验证

下载 Release 中的五个工件后，在包含这些文件的目录执行：

```bash
sha256sum -c SHA256SUMS
gh attestation verify ninfenz-<version>.tgz --repo Monyeah777/NinFenz
gh attestation verify ninfenz-<version>.cdx.json --repo Monyeah777/NinFenz
gh attestation verify ninfenz-<version>.spdx3.json --repo Monyeah777/NinFenz
```

成功输出必须把 subject digest 绑定到同一次 GitHub Actions 构建，签发身份来自本仓库的
OIDC workflow。摘要相同但没有有效 attestation，不等于来源已经认证。

npm registry 自身也会保存 npm provenance。可在包页面查看，或通过公开 registry 的
provenance API 核验；GitHub attestation 与 npm provenance 是两条独立验证面。

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

## 漏洞与事故响应

漏洞报告只走 [GitHub Security Advisories](https://github.com/Monyeah777/NinFenz/security/advisories/new)。
确认后按 `SECURITY.md` 的优先级修复；修复版本携带新的 SBOM、checksums 和 attestation。
对已知恶意版本，维护者停止发布、撤销受影响分发、在 GitHub Advisory 公布受影响版本与修复版本，
并把供应商登记改为 `prohibited` 或 `restricted`，直到替代版本通过验证。

## 标准证据边界

OSPS Baseline L1/L2 与 S2C2F L1/L2 的逐项证据见
`packaging/supply-chain/osps-l1-l2.json` 和 `packaging/supply-chain/s2c2f-l1-l2.json`。
其中 `platform-managed` 项依赖 GitHub 仓库设置，`external-manual` 项依赖账号安全设置，
`partial`/`not-applicable` 项保留明确 gap；这些状态不是“认证通过”的同义词。
