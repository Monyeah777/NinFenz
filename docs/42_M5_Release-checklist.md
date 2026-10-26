# 42 M5.6 · Release Checklist（tag 前逐项核验 · 随下个 tag 首用）

> 模板：tag vX.Y.Z 前逐项打勾；任何一项未过 = 不发布。

- [ ] **变更全齐**：CHANGELOG 归档（[Unreleased] 内容迁至版本段并清空）+ VERSION-MATRIX 同步（版本×方案×能力行）。
- [ ] **audit 建档在**：docs_audit-<N>-vX.Y.md verdict 通过（含五维自评段）。
- [ ] **verify 全绿**：`bash verify.sh` 0 WARN 0 FAIL——**本模板不钉运行时计数**（check 数与 PASS 基线见 `nf stats --check` 生成区与 `quality_baseline.EXPECTED_*`；模板里钉死必漂，2026-09-30 实测此处曾停在 check1-32/PASS=51）。
- [ ] **覆盖率数字公示**：`bash scripts/coverage_summary.sh`（core ≥80%）。
- [ ] **判级器词表核验**：06 §11 无新增未定义强度词（必须/禁止/应/可之外）。
- [ ] **错误信息审计零缺失**：check27 R4 绿。
- [ ] **文档卫生**：doc_hygiene 标识/last-updated 常驻绿（指令类 100% + 零过期）。
- [ ] **双端同步**：README 版本块 ✅ 已发布 + ROADMAP 状态行归位。
- [ ] **端壳线确认**：无端壳待办残留（L3 端壳线已永久退役，2026-09-09 作者裁决；见 docs/L3_FROZEN.md）。

## Golden Master 冻结（M5.6 + 批 C #5）——**已退役**

原项（tag 点产物快照：协议件 + `verify.sh` + `desktop/src/core/*.py` 的 sha256 清单 + `nf sig --verify` 指纹）
已于 2026-10-11 作者裁决退役：156 条清单 77 条失效、无门禁消费、曾泄漏进 npm 发布物。
清单与生成脚本已从仓库和 payload 排除表删除；tag 点不再产出该项。
