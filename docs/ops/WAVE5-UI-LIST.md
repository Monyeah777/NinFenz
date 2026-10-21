# wave5 UI 清单（e=ui，10 条转人工）

| ID | 判词 | 手册要求（要点） | 人工动作 | 完成自证 |
|---|---|---|---|---|
| BR-01 | FAIL | 默认分支禁止直推 | Settings → Branches 勾选 Require a pull request | API branches/main protected=true |
| BR-02 | FAIL | 必检项勾选 | Require status checks 勾 gate / internal-links-404-fail / pr-title-conventional | 同上，截图 |
| BR-03 | FAIL | 单人现实配置 | approvals=0 + 不允许 bypass + 要求对话解决 | 同上，截图 |
| BR-06 | UNKNOWN | 2FA 开启 | 账号 Settings 开 2FA | 设置页显示 Enabled |
| CW-09 | FAIL | 机器人评审 | 安装 reviewdog/CodeRabbit App（可选） | PR 上有 bot 评论 |
| MT-07 | 未做 | OpenSSF Badge 申报 | 注册项目并逐条填表 | badge 页面 URL |
| RL-03 | FAIL | Release 与 tag 对应 | 发一次 tag（release.yml 已配置） | /releases 非空 |
| RP-01 | PASS(实测) | About 三项 | 已由 main 设置，复核即可 | API description/homepage/topics |
| RP-02 | 部分 | 徽章真实性 | 保留 ci-verify 真徽章；Glama 不作治理证据 | README 徽章指向 |
| RP-03 | FAIL | Discussions 开启 | Settings → Features 勾 Discussions | has_discussions=true |
| RP-04 | 部分 | Wiki 关闭 | Settings → Features 取消 Wiki | has_wiki=false |

说明：BR-01/02/03、BR-06、RP-03/04 无法由 API 写入（需要 Web 或账号权限），其余为复核类。逐项操作步骤见 docs/ops/manual-actions.md。
