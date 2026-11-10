<!--
PR 模板（NF）——与 `.github/ISSUE_TEMPLATE/` 的两个表单**同构**：先自检、再给可核证据。

纪律：**一个 PR 只做一件事**。混装改动会让评审无法判断「哪一处引发了哪一处变化」，
也会让回滚变成选择性手术。宁可开两个 PR，不要开一个「顺便」。

判据：`desktop/tests/test_pr_template_contract.py` 逐条核本文件——缺段 / 悬空路径 / 域勾选丢失即红。
-->

## 本 PR 只做一件事（一句话声明）

> 本 PR 只做一件事：<一句可核的话，例：把某文件的某段从 A 口径改成 B 口径>

声明与内容不符（顺手带了别的改动）时，评审会要求拆 PR——这不是形式主义：
一个 PR 一件事，回滚与归因才成立。拆不开 = 说明改动本身还没想清。

## 改动域（只勾真实改到的面，可多勾）

- [ ] 协议层（01–07 / 08 / 09 方案）——是否触发 01 §7 V2 bump：是 / 否
- [ ] 代码层（scripts/ · desktop/ · tui/ · engine/ · integrations/ · site/）
      代码面清单唯一真源 = `library/intake.json` 的 `submission.code_surfaces`；本行只是它的投影，
      **不得在此另写一份清单**（漂移即 verify check34 FAIL）。
- [ ] 社区领域包 `community/`（R1 包间禁互引 / R2 类别独占 / R3 装配契约）
- [ ] 工程治理（`docs/meta/ROADMAP.md` / `CHANGELOG.md` / `CONTRIBUTING.md` / `.github/` / `verify.sh`）

## 变更说明（问题 → 做法 → 影响面）

**问题**：（现在哪里不对、谁踩到？没有这一步，评审无法判断这次改动值不值得做。）

**做法**：（怎么改的、关键取舍；被否掉的替代做法一句话带过。）

**影响面**：（谁会被影响——CLI 用户 / 协议消费方 / 社区包 / 门禁与生成物；
有无行为变化、要不要迁移、不兼容面在哪里。）

## 可核验收（reviewer 能独立复跑，不是「我跑过了」）

| 命令 | 期望输出 |
|---|---|
| `bash verify.sh` | 全绿：0 FAIL（check 数与 PASS 基线以生成区为准，不手写） |
| `python scripts/precheck.py` | 闸门 23 · 全绿 |
| `python -m unittest desktop.tests.test_<你的判据模块>` | OK（N tests） |
| `python scripts/freshness_check.py --quiet` | 新鲜度：4 项 · 未过 0（freshness 4/4） |

- 守住这次改动的判据：`desktop/tests/test_<你的判据模块>.py`——它在什么输入下会变红？
  把这句话写出来；写不出来说明这次改动没有判据（评审会要求先补判据再合并）。
- 未验证面：写清没跑的平台 / 没覆盖的路径——可核性来自边界被写明，而不是被隐藏。
- 失败样本（可选）：贴一条「改前红、改后绿」的实际输出，比任何形容词都有说服力。

## 门禁自检（四项全勾才可合并）

- [ ] `bash verify.sh` 全绿（0 FAIL；WARN 须逐条说明为什么可接受）
- [ ] CHANGELOG 已更新——本仓**不手改** `CHANGELOG.md`：在 `changes/unreleased/` 落一条
      `type:` / `note:` 两行，发布收口由 `nf release` 归档
- [ ] 文档状态行已同步（`docs/meta/ROADMAP.md` 的当前状态与本次改动一致；无状态变化须写明理由）
- [ ] 生成物已重算（冻结链按 `CONTRIBUTING.md` 顺序整链跑完；freshness 4/4，见上表）

## 关联写法（Closes / Refs）

- 关单：`Closes #N`——合并即关，一个 PR 只关它**真正修好**的那一件
- 引用：`Refs #N`——只引用不关单（背景 / 后续 / 相关但未修）
- 无 Issue 时写「无关联 Issue」并说明为什么这次不需要（例：纯生成物重算、机械重绑）

DCO：提交须带 `Signed-off-by:`（`git commit -s`），条款见 `CONTRIBUTING.md` §7。
