---
id: AUD-0001
title: W4 审计/验收协议化 —— 自审
date: 2026-09-16
scope: 长期计划 W4：审计报告的格式与判据升为规范件；审计内容仍属说明件（分层消解既有冲突）
verdict: pass
auditor: 本轮执行者
subjects:
  - protocol/audit.json:cce69546ca42d2d5fb3785a22d51e8cd6c49229d8d2f35c4abb1d2b9ee0a91b3
  - desktop/src/core/audit.py:b316c77fb2fa718a105af8c51a234c435847077f71309adbbf5f0d6bb25d2afb
  - desktop/src/core/audit_legacy.py:dda2800fa2a8760ceffdb7bb719cf05557222ac7161bb2a4a2bfb631665f4a01
  - desktop/src/core/audit_subject.py:1cb262ba9db84c9af4e9ec046e82139ca5c65da25f34f77b9aa3d38f31e00f43
  - desktop/tests/test_audit.py:63bf6c8407ff5a7b51bc25cb9d3a3b833bac372b68b56f9b3d9a7bdf140a7192
  - desktop/tests/test_audit_rebind.py:63066cb91114aef5bceaf4fa54d392ec31210d6c141d81345eda122e7055c2b1
accepted_by: 作者
accepted_at: 2026-09-16
---
> 重审（2026-10-30）：全仓审计口径复核：显式 legacy 清单、subjects 根内解析、Path 参数闸门、惰性导入与 manifest 可复算

> 重审（2026-10-14）：收口：长行/导入序/静默跳过理由/风格基线重冻（评审）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI）：重审并更新 digest 口径机器化，替换手搓脚本


> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

## 一、审什么

W4 的两件新规：`protocol/audit.json`（审计该怎么写的约束）与 `desktop/src/core/audit.py`（判据实现）。
本报告的 `subjects` 把这两件的 sha256 绑进结论——**任一被审对象再被改动，本审计立即失效**，必须重审。

## 二、结论（verdict = pass）

1. 审计**内容**（某时刻查到了什么）仍属说明件：`results/audit/**` 未被加入回执覆盖面，
   符合 `protocol/normative.json`「说明件不得被回执锚定」；
2. 审计**格式与判据**已升为规范件：`protocol/audit.json` 进入回执覆盖面；
3. 结论绑定 digest 已可机检：对象改动 → `nf audit verify` 报「旧审计失效」；
4. 验收签收双要素（`accepted_by` + `accepted_at`）已判据化；
5. 存量 11 件无审计头的审计件按 **WARN** 挂账（不判死），符合"先可数、再逐回合收"。
6. legacy 豁免只认 `protocol/audit.json::legacy_records.paths` 的显式登记；未登记件缺
   frontmatter/id 一律 FAIL，不能靠删除字段降级。

## 三、未覆盖（如实挂账）

- **基线数字可复算**只写进 `rules`，尚未做成常驻断言（属断言表可搬运的形状类判据，留给下一波）；
- 存量 11 件 legacy 审计头的回填不执行（每件都要绑当时的被审对象 digest，属历史时点事实，
  不能事后补 digest——**永久保持 legacy + WARN**，而不是补一个假的过去状态）。清单失效
  （新增件称 legacy、历史件补齐完整头后仍留清单）由 `nf audit verify` 判 FAIL。
