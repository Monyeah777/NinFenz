# NIST SSDF v1.1 作用域证据

> 标准：NIST SP 800-218, Secure Software Development Framework v1.1。
> 这是内部作用域证据，不是 NIST 认证，也不表示每项组织职责都由独立的第二人执行。

## 覆盖范围

机读矩阵按 NIST 官方 SSDF 表覆盖 19 条实践、42 条任务：

- PO.1–PO.5：安全需求、职责、工具链、组件准入与开发环境。
- PS.1–PS.3：代码保护、发布完整性与发布归档。
- PW.1–PW.9：设计、第三方组件、编码、构建、审查、测试与安全默认值。
- RV.1–RV.3：漏洞识别、评估修复与根因分析。

官方表 URL、SHA-256 与复核日期固定在同一矩阵中；任务 ID、标题、归属实践和完整性由
`ssdf_policy.py` 校验。实践状态不是手写汇总，而是由任务状态派生：

- 实践层：11 条 `enforced`、8 条 `external-manual`；
- 任务层：30 条 `enforced`、12 条 `external-manual`。

没有 `partial`；任何任务或实践退回 `partial` 都会使门禁失败。

## 外部人工证据

以下职责无法由单仓库克隆真实证明，因此保持 `external-manual`：

- PO.2.2：角色培训、熟练度复核与人员记录。
- PO.2.3：管理层或授权负责人的安全开发承诺。
- PO.2.1：角色与职责的周期性复核记录。
- PO.5.1：开发、构建、测试与分发环境的隔离证据。
- PO.5.2：开发终端加固与补丁状态。
- PS.1.1：GitHub 分支保护、账户会话与恢复配置。
- PS.3.1：发布归档位置、保留期限、访问控制与恢复演练。
- PW.2.1：独立合格设计审查人。
- PW.7.2：每个变更集的独立人工代码审查与问题分诊。
- PW.8.2：测试问题的工单分诊与修复记录。
- RV.3.2：跨时间的根因趋势复审连续性。
- RV.3.4：根因对应的 SDLC 变更或显式不改决定。

这些项不得用机器人自审、第二个身份或伪造审批替代。仓库内自动化证据可以支持控制，
但不能升级为外部人工事实。

## 漏洞响应闭环

`results/supply-chain/vuln-disposition.json` 是 RV 机读台账：

- 明确声明“不声称没有漏洞”，空台账不等于安全。
- 固定 Critical/High/Medium/Low 响应 SLA。
- 每条 finding 必须登记来源、发现日期、受影响版本、可利用性、影响和证据。
- `affected` 或 `under_investigation` 必须给出处置 action，并阻断发布。
- `fixed` 必须有修复版本、根因、同类变体复审、已有回归测试和对应 OpenVEX statement。
- `not_affected` 必须有 justification、impact statement 和对应 OpenVEX statement。
- 台账必须包含有日期、频次、模式、SDLC 行动与回归测试的根因复审记录。

OpenVEX 由 `python scripts/generate_vex.py --write` 从同一台账确定性生成。

## 判据

```bash
python scripts/ssdf_policy.py
python -m pytest desktop/tests/test_ssdf_policy.py -q
python scripts/generate_vex.py --check
```

`verify_report` 将 SSDF 与 ASVS、工作流、供应链和代码门禁一起聚合成机器可读报告。
本矩阵是内部作用域证据，不构成 NIST 认证；`external-manual` 不会被自动化绿数替代。
