# 42 M5.6 · Release Checklist（tag 前逐项核验）

> 模板：tag vX.Y.Z 前逐项打勾；任何一项未过 = 不发布。

> **状态：清单仍现行使用（已于后续发布流程中参照执行）**——2026-11-13 修正两处**路径引用**（`VERSION-MATRIX.md` / `ROADMAP.md` 已归拢到 `docs/meta/`，原文裸名已失效）与一处时点表述；发布流程的**现行真源**=`docs/release.md`（本清单是它之前的逐项核验表）。Golden Master 项已于 2026-10-11 退役（见文末）。

- [ ] **变更全齐**：CHANGELOG 归档（[Unreleased] 内容迁至版本段并清空）+ `docs/meta/VERSION-MATRIX.md` 同步（版本×方案×能力行）。
- [ ] **audit 建档在**：docs_audit-<N>-vX.Y.md verdict 通过（含五维自评段）。
- [ ] **verify 全绿**：`bash verify.sh` 0 WARN 0 FAIL——**本模板不钉运行时计数**（check 数与 PASS 基线见 `nf stats --check` 生成区与 `quality_baseline.EXPECTED_*`；模板里钉死必漂，2026-09-30 实测此处曾停在 check1-32/PASS=51）。
- [ ] **覆盖率数字公示**：`bash scripts/coverage_summary.sh`（core ≥80%）。
- [ ] **判级器词表核验**：06 §11 无新增未定义强度词（必须/禁止/应/可之外）。
- [ ] **错误信息审计零缺失**：check27 R4 绿。
- [ ] **文档卫生**：doc_hygiene 标识/last-updated 常驻绿（指令类 100% + 零过期）。
- [ ] **双端同步**：README 版本块（§版本）✅ 已发布 + `docs/meta/ROADMAP.md` 状态行归位。
- [ ] **端壳线确认**：无端壳待办残留（L3 端壳线已永久退役，2026-09-09 作者裁决；见 docs/L3_FROZEN.md）。

## Golden Master 冻结（M5.6 + 批 C #5）——**已退役**

原项（tag 点产物快照：协议件 + `verify.sh` + `desktop/src/core/*.py` 的 sha256 清单 + `nf sig --verify` 指纹）
已于 2026-10-11 作者裁决退役：156 条清单 77 条失效、无门禁消费、曾泄漏进 npm 发布物。
清单与生成脚本已从仓库和 payload 排除表删除；tag 点不再产出该项。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（清单原稿） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 版本矩阵路径 | 裸名 `VERSION-MATRIX.md` | **`docs/meta/VERSION-MATRIX.md`**（已按架构分层归拢） |
| 路线图路径 | 裸名 `ROADMAP.md` | **`docs/meta/ROADMAP.md`** |
| 自动化体检 | 人工逐项 + 零散命令 | `nf release` 已可编排体检（`--plan` 只读 / `--freeze` 冻结链）；本清单仍作为 tag 前人工核验表 |
| 运行时计数 | 文中提醒「不钉死」（曾停在 check1-32/PASS=51） | `bash verify.sh --checks-only` 实跑为准（2026-11-13 实测 PASS=75/WARN=2/FAIL=0）；`nf stats --check` 输出 check1-42 常驻 |
| 版本真源 | VERSION-MATRIX + CHANGELOG | `pyproject.toml` 的 `version`（2026-11-13 实读 1.0.5）与 `protocol/repo_stats.json`（质量基线）；VERSION-MATRIX 仍须同步 |
| Golden Master | 已退役 | **不变**（tag 点不再产出） |

> 本表只作导航，不替代实测；发布流程细节以 `docs/release.md` 为准。

## 复现与引用口径

```bash
python scripts/nf.py release --plan    # 有序发布计划（只读：命令/产出/判据）
python scripts/nf.py stats --check     # 质量基线自述数字实算（EXPECTED_CHECKS/EXPECTED_PASS）
bash verify.sh --checks-only           # 静态门禁现状（本清单第 3 项）
bash scripts/coverage_summary.sh       # 覆盖率门槛（本清单第 4 项）
```

- 引用本文时：清单 = **tag 前人工核验表**；自动化编排与发布真源 = `docs/release.md` + `nf release`。
- 路径核对：`docs/meta/VERSION-MATRIX.md` / `docs/meta/ROADMAP.md`（裸名已失效，勿再照抄旧写法）。
