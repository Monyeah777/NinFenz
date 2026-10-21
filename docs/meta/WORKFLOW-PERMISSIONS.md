# workflow 权限台账（BR-05）

> 判据：顶层默认只读；写权限按 job 单独授予并说明原因。机器判据：`scripts/check_workflow_permissions.py`（顶层出现 write 或缺顶层 permissions 即 FAIL）。

## 顶层权限（全部只读）

| workflow | 顶层 permissions |
|---|---|
| .github/workflows/ci-verify.yml | contents: read |
| .github/workflows/coverage.yml | contents: read |
| .github/workflows/cross-lang.yml | contents: read |
| .github/workflows/cross-platform.yml | contents: read |
| .github/workflows/dependency-audit.yml | contents: read |
| .github/workflows/docker-nfal.yml | contents: read |
| .github/workflows/e2e-desktop.yml | contents: read |
| .github/workflows/external-links.yml | contents: read |
| .github/workflows/gitee-poll.yml | contents: read   # 顶默认只读 |
| .github/workflows/library-ingest.yml | contents: read   # 顶默认只读 |
| .github/workflows/lint.yml | contents: read |
| .github/workflows/net-engine.yml | contents: read |
| .github/workflows/net-probes.yml | contents: read |
| .github/workflows/npm-publish.yml | contents: read   # 顶默认只读；id-token 下发到 publish job（provenance 必需） |
| .github/workflows/release-gate.yml | contents: read |
| .github/workflows/rust-parity.yml | contents: read |
| .github/workflows/sast.yml | contents: read |
| .github/workflows/scorecard.yml | read-all |

## job 级写权限（逐条给原因）

| workflow | job | 授予 | 为什么需要 |
|---|---|---|---|
| .github/workflows/gitee-poll.yml | poll | contents: write   # 入库要 git push（唯一写点） | 投稿入库要 push 回仓（contents: write） |
| .github/workflows/library-ingest.yml | ingest | contents: write   # 入库要 push | 入库要 push；回评并关闭 Issue（issues: write） |
| .github/workflows/library-ingest.yml | ingest | issues: write     # 回评并关闭 Issue | 入库要 push；回评并关闭 Issue（issues: write） |
| .github/workflows/npm-publish.yml | publish | id-token: write | npm trusted publishing / provenance 用 OIDC 短期凭据（id-token） |
| .github/workflows/npm-publish.yml | publish-github-packages | packages: write          # 发布包到 GitHub Packages 必需 | 见该 workflow 注释 |
| .github/workflows/scorecard.yml | analysis | security-events: write     # 上传 SARIF | 上传 SARIF（security-events: write）+ publish_results（id-token） |
| .github/workflows/scorecard.yml | analysis | id-token: write           # publish_results 需要 OIDC | 上传 SARIF（security-events: write）+ publish_results（id-token） |

## 越权尝试

- 本机无法构造「用只读 token 写仓库」的真实越权请求（需要 Actions runner 与平台侧审计）。
- 替代取证：本文件 + `check_workflow_permissions.py` 的静态断言；平台上真实越权被拒的记录待人工在 Actions 日志中取证（UNKNOWN）。
- 已知结构性事实：分支保护未启用（BR-01~03 待作者），因此 token 写权限目前没有第二道平台闸门拦截——该缺口已登记在 docs/meta/UNVERIFIED.md。
