---
id: AUD-0027
title: v2.12.0 首例发布（保留式收口 + 发布机制两处缺陷修复 + Golden Master）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §二·1「用新机制发布一次」。首例实战取证暴露发布机制两处缺陷（同版本节替换静默删历史 / 提交扫描无发布边界），先修后收；CHANGELOG 既有 2.12.0 手工节按「不静默丢内容」保留。tag 与 push 属作者动作，本件不含。
verdict: pass
auditor: 本轮执行者
subjects:
  - CHANGELOG.md:665f3fb40ac05aedb2ff016ae83c06e287ee321554282641153081abbefd1fe9
  - docs/meta/VERSION-MATRIX.md:0d6b7ba72049d36354119deb1764d736433acdb1d06be767621ceeaf4cfdc1ce
  - README.md:be9a500b02a95692e8c62d90e6c70ce2e0a6a50555efe046952a6c829f8eddae
  - desktop/src/core/changelog_gen.py:152aecae6e55e53913e546658ee9385e1ea2dd5ab74e3021cd9bc665282efe40
  - desktop/tests/test_changelog_gen.py:acde329ef16701c680c1eb15df0cc8edbe3d13bdbdc45a7ee4821bf9949f24da
  - protocol/release_policy.json:1f2fc3f2a3c1ca2e26a8bbd15c1ed8a589e29756a219a4a93c857c732d156c66
  - docs/release.md:a878a24b8631d965e30d0bc865c9f88b71049f5a73025cf2984f5bd5cbca5dbb
  - scripts/nf.py:b77cf345bed8b768a5eb5978de5216606aef37b76ddfb2da5b5b65dc76e0ddea

---
> 重审（2026-10-26）：Merge W10: model check + concept index + agent contracts

> 重审（2026-10-26）：Merge W9: gate43-45 + DOCX/DITA importers + PyPI packaging

> 重审（2026-10-26）：T9.2 导入器：新增 core/import_docx.py、core/import_dita.py 与 nf import docx|dita（scripts/nf.py 增长），按冻结上限重冻 code/coupling 基线；按审计协议重绑对象 digest

> 重审（2026-10-26）：Merge W8: JS second impl + registry CID + security scan

> 重审（2026-10-26）：Merge W7: contract semantics + content IR + reference runtime

> 重审（2026-10-26）：T7.2 内容 IR：新增 desktop/src/core/content_ir.py 与 nf ir check 命令（scripts/nf.py 增长），按冻结上限重冻 code/coupling 基线；按审计协议重绑对象 digest

> 重审（2026-10-26）：Merge t-m1/t-record/t-bench: M1 evidence rule, exec record, bench leaderboard

> 重审（2026-10-26）：Merge t-maturity: M0-M3 evidence-based maturity + registry projection

> 重审（2026-10-26）：Merge t-scope: scoped allowed_module_ids + --loose

> 重审（2026-10-26）：Merge t-compliance: regulatory profile 34 clauses + 9 assets + evidence pack

> 重审（2026-10-26）：Merge t-identity: deliverable-contract first screen + demo/presets/library ordering

> 重审（2026-10-26）：Merge t-techdoc: techdoc pack depth + new gate modules

> 重审（2026-10-26）：Wave2: SSOT facts.json + domain gate + gate manifest

> 重审（2026-10-26）：rebase 到 fa3fdd58 后重冻（atoms/nf/perf_budget）

> 重审（2026-10-25）：Scorecard 收口：最新 main 合并、CODEOWNERS ASCII 化、SAST/Fuzzing、最小权限、依赖漏洞与容器 digest 统一重绑

> 重审（2026-10-25）：REUSE 3.3 合规（MIT-NOTICE + 徽章 + CI 作业）

> 重审（2026-10-25）：1.1.0 版本面 + CLA workflow + 定价

> 重审（2026-10-25）：准据法与争议解决 + 法律依据

> 重审（2026-10-25）：CLA 替代 DCO + FAQ 引用 + 免责与参考价

> 重审（2026-10-25）：分层双许可（1.1.0 起）

> 重审（2026-10-25）：跨平台收口：真实路径归一、守护状态读写锁、autostart 原子标记与机器路径短名脱敏

> 重审（2026-10-24）：夜间收口：Rust worker 安全、投稿配额、元数据、schema 与 postmortem 跨平台回执路径修复后按新输入重绑

> 重审（2026-10-23）：合并远端 README badge 后重绑审计摘要：仅文档变化

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

> 重审（2026-10-23）：Rust 快线加速收口：新增常驻 worker / PyO3 原语 / Rayon 解析并行与 code_metrics 接线；被审判据语义未变，digest 随实现同步

> 重审（2026-10-22）：H1：nf verify 仓库信任门（重冻）

> 重审（2026-10-21）：CHANGELOG 增加 2026-10-21 全仓一致性修复结果条目；既有审计结论不变

> 重审（2026-10-21）：修复 CHANGELOG 一字一行源件损坏；按 Git 历史与连续文本恢复段落，既有审计结论不变

> 重审（2026-10-21）：locales html 1

> 重审（2026-10-21）：readme head 1

> 重审（2026-10-21）：1.0.5 收口 1

> 重审（2026-10-21）：README 官方源声明与演示帧重建

> 重审（2026-10-20）：canonical notice 1

> 重审（2026-10-20）：0.x renumber 1

> 重审（2026-10-20）：readme/tag 治理 1

> 重审（2026-10-20）：release 1.0.4 1

> 重审（2026-10-20）：hygiene + version governance

> 重审（2026-10-20）：repo hygiene: junk dirs removed, LF normalized

> 重审（2026-10-20）：version governance + daemon leak fix

> 重审（2026-10-20）：D 盘迁移：跨盘 relpath 修复（nf.py 展示面 + trust_boundary 用例）

> 重审（2026-10-19）：check39 挂载五分钟入口判据（docs/quickstart.md ↔ scripts/quickstart_check.sh），verify.sh 结构性新增子判据

> 重审（2026-10-19）：nf.py 会话落点放行 .rivet（受限环境唯一可写临时区）

> 重审（2026-10-18）：CI 门禁矩阵化（32 片）

> 重审（2026-10-18）：CHANGELOG 记入门禁提速

> 重审（2026-10-18）：README 生成区重写（stats --write）

> 重审（2026-10-18）：Glama coherence：收紧 spec_ls/registry_query 描述边界；asset_get 说明为协议资产五接口规范名

> 重审（2026-10-18）：P2：check12 分片并行（verify_tests 执行器 + 权重基线）

> 重审（2026-10-17）：步骤5 结案：四组回滚证据登记（逐组取证）

> 重审（2026-10-17）：步骤5：在场/关键词组收敛到 _decl_check（等价性 15 例逐字节一致）

> 重审（2026-10-17）：步骤4 收口：attest --selfcheck 接线 + 站点/覆盖率分母同步

> 重审（2026-10-17）：步骤4：新增 check41/42（构建隔离 + 不可伪造 provenance）与对应判据模块

> 重审（2026-10-17）：能力面挂账：assertions.json 增 capability_vocabulary/index + 每条断言 capability

> 重审（2026-10-17）：整批毫秒路径深入：nf verify 增 --jobs（每 check 独立子进程跑 --only N --json，按 check 号排序合并）；机器面增 messages 使并行结果可重放文案；实测 18.6s→6.4s（2.9x）且人读面/机器面与串行逐字节一致；新增 test_verify_parallel_checks 4 条判据（等价+排序+fail-closed）

> 重审（2026-10-16）：子 check 缓存（步骤①）：新增 core/subcheck_cache.py（观测读面+目录项快照+内容寻址，fail-closed）+ gate_faces 增目录列举收集器；实测审计：观测开销 1.4–2.2x，大树遍历 check 命中收益被快照成本吃掉

> 重审（2026-10-16）：门禁提速批（续）：拆 gate_native 让引擎回到行数闸门内 + check37 走 runpy 进程内执行，gate_inproc 增 run_script；被审对象字节已变，按本仓流程重绑 digest

> 重审（2026-10-15）：门禁提速批：测试面进程内化（check12 热点）+ 新增 gate_engine/gate_labels 单进程门禁引擎 + 派生基线重冻；被审对象字节已变，按本仓 rebind 流程重绑 digest

> 重审（2026-10-14）：引入 nf audit rebind 命令（core/audit.py + CLI + 顺序纪律 + 两处面收敛）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI + 顺序纪律）：重审并更新 digest 机器化

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI）：重审并更新 digest 口径机器化，替换手搓脚本

> 重审（2026-10-14 · CHANGELOG 记 S 档条目）：被审对象随本波改动（CHANGELOG 增加数字资产契约 S 档条目），digest 依「重审并更新 digest」机械重绑；既有结论不变。

> 重审（2026-10-14 · 数字资产契约 S 档：包自述对账 / Frictionless 导出 / 可移植 schema）：被审对象随本波改动（组合包 INDEX 补登 SYSTEM_CARD 契约 / receipts 锚定面续扩 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · 数字资产契约续批 D3/E2/D4 + CHANGELOG 补记）：被审对象随本波改动（receipts 锚定面 58→67 / data_contracts 45→52 / LAYERS roles.write_exceptions 结构化 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / core/layer_model.py 由 nf layers --write 联动刷新职能投影 / code_metrics 基线重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 退役（2026-10-11）：原 subject「scripts/release_freeze.sh」随 golden master 机制退役一并删除，故从 subjects 移除；本件结论不依赖该脚本的行为，只依赖它当时**在场**这一事实。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物：`protocol/conformance_report.json` / `protocol/RECEIPTS.json` / `protocol/generated/*` / `results/interop/*` / `protocol/approvals/*` / `.release-frozen/*` 均为可复算投影或每次重签即变。

## 一、首例实战取证（开工依据）

1. **同版本节替换会静默删历史**：`insert_into_changelog` 原本无条件用生成节替换同版本节。实测 v2.12.0：1790 行人工未发布节 → 13 行生成节，会丢 333 条。
2. **提交扫描无发布边界**：`commit_subjects` 无 range，`nf changelog` 会把全史 582 条提交主题塞进版本节。
3. **既有 2.12.0 手工节无对应 changes 条目**（机制落地前积累），生成器无法覆盖——这是首例独有的迁移面。
4. **`nf release --freeze --apply` 的 `--apply` 被 argparse 拒收**：解析器只登记了 `--freeze`，而实现读 `args.apply`、帮助与 `docs/release.md` 都写 `[--apply]`——命令实际进不了执行态。
5. **冻结链顺序源指向不存在的属性**：`_release_freeze` 读 `rg.FREEZE_CHAIN`，而真源是策略件 `protocol/release_policy.json` 的 `freeze_chain`（`release_gate` 只有 `DEFAULT_FREEZE_CHAIN` + `policy()`）——该命令必抛「内部错误」。

## 二、交付

| 面 | 落点 |
|---|---|
| 缺陷一修复 | `changelog_gen.insert_into_changelog` 丢内容守卫：同版本节含未被生成覆盖的条目即抛 `ValueError`；写面 rc=2、不落盘、不归档（fail-closed）。`test_changelog_gen` 6 例 |
| 缺陷二修复 | `changelog_gen._last_tag` + `_bullets` 接入发布边界（`v2.11.0..HEAD` = 228 条；无 tag 退化全史）。`test_changelog_gen` +2 例（临时真 git 仓） |
| 收口 | `CHANGELOG.md` `[2.12.0]` 由「未发布」翻为「2026-10-05」（正文零改动）；`changes/unreleased/*` 5 条归档 `changes/2.12.0/`；`changes/unreleased/` 留 `.gitkeep` |
| 版本面 | `docs/meta/VERSION-MATRIX.md` v2.12.0 行落日期/✅ 且终端线/顶尖对标/资产契约三行标「随 v2.12.0 收口」；`README.md` 版本块「当前」切 v2.12.0、v2.11.0 转已发布 |
| 冻结链缺陷修复 | `scripts/nf.py`：补登记 `--apply`（此前被 argparse 拒收）；顺序源改读策略件 `freeze_chain`（此前读不存在的 `rg.FREEZE_CHAIN`，必抛内部错误） |
| 冻结链 | `nf release --freeze --apply`（conformance → approve → receipts） |
| Golden Master | `bash scripts/release_freeze.sh v2.12.0`（`01/02/06/07` + `verify.sh` + `desktop/src/core/*.py` 摘要 + `nf sig --verify` 指纹） |
| 审计 | 本件（AUD-0027） |

## 三、验收证据（本机实测）

- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。
- `nf release --json` → `issues: []`、`release_line: 2.12.0`。
- `nf changelog --version 2.12.0 --date 2026-10-05 --write` → **rc=2 / CHANGELOG 零 diff / 条目不归档**（守卫态；生成器对 2.12.0 不落盘）。
- `nf conformance` → conformant 27/27；`nf receipts --scope protocol` 57 件根一致；`nf approve --verify` 有效。
- `test_changelog_gen` 8 例全绿（含真 git 仓边界两例）。

## 四、遗留与设计偏差

1. **与 62 §二·1 字面命令的偏差（有意）**：v2.12.0 的 `nf changelog --write` 保持守卫态、不落盘；原因即上表缺陷一（会丢 333 条）。生成器的首次自动落盘顺延到下一个版本（目标版本节不存在 + `--since v2.12.0` 边界天然正确）。本波**不宣称生成器已为 2.12.0 落盘**。
2. `tag` / `push` 未执行（「除外部」+ 仓库口径 tag 属人）。`.release-frozen/v2.12.0` 为历史时点快照，不随现状更新。
3. 62 §三·② 余量（量化门违反 / 多语协议执行）、§三·① 存量收敛、§二·2 .NET 重冻（本地受阻）不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑ | 发布机制两处缺陷各有判据；版本面三处不悬空；Golden Master 结构完整 |
| 动态可执行 | ↑ | 守卫与提交边界均有真仓/真 git 仓实测；冻结链与快照可复跑 |
| 架构纯度 | → | 修复落在既有 `changelog_gen` 单点，不新增模块/check 序号 |
| 资产密度 | → | 发布收口为主，不新增内容资产 |
| 文档可执行性 | ↑ | `docs/release.md` 口径与实测一致；首例记录可复现（内部档 + 本件） |
