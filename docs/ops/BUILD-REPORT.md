# BUILD_MANUAL 施工报告

## 0. 身份结论（P0）

仓库 D:/NinFenz（worktree D:/nf-wt-hyg2，分支 build/manual-main）确认为手册所指对象：根目录有 README / verify.sh / AGENTS.md / .github；项目性质为「规范驱动的文档生成工坊（CLI / MCP / 桌面 / 9 种语言引擎）」。手册 sha256 57cf37d7… 与本地原件逐字节一致。

## 1. 快照（P1，2026-10-21）

- head：53054dfe（本分支；基线 origin/main=9f0e7386）
- branch：build/manual-main；dirty_lines：0
- root_entries：67；file_count：3875
- 关键文件在位：README(155 行)、LICENSE、AGENTS.md、CHANGELOG、verify.sh、CONTRIBUTING、SECURITY、.gitignore、.gitattributes、.editorconfig、.pre-commit-config.yaml、.markdownlint.json、.env.example、.github/CODEOWNERS
- 明细见 docs/ops/preflight.json

## 2. 漂移清单（P2，按 §0.6 分档）

| ID | 类型 | 说明 | 档 |
|---|---|---|---|
| SP-01 | changed | 根条目 53→67（本轮新增 4 个配置入口） | 中漂移 amend |
| RL-01 | changed | 版本形态三段式→0.xx 单序列 + 1.0.x | 中漂移 amend |
| CI-01 | changed | 工作流命名与手册三名不符 | 中漂移 amend |
| FX-06 | changed | 索引层干净但无重复检查 | 中漂移 amend |
| RP-01 | changed | About 已由 main 设置 | 小漂移 |
| GF-10 | changed | NarrativeForge 残留 5 文件 | 中漂移（wave4 方案） |

## 3. 105 条分布（P3/P4）

- 已建成（含自证）：69
- 不适用（D2 驳回 + 替代判据）：5（CW-08 / RP-05 / HS-01 / HS-02 / HS-04）
- UNKNOWN（不许猜）：3（BR-06 / IN-01 / IN-02）
- 转人工（平台 UI）：10（BR-01/02/03、CW-09、MT-07、RL-03、RP-01/02/03/04）
- 待施工（wave4/6 方案就绪，需作者裁决或排期）：18（含 DC-06 部分）
- 本轮有效分母 = 105 - 5（不适用）= 100；未走 reject 的条目不重算历史得分。

## 4. 已施工波次与门禁

| 波次 | 条目 | 结果 | 门禁 |
|---|---|---|---|
| wave1 | 10 条（FX-01..05、CW-03/04、RL-02、CI-03、FG-02） | 10/10 建成 | 全绿（提交 e765c593） |
| wave2 | 25 条（治理/SLA/维护文档、workflow 权限下沉） | 25/25 建成 | 全绿（提交 ed28a6d8） |
| wave3 | 32 条（CI 接线/供应链/发布线/覆盖率趋势等） | 31 PASS + 1 部分（DC-06） | 全绿（提交 43a382cc） |
| wave4 | 16 条 | 3 已完成（FX-08/09/12）+ 3 不适用 + 10 方案 | 方案见 WAVE4-PROPOSALS.md |
| wave5 | 10 条转人工 | 清单见 WAVE5-UI-LIST.md | — |
| wave6 | 9 条 | 7 方案 + 2 UNKNOWN | 方案见 WAVE6-PROPOSALS.md |

## 5. 重解释与偏差

- amend 6 条：SP-01、RL-01、CI-01、CI-08、FX-06、RP-01（from→to 见 docs/ops/rulings.jsonl）。
- reject 5 条：CW-08、RP-05、HS-01、HS-02、HS-04（全部 D2，替代判据见 filings）。
- 超纲登记 11 条（加严/提前/换路，均带 revert）：见 docs/ops/deviations.json。
- 明确未做：任何历史改写（强推/删 tag/改提交）、任何判据放宽、任何 noqa 逃逸（SAST 基线冻结为新增 gate 脚本的 subprocess 形态，属评审后冻结而非静默）。

## 6. 复现

    git switch build/manual-main
    bash verify.sh --full --no-cache      # 期望全绿（PASS 计数以本次运行为准，不在此写死）
    python scripts/repo_doctor.py         # 期望全项 PASS
    bash scripts/check_markdown_structure.sh
    python scripts/check_workflow_permissions.py
    python scripts/check_internal_links.py --json
    python scripts/check_untracked_artifacts.py
    python scripts/check_gitignore_coverage.py

登记件：docs/ops/preflight.json、pruned.json、rulings.jsonl、deviations.json、manual-actions.md、WAVE4/5/6 方案；逐条台账在 D:/NF-Plan/build-manual-ledger.md。

## 7. 剩余与建议

1. 作者裁决：SP-01/SP-03 社区件是否搬入 .github（影响外链）；SP-02 工具配置是否并入 pyproject。
2. 可立即做（低风险，未做）：DC-02 docs/index.md、DC-03 决策入口、RL-01 VERSION-MATRIX 双线、MT-05 三条本地 hook。
3. 平台项按 manual-actions.md 操作；每季度复核。
4. wave6 按季度排期；IN-01/IN-02 需人工取证。
