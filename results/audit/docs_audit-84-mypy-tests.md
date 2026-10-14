---
id: AUD-0036
title: 类型收敛扩面到 desktop/tests（66 条清零，27 文件）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」；承接 AUD-0034/0035。开工依据为内部实测（mypy desktop/tests 错误条数 66）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/tests/test_write_flag_gate.py:bc55da5403b7acdcd8552c1f28c44f553f4a4f191ff8b9a81c47bae42a035803
  - desktop/tests/test_verification_cards.py:f4486f2683676e0b9094eaad6a7a4d20c424c9e07bb101e3692a90b6d5828492
  - desktop/tests/test_serve_default.py:739e151eda38b317123e03c06892f0ef2ef095735cc5dbb761453111ac2522b4
  - desktop/tests/test_selfcontained_rebuild.py:c1804902ab453ca60333c35b712b9e9a8a14aed34664aafe3b5ff184ad18ef20
  - desktop/tests/test_rust_fastlane.py:d81a50895980f0877f858b088f4ad430753d73807504e28b3d83058c0762ccba
  - desktop/tests/test_quant_domain_package.py:e11700ea8f52a9d2a3c39838923f9264a099aa0997ce5e6890a9a96e65bc1709
  - desktop/tests/test_mcp_write_freedom.py:4d951c1d395bec365ecc9971d2ce6acdc0063439823d61e9c23b7fb77767c025
  - desktop/tests/test_mcp_runtime.py:9d6d1b11e2c2ecd517a9ddbe8bae64a3578e5e9462c12032dc1411f66f8f61eb
  - desktop/tests/test_live_doc_counts.py:8d522b35f224f733bcac561a57376699a75dd3593e945475fc77319673d458d0
  - desktop/tests/test_layer_model.py:74ef800a95d1caed9d88809f76708b6de4427c6be9412387e5531e807f8ebf42
  - desktop/tests/test_knowledge_sig.py:634a727aab5fa9e119835be2e9a2c60dbe36054b66b8d955e0856db048fc9b34
  - desktop/tests/test_judgement_coverage.py:d63adb43b766905494859941818d5eb6c5fc5eb4f19d9f5353df7b0d869c9f24
  - desktop/tests/test_judge_references.py:4166744627ab477eddfff9fe782eee5f6bb457d8f4c93beb23df584087c8bf53
  - desktop/tests/test_intake_gate.py:7b0fd39f903557abed07f6e10a562904bb043204d4843ced89d47df064f83fb2
  - desktop/tests/test_import_injection.py:b576a9c4ade045b686a888f0dd5c3fd8b46788bbcf9fbdc71b195d983f50b84b
  - desktop/tests/test_gap_review.py:f78b4dc0c9f7d6fa035c3cd3c9f1415032416311b0d11d5d96a77f44a718f5e7
  - desktop/tests/test_explain_coverage.py:015b68d9207bfe43ff9669a3ea488b070bce3cd10efc96de7ee0aa12796264d6
  - desktop/tests/test_doc_reachability.py:069e8f4b5bdab33c733c3f08272f00624b0638c8b61664cbde34f2607b96d9de
  - desktop/tests/test_dead_code.py:f4e95574a247a2445b48427c0a45fce3374ea1fe214e678240077910b27da4fe
  - desktop/tests/test_daemon_parity.py:50e84719761faee8726e25025fd52efc823dcdddb1c57f7efc4ae3488694c76b
  - desktop/tests/test_concept_graph_gate.py:2a44468a58648d05497f14e25b782d2e2e55143900b1b19e9ecb18a8e3335c57
  - desktop/tests/test_commit_msg.py:b4dda2ec6229fdad0e94a9473f07dfb4d7766e1f35f9495ee3e126be6b4c5fcc
  - desktop/tests/test_cli_json_face.py:522b2ce20375bf6399f25879c5e8a797202d5923ee05c99703334be5ee05ae8d
  - desktop/tests/test_ccv3_adapter.py:bf7e200b3c8df8d56dd811d2baab6a5d4961d4a043aa98bdfa2b4e95640bf7db
  - desktop/tests/test_ai_domain_closure.py:f9ec87c5c53daa811f443ec207fe6190c48039f24228c8d7af1b9873d6805bba
  - desktop/tests/test_terminal.py:b9f8f6fecd185f9a9bb99cb391e937d7fb76998a84360a251bd33ab3c05bf503
  - desktop/tests/test_nf_cli.py:4ddd00ad386d0e35e3bc717db777fda922019e1fd1f38580ef8912bdac682220
---
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
