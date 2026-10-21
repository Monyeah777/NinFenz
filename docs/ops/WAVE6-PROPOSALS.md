# wave6 方案（长期运营类，9 条）

> 本轮只出方案，不新增平台申报/外部审计（§3.5：对外承诺须作者拍板）。
> 已完成：无（CW-07 属平台设置/工作流，本轮已补 stale 工作流？—— 未补，见下）。
> 未取证：IN-01 / IN-02（需登录 Web，见 manual-actions.md）。

## CW-07 Stale Bot（FAIL）

- 现状：无 stale 工作流；单人仓库 Issue/PR 量小，误关风险低但可积压。
- 方案：用 actions/stale v9（SHA 锁），只对 Issue 生效：30 天无活动打 stale 标签，再 14 天关闭；**不**碰 PR（避免误关长期分支）；排除 label: pinned/security。
- 前置：先确认 Issue 数 <50（当前远低于），否则先用 label 人工归档。
- 可逆：删 .github/workflows/stale.yml。
- 需作者裁决：关闭前是否要通知（默认发一条评论）。

## SC-11 SLSA 等级定位（部分）

- 现状：check41（构建隔离）+ check42（不可伪造 provenance）在位；cosign 外锚缺位时报 WARN。
- 方案：在 protocol/CONFORMANCE 已声明能力；对外表述统一为「SLSA L3 构建隔离 + 不可伪造 provenance（外锚 cosign 缺位时如实标注 WARN）」，不写「已认证」。
- 可逆：纯文档措辞，revert 单行。

## SC-12 数字资产来源（C2PA，未做）

- 现状：仓内数字资产为文本/JSON，无 C2PA 容器格式。
- 方案：对发布物（npm tarball）附加 manifest 摘要 + provenance attestation 即满足「来源可验」；不引入 C2PA SDK（对纯文本仓是过度）。
- 结论：reject D2（前提不成立：无 C2PA 资产），替代 = SC-07/SC-09 的 attestation 链。

## MT-06 CHAOSS 指标（未做）

- 方案：先做「可自动取数的 5 项」：commit cadence（RELEASE-CADENCE 已有）、issue 响应时长（GitHub API）、PR 合并时长、贡献者数、release 频率。脚本 scripts/chaoss_snapshot.py --json，月更写入 results/audit/。
- 风险：单人项目大部分指标恒为 1/0，易被误读；文档必须写明口径。
- 可逆：删脚本与月更工作流。

## MT-08 第三方审计（未做）

- 方案：不主动安排（§3.5 对外承诺）；保留「外部实测线」封存状态，作者显式触发时按 E1/E2 清单执行。
- 结论：保持未做，属作者决策项。

## MT-09 提交者集中度（未做）

- 现状：提交者 1 人（git shortlog 实测）。
- 方案：不制造虚假多样性；在 GOVERNANCE.md 写明「单人维护」事实与晋升触发条件（已写）。指标层面记录 shortlog 到 repo-health 月报即可。
- 可逆：删月报步骤。

## IN-01 Dependents（UNKNOWN）

- 需人工：GitHub 仓页 Insights → Dependency graph → Dependents（需登录）。记录 dependents 数与代表性项目；季度复查。

## IN-02 Traffic（UNKNOWN）

- 需人工：Insights → Traffic（需 admin）。记录 14 天 views/clones 与来源；为「唯一官方仓库」声明提供事实支撑。

## IN-03 变更热点分析（未做）

- 现状：scripts/hotspot_profile.py 是性能热点取数（cProfile/py-spy），不是变更热点。
- 方案：新增 scripts/change_hotspot.py：git log --numstat 统计近 90 天改动频次 × 文件，输出 top20；接入 repo-health 月更，供重构排期。
- 可逆：删脚本与工作流步。
- 备注：与性能热点分开命名，禁止混用。

## 排期建议

季度节奏：CW-07（Q1）→ MT-06/MT-09（Q1-Q2）→ IN-03（Q2）→ IN-01/IN-02 人工季报 → SC-12/MT-08 由作者决定是否启动。
