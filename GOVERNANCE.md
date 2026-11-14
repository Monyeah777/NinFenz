# 开源治理（GOVERNANCE）

> ⛔ 操作指令：本件是开源治理/发布/废弃政策的入口；机读登记 `protocol/legal.json` 的 `oss_governance` 段，判据 `desktop/tests/test_legal_contract.py`。改治理流程须同步登记，否则判据红。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §3A D13（P1 盲区 BL-10）
> 纪律：单人维护事实如实写；不冒充社区治理、不声称合规。

## 角色与决策

- 维护者：`MAINTAINERS.md`（当前为单维护者 + 作者裁决制）。
- 决策记录：`decisions/`（公开仓只留模板/索引；真实决策正文按 `ADR-0000` 留私有档案）。
- 行为准则：`CODE_OF_CONDUCT.md`（私密报告通道）；安全报告：`SECURITY.md`（GitHub Security Advisories 私密通道）。
- 贡献流程：`CONTRIBUTING.md`（Conventional Commits + 分支策略 + 提交钩子）。
- 支持：`SUPPORT.md`（不自称 SLA）。

## 发布

- 发布顺序与冻结链：`docs/release.md`（conformance → approve → receipts；版本面三处：CHANGELOG / VERSION-MATRIX / README）。
- 版本语义：SemVer 2.0——破坏性变更走 major 并给迁移说明；变更日志遵循 Keep a Changelog（`CHANGELOG.md`）。
- 发布是**质量展示事件**：`bash verify.sh --full` 全绿 + 冻结链可复算才发；未跑的面不得写成全绿。

## 废弃

- 资产/模块：`deprecate`/`restore`/`retired` 生命周期（实现 `desktop/src/core/module_lifecycle.py`；门禁 check24 拒 deprecated/retired 被引用）。
- 文档/协议：Supersede-only（RPC 头 + supersede 链）；旧件不删，标 `superseded`/`retired` 并指向替代件。
- 兼容窗口：以「版本面 + 迁移说明」表达（逻辑口径），不写日历承诺。

## 评分卡与安全

- OpenSSF Scorecard：`.github/workflows/scorecard.yml`（**CI-only**；本机不跑，结果在 GitHub 面板可见；本仓不冒充已评分）。
- 依赖审计：`.github/workflows/dependency-audit.yml` + 固定版本清单；action 钉 commit SHA（`desktop/tests/test_ci_supply_chain.py` 判据）。
- 供应链/来源：SBOM 与 interop 导出面（`results/ccos/sbom.json`、`results/interop/*`）。

## 不承诺

- 不承诺社区规模、响应 SLA 或认证；单维护者事实与残余风险在 `SUPPORT.md` 与 `docs/legal/LEGAL.md` 明示。
