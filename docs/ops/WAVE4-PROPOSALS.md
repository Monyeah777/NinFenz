# wave4 方案（结构搬迁与历史改写类，16 条）

> 本轮只出方案，不动目录与历史（§3.5：动历史/动结构前必须停问作者）。
> 已完成：FX-08 / FX-09 / FX-12（wave1 顺带落地，自证见台账）。
> 不适用：HS-01 / HS-02 / HS-04（D2 驳回，见 rulings.jsonl 与 pruned.json）。

## SP-01 根目录白名单（FAIL → 待裁决）

- 现状：根目录 67 条目（手册快照 53）；超白名单约 30 个。
- 方案：分两批搬迁，每批独立可回滚。
  - 批 1（零风险）：把非入口的规划/维护文档收进 docs/meta/；根级保留 README/LICENSE/AGENTS/STRATEGY/verify.sh 作为「入口例外」，并在 docs/meta/ROOT-MANIFEST.md 登记引用证据。
  - 批 2（需作者裁决）：社区件（CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/SUPPORT/MAINTAINERS）搬入 .github/ —— GitHub 认这些位置，但会让 5 个文件的现有外链失效。
- 前置：先建 docs/meta/ROOT-MANIFEST.md（白名单 + 例外清单 + 引用证据），再加 check_root_manifest.py 防回潮。
- 风险：外链失效（README/Issue 模板/第三方引用）；迁移必须同 PR 修引用并跑 docs-links。
- 可逆：全部为文件移动，git revert 单提交即可；不涉及历史改写。
- 需作者裁决：是/否（社区件是否搬入 .github）。

## SP-02 工具配置收纳（部分 → 待裁决）

- 现状：ruff.toml、REUSE.toml、glama.json、wrangler.jsonc 在根；pyproject.toml 未承载工具配置。
- 方案：把 ruff/pytest/mypy 配置并入 pyproject.toml 的 tool.* 段，删除 ruff.toml；编辑器类（.editorconfig）按 FX-12 保留在根。
- 风险：ruff.toml 是 ci-hygiene/pre-commit 的显式路径，迁移要同步三处引用。
- 可逆：恢复 ruff.toml + 删除 pyproject 段。

## SP-03 社区文件归位（FAIL → 需作者裁决）

- 同 SP-01 批 2；另需在 README 顶部加「社区件位置」一行说明。
- 需作者裁决：是/否。

## SP-04 规划文档归位（部分）

- 现状：docs/meta/ROADMAP.md 已在位；STRATEGY.md（最高层方向）仍在根。
- 方案：STRATEGY.md 保留根级（被 AGENTS.md 强制阅读链引用，属入口例外），在 ROOT-MANIFEST 登记；其余规划类文档一律 docs/meta/。
- 可逆：无移动则无风险。

## SP-05 缓存与产物零残留（部分）

- 现状：索引层四类命中 0；.gitignore 已补依赖/产物/运行时/编辑器/环境五类。
- 方案：无剩余动作；若要更强，把 git status --ignored 抽查纳入 repo-health 月更（会引入平台差异，暂不做）。
- 结论：建议按「已满足」重判（evidence: .gitignore + check_untracked_artifacts）。

## GF-10 文件一致性（部分）

- 现状：NarrativeForge 残留 5 文件；About 已改为 NinFenz。
- 方案：逐文件确认残留是「历史记录」（CHANGELOG 历史条目应保留）还是「活文档」（应改）。活文档统一改 NinFenz；历史记录不动。
- 风险：批量替换会误伤历史/协议引用；需逐条人工确认。
- 可逆：单提交内 revert。

## RL-01 语义化版本（部分 → amend）

- 现状：0.xx 单序列 + 1.0.x CLI 线（作者裁决），CHANGELOG 顶部已改 Unreleased。
- 方案：docs/meta/RELEASE-CADENCE.md 已含「版本号语义」段；再在 VERSION-MATRIX 登记双线映射。
- 结论：amend（手册三段式 → 本仓双线），不改版本号现状。

## DC-02 文档结构（FAIL）

- 方案：新增 docs/index.md（入口索引：quickstart/protocol/standards/meta/agent 五类各一行），并在 README 文档导航段引用；adr/ 与 spec/ 目录暂不新建（决策记录已在 decisions/，spec 真源在 01/02 协议件）。
- 风险：新入口会与 docs/standards/index.md 重复，需保持单一入口层级。
- 可逆：删除 docs/index.md 与其引用行。

## DC-03 ADR 目录（部分）

- 方案：保留 decisions/（含 INDEX/README/ERRATA 的成熟形态），在 docs/index.md 里给「决策记录」入口指向 decisions/INDEX.md；不搬迁。
- 结论：amend（落点 decisions/ → 手册 docs/adr/），理由：现有目录已有状态机与 ERRATA 机制。

## MT-05 PR 前自检信号集（未做）

- 方案：.pre-commit-config.yaml 已含 5 条最低钩子；再加 3 条本地信号：ruff 全量、markdown 结构、gitignore 覆盖度。三者在 CI 已跑，本地加只是为了缩短反馈环。
- 成本：pre-commit 运行时间 +8~12 秒（可缓存）。
- 可逆：删 3 个 local hook。

## 执行顺序建议（若作者批准）

1. DC-02 + DC-03 + RL-01 + SP-02（低风险文档/配置）
2. MT-05
3. SP-01/SP-03 批 1
4. SP-01/SP-03 批 2（需作者签字）
5. GF-10 逐条
每步独立 commit + 全量门禁。
