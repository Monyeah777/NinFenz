# 获取支持（SUPPORT）

> 本仓**离线、单人维护、无 SLA**：下面写的是「怎么最快拿到答案」与「什么不该开 Issue」，不是响应承诺。
> 口径与机器面同源：入口配置 `.github/ISSUE_TEMPLATE/config.yml`（**空白 Issue 已关**）、安全通道
> `SECURITY.md`、投稿闸门 `library/intake.json`。与表单/文档的一致性由判据守住（`desktop/tests/test_support_contract.py`）。

## 先自查（多数问题在这一步解决）

1. **先搜**：在 Issues 里搜关键词，再翻 [CHANGELOG.md](CHANGELOG.md) 看是否已在近版修好——已修的重复报告会被直接关闭并指回原条目。
2. **先看**：`README.md`「五分钟快速开始」；`nf doctor` 看环境自检；`nf help <子命令>` 看命令用法；编辑器接入见 `docs/lsp.md`。
3. **先缩小**：把复现压到「一条命令 / 20 行以内片段」——能复跑比描述详细更重要。

## 去哪问（按面走通道）

| 你的事 | 通道 | 说明 |
|---|---|---|
| 缺陷 | `.github/ISSUE_TEMPLATE/bug_report.yml` | 结构化表单；环境 / 复现 / 期望 / 实际按栏填 |
| 功能请求 | `.github/ISSUE_TEMPLATE/feature_request.yml` | B1 五问逐栏；先看 `docs/meta/ROADMAP.md` 的路线与版本 |
| 安全漏洞 / 越权 / 凭据泄露 | [SECURITY.md](SECURITY.md) 的私密通道（GitHub Security Advisories） | **不要开公开 Issue**——公开即视为已泄露 |
| 行为准则举报 / 申诉 | 同一私密通道（见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)） | 保密处理；申诉 14 天内一次，由未参与原处置的维护者复核 |
| 内容 / 领域包投稿 | 投稿表单 + `CONTRIBUTING.md` §4.4；闸门真源 = `library/intake.json` | 仅作者本人自投；通道模式以声明件为准 |

> 空白 Issue 已关：上表之外的问题没有「随便开一个空 Issue」的口子——选择页的四条分流入口就是入口面。
> 拿不准属于哪一类时，**按最接近的一类走**，评审会改判——不要因为不确定就不报。

**安全报告的私密直达**：`https://github.com/Monyeah777/NinFenz/security/advisories/new`
（等价路径：GitHub 仓库页 → Security → Report a vulnerability）。这是唯一不公开的入口；
公开 Issue 一旦带上复现细节，按「已泄露」处理。

## 提 Issue 前自检（四项，缺一项会被要求补）

- [ ] 已搜索已有 Issue 与 `CHANGELOG.md`，确认不是重复
- [ ] 这不是安全问题（安全问题走 `SECURITY.md` 私密通道）
- [ ] 日志 / 截图 / 附件已脱敏（无 token、密钥、私密路径）；**凭据出现在公开 Issue 即视为已泄露**
- [ ] 本条只报一个缺陷（多现象分开报）；复现步骤能被他人独立复跑

## 怎么问（可核，不是「说清楚点」）

- **最小复现三件套**：①一条可复跑命令或 20 行以内片段；②期望与实际的原文两段；③版本三元组
  `nf --version` + verify 基线（`protocol/repo_stats.json` 的 verify_version）+ 内容线 tag。
- **一次只报一件**：一条 Issue 只报一个缺陷或一个能力；混报会让「修好没」无法判定。
- **结论可独立验证**：能给判据或命令输出的就贴输出（例如 `python scripts/precheck.py` 的末行），别只写形容词。

## 之后会发生什么

- **不静默丢弃**：不承诺时限，但「受理与否」必有明确回复；**每个 Issue 关闭前必有状态位**
  （fixed / duplicate / needs-info / wontfix / out-of-scope）与一句理由。
- 受理后按严重程度排序修复；修复随常规提交入仓，并在 `CHANGELOG.md` 以结果形态记账（不含复现细节）。
- 被拒 / 被关的会写明依据（对照哪条准则 / 哪条验收判据）；不服走上面同一私密通道的申诉。

## 支持边界（诚实声明）

本仓不提供 SLA、不承诺响应时限，也不对投稿内容的正确性或版权作担保（授权链见 [CONTRIBUTING.md](CONTRIBUTING.md) §7）。
上游依赖与标准组织的问题请找对应上游；本仓对第三方项目不作背书。
