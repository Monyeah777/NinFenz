# 需人工配合清单（平台设置 / 账号级 / 无 API 可读）

> 这些条目 agent 无法代替：需要 GitHub Web 设置、账号安全设置，或需登录后人工判读。
> 每项给出：要做什么 / 在哪做 / 为什么 / 做完如何自证。

## A. 分支保护（BR-01 / BR-02 / BR-03）

1. Settings → Branches → Add branch protection rule，Branch name pattern 填 main。
2. 勾选 Require a pull request before merging（BR-01：禁止直推）。
3. 勾选 Require status checks to pass before merging，把 gate（ci-verify 的 gate job）、internal-links-404-fail、pr-title-conventional 加为必检（BR-02）。
4. 单人现实配置（BR-03）：Require approvals 填 0（无第二人可审），但保留 Do not allow bypassing the above settings；并勾选 Require conversation resolution before merging。
5. 自证：GET /repos/Monyeah777/NinFenz/branches/main 返回 protected: true；或网页截图 Branch protection rules 面板。

## B. 账号安全（BR-06）

1. Settings → Password and authentication 开启 2FA（TOTP 或安全密钥），恢复码离线保存。
2. 自证：个人设置页 2FA 状态为 Enabled。

## C. 仓库呈现（RP-01 / RP-02 / RP-03 / RP-04）

1. About（RP-01）已由 main 设置，复核：description 非空、homepage=ninfenz.dev、topics ≥8。
2. 徽章（RP-02）：保留 ci-verify 真运行徽章；Glama 分为外部评分，不作为治理证据（语义见 docs/meta/SCORECARD-SEMANTICS.md）。
3. Discussions（RP-03）：Settings → Features 勾选 Discussions 并建 Ideas/Q&A 分类；自证 has_discussions: true。
4. Wiki（RP-04）：Settings → Features 取消 Wiki，避免与 docs/ 双写；自证 has_wiki: false。

## D. 供应链平台开关（SC-06 / SC-07 / SC-11）

1. Settings → Code security 开启 Dependabot alerts 与 Dependabot security updates（SC-06 的告警面；工作流侧处置核对已就位）。
2. 发布后在 Release 页确认 Attestations 可见；用 gh attestation verify <file> --repo Monyeah777/NinFenz 自证（SC-07）。
3. SLSA 等级对外定位（SC-11）需人工确认措辞，仓内能力以 protocol/CONFORMANCE 为准。

## E. 外部评分与申报（MT-07）

1. OpenSSF Best Practices Badge：需人工注册项目并逐条填表（agent 不代填）。
2. Scorecard 结果仅作过程评分引用，不得替代 verify 结论。

## F. 发布视图（RL-03）

1. 首次发布后 Releases 页应出现与 tag 对应的 Release（release.yml 已配置自动 notes 与产物）。
2. 自证：GET /repos/Monyeah777/NinFenz/releases 非空且与 tag 一一对应。

## G. 协作自动化（CW-09）

1. 若要接机器人评审：安装 reviewdog 或 CodeRabbit App 并限定 pull_request 事件；单人仓库收益低，可延后。

## 未取证项（UNKNOWN）

- IN-01 Dependents 面板：需登录 Web 查看，API 不可读。
- IN-02 Traffic 分析：需 admin 权限，API 不暴露。
- BR-06 2FA：API 不可读，见 B 节。

## 复查节奏

- 平台项每季度复核一次；复核结果追加到本文件末尾（日期 + 状态 + 截图/URL）。
