---
id: AUD-0036
title: 类型收敛扩面到 desktop/tests（66 条清零，27 文件）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」；承接 AUD-0034/0035。开工依据为内部实测（mypy desktop/tests 错误条数 66）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/tests/test_write_flag_gate.py:51edfd9e37a5421119af1907496d12b2d85188a0bfc827606028c372ef9a5105
  - desktop/tests/test_verification_cards.py:f4486f2683676e0b9094eaad6a7a4d20c424c9e07bb101e3692a90b6d5828492
  - desktop/tests/test_serve_default.py:4a4d19c399ba06f70d8c7153a8d23dd29c3330466df1c0e86434b9500d00a65c
  - desktop/tests/test_selfcontained_rebuild.py:c1804902ab453ca60333c35b712b9e9a8a14aed34664aafe3b5ff184ad18ef20
  - desktop/tests/test_rust_fastlane.py:ce2703a108483dd330de84f40137d190e2c930f90626dbdb908de3d9d9df2f99
  - desktop/tests/test_quant_domain_package.py:e11700ea8f52a9d2a3c39838923f9264a099aa0997ce5e6890a9a96e65bc1709
  - desktop/tests/test_mcp_write_freedom.py:a2afa8cf6e1d6c2ccb2cde5f57b796d0b8722908be632e227b2a8dc76fe9cf2e
  - desktop/tests/test_mcp_runtime.py:cf53f00460f76e3eabb0a45842f584878e12d7d402fe613dcc355c5f62a25457
  - desktop/tests/test_live_doc_counts.py:382aeb33f6bbc1c7b225810850c78b6990bf50833efc65f4a1ced8f887f9b9a4
  - desktop/tests/test_layer_model.py:8cea98de879a4bdf795f95afff9c8fa9a7675ebac227018b7b7694a158bfd69c
  - desktop/tests/test_knowledge_sig.py:4705091a139b4fc4da9a61bc816e30eeec3221688f3d923e43afc3b11609c17e
  - desktop/tests/test_judgement_coverage.py:d63adb43b766905494859941818d5eb6c5fc5eb4f19d9f5353df7b0d869c9f24
  - desktop/tests/test_judge_references.py:4166744627ab477eddfff9fe782eee5f6bb457d8f4c93beb23df584087c8bf53
  - desktop/tests/test_intake_gate.py:3c6786fe00d913603509ac1345208c031def063287c2230682636af439ae5a48
  - desktop/tests/test_import_injection.py:b576a9c4ade045b686a888f0dd5c3fd8b46788bbcf9fbdc71b195d983f50b84b
  - desktop/tests/test_gap_review.py:f78b4dc0c9f7d6fa035c3cd3c9f1415032416311b0d11d5d96a77f44a718f5e7
  - desktop/tests/test_explain_coverage.py:015b68d9207bfe43ff9669a3ea488b070bce3cd10efc96de7ee0aa12796264d6
  - desktop/tests/test_doc_reachability.py:b74cc400e354ca12cf632747eefbe41766f42fce445961613d97e02dd7d1b828
  - desktop/tests/test_dead_code.py:3b4f00dfe82740ba10c7e9949c8114401605050451baee03f95dfdaf2e75d4c1
  - desktop/tests/test_daemon_parity.py:f9cd71ded4eafa37c0080c632bfd304f2fb76feb6a0109de6c73337b4ff44343
  - desktop/tests/test_concept_graph_gate.py:2a44468a58648d05497f14e25b782d2e2e55143900b1b19e9ecb18a8e3335c57
  - desktop/tests/test_commit_msg.py:b4dda2ec6229fdad0e94a9473f07dfb4d7766e1f35f9495ee3e126be6b4c5fcc
  - desktop/tests/test_cli_json_face.py:edbbed0acb44ab9d9fe28c5de9a88af50cf63b1c1b173a873c976b9bc6367a7e
  - desktop/tests/test_ccv3_adapter.py:bf7e200b3c8df8d56dd811d2baab6a5d4961d4a043aa98bdfa2b4e95640bf7db
  - desktop/tests/test_ai_domain_closure.py:f9ec87c5c53daa811f443ec207fe6190c48039f24228c8d7af1b9873d6805bba
  - desktop/tests/test_terminal.py:0bb35b80919c62ee22b8460a538826279b092db6775f527b23896ca08b638b00
  - desktop/tests/test_nf_cli.py:18c407b6780205e50997d99ab9ea967e6ee066b2dca5d087e9eeea632d311804
---
> 重审（2026-11-08）：计数模式扩 N 条单测/探针/用例

> 重审（2026-11-08）：活文档计数扫描面扩到 workflows

> 重审（2026-11-07）：门禁修：silent-skip 理由 / 两个文本参数登记 / --mode 复核

> 重审（2026-11-07）：nf evidence batch（目录逐件复验，整批不可用即失败）

> 重审（2026-11-06）：Rust 侧 SINK_ALLOW 同步 + 陈旧二进制守卫 + 漂移判据

> 重审（2026-11-06）：哨兵修复收口（重绑）

> 重审（2026-11-06）：快照内只判 HEAD（脏树信号仅用于活树）+ 取消不崩

> 重审（2026-11-06）：cc_label PNG iTXt 载体（可读回/不改像素/CRC 合法）

> 重审（2026-11-05）：cc_label sidecar 回退（nf-label-sidecar/1，绑定对象摘要）

> 重审（2026-11-05）：cc_label 声明层（nf-label/1 IR）+ 供应链核对进发布结论

> 重审（2026-11-04）：check12 修复波：JSON 面登记 / json_doc 收敛 / Rust 回执去重同步 / 基准 JSON 纯净

> 重审（2026-10-30）：新增契约级 Git 演进时间线；结构化 Markdown YAML 字段与 JSON schema 差异纳入影响度

> 重审（2026-10-30）：全仓审计口径复核：显式 legacy 清单、subjects 根内解析、Path 参数闸门、惰性导入与 manifest 可复算

> 重审（2026-10-29）：CLI 命令树无损分组、meta-cockpit 接线与恢复分支全量验证后重绑；既有结论不变

> 重审（2026-10-29）：恢复分支全量验证：接线 meta-cockpit 公共模块、清理零引用、修复 ReDoS/CLI 闸门/公开文档路径后重绑；既有结论不变

> 重审（2026-10-25）：决策/交接/复盘外置：公开面只留模板（ADR-0000）

> 重审（2026-10-24）：CI 跨平台稳定性修复：角色投影只认 Git 跟踪面、报告路径脱敏、ReDoS 负例与 GUIDANCE 豁免判据同步，重审当前测试与门禁对象。

> 重审（2026-10-24）：2026-10-24 投稿写面收口：Gitee 改为作者白名单，加入日配额与跨平台空目录占位，重绑投影响应文件

> 重审（2026-10-23）：A 类跨平台修复（尾点占位/盘符路径）后重绑

> 重审（2026-10-23）：Rust 快线加速收口：新增常驻 worker / PyO3 原语 / Rayon 解析并行与 code_metrics 接线；被审判据语义未变，digest 随实现同步

> 重审（2026-10-22）：R2：MCP 内部错误脱敏（重冻·修订）

> 重审（2026-10-22）：R2：MCP 内部错误脱敏（重冻）

> 重审（2026-10-22）：基线修复：契约面只认仓库件 + doc 可达性 worktree-aware（重冻）

> 重审（2026-10-21）：rating_decided 1

> 重审（2026-10-20）：hygiene + version governance

> 重审（2026-10-20）：repo hygiene: junk dirs removed, LF normalized

> 重审（2026-10-20）：version governance + daemon leak fix

> 重审（2026-10-19）：干净树重冻；修正外部 WIP 污染（AUD-0036 subject 从 WIP 版 0d431643 回到干净版 ad0bab51）

> 重审（2026-10-19）：gate_labels 真值缓存指纹 + heredoc 修复

> 重审（2026-10-19）：重测试再切分（机器面 16 片 / JSON 面 4 片）+ 内层线程 8/jobs

> 重审（2026-10-18）：工具名归一：6 个旧名 -> _list/_search/_read；旧名 alias；官方 tdqs 4.9 两次

> 重审（2026-10-18）：asset_read：删除 outputSchema 的 found（无匹配为错误），2 参数 schema 一致；本地 TDQS 4.8/4.9

> 重审（2026-10-18）：P2：两条全命令面扫描切片化

> 重审（2026-10-18）：P2：判定同根改跨进程比对 + 常驻集去掉 npm payload

> 重审（2026-10-18）：Glama coherence：新增 pattern_ls/asset_ls；asset_read 兼容别名；同步 12 工具面

> 重审（2026-10-18）：Glama coherence：asset_get→asset_read（旧名兼容别名）+ 协议边界描述；行尾规范为 LF

> 重审（2026-10-18）：Glama coherence：MCP 面 asset_get→asset_read（旧名保留兼容别名）；spec_ls/registry_query 描述边界

> 重审（2026-10-18）：Glama coherence：收紧 spec_ls/registry_query 描述边界；asset_get 说明为协议资产五接口规范名

> 重审（2026-10-18）：P2：check12 分片并行（verify_tests 执行器 + 权重基线）

> 重审（2026-10-15）：门禁提速批：测试面进程内化（check12 热点）+ 新增 gate_engine/gate_labels 单进程门禁引擎 + 派生基线重冻；被审对象字节已变，按本仓 rebind 流程重绑 digest

> 重审（2026-10-14）：Rust 快线同步：receipts 固定段 44→54 + verify_report SPECS 30→31（role_coordinates）+ asset_contract 裁定退出原生面

> 重审（2026-10-14）：引入 nf audit rebind 命令（core/audit.py + CLI + 顺序纪律 + 两处面收敛）


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物；测试文件不在 `code_metrics` 棘轮面，未触发重冻。

## 一、结果

`python -m mypy desktop/tests --ignore-missing-imports` 错误条数 **66 → 0**。至此 **`desktop/src` + `scripts` + `desktop/tests` 全树 0 条**（默认口径）。

## 二、交付（按修法归类）

| 类 | 模块/修法 |
|---|---|
| `module_from_spec` 契约（最大块，约 21 条） | 10 个测试模块补 `assert spec is not None and spec.loader is not None`（typeshed 的 `spec_from_file_location` 返回可空）；含 test_terminal / test_nf_cli / test_commit_msg / test_layer_model 等 |
| 声明/集合显式类型（约 15 条） | `counts`/`found`/`params`/`args`/`_CACHE`/`_PRESET_STATE`/`_REPORT`/`KNOWN_EXTERNAL`/`NAMED_COUNTS`/`REVIEWED_UNREFERENCED` 等标注 |
| 类级夹具属性 | test_doc_reachability（`commands: set` / `tops: set` 类级声明）、test_daemon_parity（`doc: dict`）——mypy 不认 `setUpClass` 里的 `cls.x = ...` |
| 可空契约 | test_judgement_coverage（`schema: Optional[str]`）、test_intake_gate（`doc`/`index_text` Optional）、test_ccv3_adapter（`body` 拆原始值） |
| 跨平台/属性 | test_knowledge_sig（`os.sys`→`import sys`）、test_mcp_runtime（FakeIn 覆写只读 `buffer`，单点 `# type: ignore[misc]`） |
| **重名测试（真缺陷）** | `test_gap_review.ReviewLimitTest` 有两个同名 `test_limit_zero_means_all_rows`——**后者遮蔽前者，前者从未执行**；第二个按其实体改为 `test_limit_two_caps_rows`，两例自此都会跑 |

## 三、验收证据（本机实测）

- `mypy desktop/tests` 错误条数 **66 → 0**。
- `python scripts/code_metrics.py` → 通过（测试文件不在棘轮面）。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**（check12 会全量跑这些测试）。

## 四、遗留与设计偏差

1. 类型线至此覆盖全 Python 树；radon 复杂度面（≥C 319 / ≥D 99）仍未动。
2. `test_gap_review` 的重名是**既有真缺陷**（被遮蔽的用例从未跑），本件只更名、不删任何用例。
3. 62 §三·② 余量与 §二·2 .NET 重冻不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑↑ | 全树 mypy 0 条；verify 双绿；顺带恢复一条从未执行的重名用例 |
| 动态可执行 | ↑ | 被遮蔽用例恢复执行 |
| 架构纯度 | → | 只改测试内标注/断言/命名 |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
