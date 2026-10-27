# 维护者

| 角色 | 人 | 职责 |
|---|---|---|
| Owner / Maintainer | [@Monyeah777](https://github.com/Monyeah777) | 最终裁决、发布、协议与方向 |

- 维护者的裁决边界与质量准绳见 [STRATEGY.md](STRATEGY.md) 与 [AGENTS.md](AGENTS.md)。
- 行为准则的举报与申诉见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
- 当前为单人维护（审计 §11k 已如实记为「单人新仓的客观状态」）。

## 权限管理

- GitHub 写权限、发布权限和维护者角色只按最小权限授予；新增或提升权限必须有明确身份、业务
  理由、所需最小角色与预计期限。
- 每次权限变更须复核 MFA、所需 scope、是否可用更短期的 GitHub App / OIDC 凭据替代，以及撤销
  条件；不再需要的协作者权限和 token 应及时移除或轮换。
- 自动化不得使用个人 PAT 发布正式版本。发布使用 GitHub Actions 的短期 `GITHUB_TOKEN` / OIDC；
  需要外部 registry 凭据时只存为受保护环境和 repository secret，禁止写入仓库。
- 当前只有一名人类维护者，非作者审批与多人权限分离无法由自动化伪造；该边界在 OSPS 证据中
  保持 `external-manual`，直到真实第二名人类维护者参与复核。
