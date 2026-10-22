# CI 红 · 取证与归因（D:\nf-wt-ci · branch gov/ci）

> 证据来源（只读拉取，2026-10-22）：
> - 最近一次 `ci-verify` 失败 run：**39625381588**（head `32972ff3`, 2026-10-21T15:24Z, main）
>   `/actions/runs/39625381588/jobs` → 34 作业 / **16 failure**（static-checks-42 + 15 个 unit 分片）。
> - 每个失败作业的 job 日志逐条下载（`actions/jobs/<id>/logs`），分片内 `失败用例（分片 N）` 组给出
>   `.nf-logs/shardN.log` 的 `FAIL:`/`ERROR:` 行（ci-verify.yml 的 aebca611 诊断回显已生效）。
> - `coverage` run 39625381736 的 job 日志含**全量 discover 的 20 条完整 traceback**（与分片集互为补充）。
> - 本地复现：`NF_VERIFY_TMP=.nf-logs bash verify.sh --checks-only --no-cache` → **EXIT=1, FAIL=11**，
>   其中 check17/18/19/21/22 五条与 CI 静态作业**逐字一致**（`No such file or directory`）。
> - 工单附带事实：CI 分支 `gov/ci` = main + 3×`chore: 收口重算` + 1×diag 提交；失败 run 的 head 不含这 3 个收口提交。

## 一、16 个红作业清单（run 39625381588）

| # | 作业 id | 作业名 | 结论 |
|---|---|---|---|
| 1 | 119309782486 | static-checks-42 | failure |
| 2 | 119309782770 | unit-tests-3-of-32 | failure |
| 3 | 119309782835 | unit-tests-23-of-32 | failure |
| 4 | 119309782886 | unit-tests-10-of-32 | failure |
| 5 | 119309782889 | unit-tests-15-of-32 | failure |
| 6 | 119309782987 | unit-tests-8-of-32 | failure |
| 7 | 119309783025 | unit-tests-30-of-32 | failure |
| 8 | 119309783075 | unit-tests-29-of-32 | failure |
| 9 | 119309783156 | unit-tests-31-of-32 | failure |
| 10 | 119309783164 | unit-tests-25-of-32 | failure |
| 11 | 119309783219 | unit-tests-26-of-32 | failure |
| 12 | 119309783222 | unit-tests-20-of-32 | failure |
| 13 | 119309783278 | unit-tests-0-of-32 | failure |
| 14 | 119309783304 | unit-tests-27-of-32 | failure |
| 15 | 119309783432 | unit-tests-22-of-32 | failure |
| 16 | 119309783467 | unit-tests-12-of-32 | failure |
| — | 119311331721 | gate | skipped（needs 全绿才跑） |

其余工作流（同一 head 的失败 run）：
`coverage` 39625381736（core-coverage-ge-80）· `net-engine` 39625381712 · `rust-parity` 39625381501
（cargo-test-ubuntu / cargo-test-windows / rust-vs-python-truth-parity 三红）· `gitee-poll` 39701989216 ·
`cross-platform` 39625381558（三平台 gate 全红）· `net-probes` 39368507890（dependabot 分支）。

## 二、逐项归因表（红 → 根因(文件:行) → 修法 → 验证命令）

### A. static-checks-42：6 FAIL

| 失败项 | 根因（文件:行） | 修法 | 验证 |
|---|---|---|---|
| check17/18/19/21/22 unittest 五连 FAIL（日志 `No such file or directory`） | `verify.sh:40-41` 允许 `NFL_TMP` 为**相对路径**（CI 设 `NF_VERIFY_TMP=.nf-logs`）；`verify.sh:1381,1394,1409,1501,1516` 的日志重定向写在 `( cd desktop && ... >"$NFL_TMP"/... )` **子 shell 内**——`cd desktop` 后相对 `.nf-logs` 解析到 `desktop/.nf-logs`，必然 ENOENT。本地已逐字复现。 | 在 `verify.sh` 建目录后**把 NFL_TMP 绝对化**（`NFL_TMP="$(cd "$NFL_TMP" && pwd)"`），并把 `TMPDIR/TEMP/TMP` 只在系统临时目录不可写时才指到它。 | `NF_VERIFY_TMP=.nf-logs bash verify.sh --checks-only --no-cache` → FAIL 里不再出现 check17-22 |
| check39 终端与端壳残留门禁：`顶尖 CLI 基线未过：18/19，失败项：session-persist`（`.nf-logs/nf_check39.log`） | `desktop/src/core/terminal.py:1167-1169` `baseline_tmp_dir()` 取 `tempfile.gettempdir()`；CI 的 `TMPDIR` 被 `verify.sh:57` 指成 **仓库内相对 `.nf-logs`**（Python 会绝对化成 `/home/runner/work/NinFenz/NinFenz/.nf-logs`）⇒ 会话文件写进**仓库树内**，被写盘闸门/落盘判据拦下。本地（TMPDIR=系统 temp）19/19 通过。 | 同上（不把 TMPDIR 指向仓库内）。修后用 `TMPDIR=<repo>/.nf-logs nf shell --baseline` 复现→验证转绿。 | `nf shell --baseline`（19/19）与 `NF_VERIFY_TMP=.nf-logs bash verify.sh --checks-only` 的 check39 |

### B. 15 个 unit 分片：20 条失败用例（逐条来自 job 日志 `失败用例（分片 N）`）

| 分片(作业) | 失败用例 | 根因（文件:行） | 修法 |
|---|---|---|---|
| 3 (782770) | `test_watch.ResponseCacheTest.test_verify_is_allowlisted_and_second_run_hits_cache`（同代际第二跑必须命中缓存 1!=0） | `desktop/tests/test_watch.py:94`；`verify` 缓存目录取 TMPDIR/NF_HOME ⇒ 相对 `.nf-logs` 导致两次跑不共享可命中缓存 | A 修复（TMPDIR 绝对化/不落仓库）后复验 |
| 3 (782770) | `test_lsp.TestReadContainment.test_outside_uri_returns_empty_from_every_face`（'' != 根外机密内容） | `desktop/tests/test_lsp.py:119`；`desktop/src/core/lsp.py` 根外包含判定在 POSIX 上用 `Path.is_relative_to` 假阳性（需按 resolved 路径/大小写敏感口径） | 修 lsp.py containment（根外读一律空） |
| 23 (782835) | `test_role_model.RealRepoTest.test_scan_clean`（role_coordinates.json 与实时重算不一致） | `protocol/role_coordinates.json` 派生面**漂移**（main 未重冻；gov/ci 的 3×`收口重算` 已重算，本地 gov/ci 该测已绿） | 冻结链重算（不手改），随分支推送验证 |
| 10 (782886) | `test_doc_reachability.GuidancePathReachabilityTest.test_code_guidance_paths_resolve`（文档引用 path 解析不到） | `desktop/tests/test_doc_reachability.py:423`；被引 `desktop/src/core/gate_inpr*.py` 路径在文档表里与实际不符（本地也红） | 修文档表里的路径（或补文件），不放松判据 |
| 10 (782886) | `test_doc_reachability.LivingDocConsistencyTest.test_living_docs_paths_resolve` | 同上，`test_doc_reachability.py` 活文档一致性专件（本地也红） | 同上 |
| 10 (782886) | `test_suite_isolation.SuiteHomeIsolationTest.test_session_home_is_a_temp_dir`（home 父目录 ≠ /tmp） | `verify.sh:57` 把 `TMPDIR` 指向仓库内相对 `.nf-logs`；`scripts/verify_tests.py:276` 用 `tempfile.TemporaryDirectory()` 建 home ⇒ home 落在 `repo/.nf-logs/...`（测试进程里 gettempdir 又因 cwd=desktop 退回 /tmp） | A 修复（TMPDIR 保持系统 temp；只有兜底时才指 NFL_TMP） |
| 15 (782889) | `test_p6_evaluations.RiskAndBaselineTest.test_time_to_restore_is_unknown_only_for_a_named_reason`（'restored' not found） | `deployments/postmortems` 数据面读不到：CI `checkout` 默认 **fetch-depth=1 / 无 tags**（`ci-verify.yml:100` 等 checkout 步骤）；本地 23 个 tag、全历史 ⇒ 绿 | 各测试作业 checkout 加 `fetch-depth: 0, fetch-tags: true`（coverage/cross-platform 同） |
| 30 (783025) | `test_p6_evaluations...test_no_metric_is_reported_without_a_basis`（efficiency_and_flow 无缺席原因） | 同上：有指标因缺 tag/历史而算不出且未给出 why | 同上 |
| 20 (783222) | `test_p6_evaluations...test_change_failure_rate_comes_from_the_incident_registry`（unexpectedly None） | 同上（incident registry/tag 面） | 同上 |
| 22 (783432) | `test_p6_evaluations...test_tags_give_real_deployment_and_lead_time`（unexpectedly None） | 同上（tag_count>5 要求 23 个 tag 在场） | 同上 |
| 29 (783075) | `test_plugin_wasm_host.LoadTest.test_declared_manifest_is_loadable_without_issues`（插件产物不在场：…/nf-plugin-sha256.wasm） | CI 不构建 wasm 产物（`engine/wasm/sha256/target/**` 为忽略面）；而本文件头明确写「wasmtime 或 .wasm 产物不在场即 **skip**（这里不构建）」，这两条用例漏了 skip 守卫（`desktop/tests/test_plugin_wasm_host.py:35` / `:85`） | 按文件自述口径给这两条加 `skipUnless(ARTIFACT_READY)`；不删断言、不降判据（产物在场时仍全跑） |
| 26 (783219) | `test_plugin_wasm_host.FallbackTest.test_host_self_test_passes`（自带清单不该有问题：插件产物不在场） | 同上 | 同上 |
| 8 (782987) | `test_gate_select.FilterTest.test_filters_private_and_bytecode`（'C:/outside/y.py' 未被过滤） | `desktop/src/core/gate_select.py` 外部路径过滤只认 POSIX 绝对路径，Windows 盘符路径在 Linux 上被当相对路径保留 | 修 gate_select 过滤：同时识别 `C:/`、`C:\` 盘符绝对路径 |
| 25 (783164) | `test_gate_observe.NormalizeTest.test_filters`（'C:/outside/x.py' 残留） | `desktop/src/core/gate_observe.py` 同上 | 同上（复用同一判定） |
| 31 (783156) | `test_verify_report.RealRepoTest.test_committed_report_is_fresh`（protocol/verification_report.json 与实时重算不一致） | 派生面漂移；gov/ci 3×收口重算应已覆盖（本地待复验） | 冻结链重算，随分支验证 |
| 27 (783304) | `test_verify_report.RealRepoTest.test_real_repo_has_no_failing_judgement`（['role_coordinates']） | 同上，报告里 role_coordinates 仍 FAIL（连带 role_model 漂移） | 收口重算后复验 |
| 27 (783304) | `test_role_model.RealRepoTest.test_projection_is_current` | role_coordinates 投影不新 | 同上 |
| 27 (783304) | `test_conformance_scan.LogicalReadFaceAuditTest.test_sites_only_read_inside_their_declared_face`（读取面出现 `.nf-logs/nf_shard_home_27_*/cache/...json`） | A 的连带：分片 home 落在**仓库内** `.nf-logs/`，被读取面审计记成"越界读取" | A 修复（home 落系统 temp） |
| 20 (783222) | `test_cli_json_face.JsonFaceNoMachinePathTest.test_success_faces_are_portable`（`nf shell ...` 回吐 `<repo>/.nf-logs/...` 绝对路径） | A 的连带：`NARRATIVE_FORGE_HOME` 落在 `/home/runner/work/.../.nf-logs` ⇒ 命中 `/home/[a-z]` 机器路径正则 | A 修复 |
| 20 (783222) | `test_daemon.DaemonFreshnessTest.test_path_keyed_caches_are_cleared_per_request`（pack_combo 进程缓存未清 0<1） | `desktop/tests/test_daemon.py:171` + `desktop/src/core/daemon.py` 清缓存面在 Linux/相对 TMPDIR 下未命中（需 A 修复后复验，再定是否代码缺陷） | 先 A；不绿再逐行核 daemon 清理路径 |
| 0 (783278) | `test_verify_report.BuildTest.test_build_is_deterministic`（两次 digest 不同） | `desktop/src/core/verify_report.py` 摘要输入含**机器相关路径**（`/home/runner/...` 与本地 `D:\...` 不同/临时目录不同） | 修摘要输入为仓库相对路径（不手改期望；本地同红已复现） |
| 12 (783467) | `test_atomic_write.RepoTruthWritersUseAtomicWriteTest.test_trace_writer_keeps_old_content_on_failed_replace`（写失败须如实回 False） | `desktop/tests/test_atomic_write.py:47` + `desktop/src/core/atomic_write.py`（trace 写入失败被吞）；本地 Windows 也红（PermissionError 语义差异另见同文件 4 条本地红） | 修 trace writer 失败路径返回 False；并让测试的"只读目录"在 POSIX/Windows 上都成立 |

### C. 其它工作流

| 工作流 | 红点 | 根因 | 修法 |
|---|---|---|---|
| coverage | `core-coverage-ge-80` | ①全量 discover 撞上 B 组同批失败（20 failures）；②`coverage report --fail-under=80` 阈值是**目标**不是现状，需补测试提覆盖；③coverage 作业未设 `NARRATIVE_FORGE_HOME` 兜底（`coverage run -m unittest discover -s desktop/tests` 不加载 `desktop/tests/__init__.py` 的隔离兜底），故 suite 隔离类失败在 coverage 独立出现 | 先修 B 组；再量覆盖率缺口最大模块并补测试（不排除文件、不降阈值）；coverage 作业改为经 `scripts/verify_tests.py`（或显式设 home）跑 |
| net-engine | `net-engine-readonly-gate` | `语料身份 be3a7862… ≠ 金标 fe8e8f3e…（模式=工作区）` + 工作区/导出态语义断言差异（golden 锚定 HEAD 983741b）；.NET 金标未随语料重算 | 按 .NET 引擎 RUNBOOK「复基线」`run-rebaseline.ps1` 重算夹具/常量（不手改期望），或把门切到导出快照模式；需先确认当前 HEAD 的 .NET 编译态 |
| rust-parity | `cargo-test-ubuntu` / `cargo-test-windows` | **workflow bug**：toolchain 步骤执行了 `cargo test --version`（cargo 无此参数，`error: unexpected argument '--version'`） | 删该行（改 `cargo test --help`/`cargo --version`） |
| rust-parity | `rust-vs-python-truth-parity` | `check_parity.ps1` 7 面不一致：`event-backing`/`io-types`/`schema-clean`/`pipeline-dryrun`/3×逐字节 —— Rust 冻结表/契约实现落后于 Python 真源（与 cargo test 的 9 条同源） | 用 `engine/rust/tools/` 的生成器/`nf asset contract --freeze` 重算 Rust 冻结面（不手改），并补 cargo 单测绿 |
| gitee-poll | `poll` | 定时任务（每 10 分钟）从 Gitee 拉 Issue；缺 `GITEE_TOKEN`/网络/接口字段变更（job 日志仅 exit 1，需 secrets 侧确认） | 先加诊断输出定位（token/HTTP 码）；属运维/secrets 面，代码侧不降判据 |
| cross-platform | 三平台 gate 全红 | 全量 `verify.sh --full` 继承 ci-verify 同批失败 +（macOS/Windows 平台差异待各自日志逐条核） | 随 A/B 修复后复验；平台差异逐条归因 |
| net-probes | dependabot 分支红 | 历史 workflow（2026-10-20）；与 main 红无直接关系，待该 workflow 自身日志归因 | 本轮先不改（不属 16 红线；避免扩散） |

## 三、修复顺序（每类一个 commit）

1. `fix(verify): NFL_TMP 绝对化 + TMPDIR 不落仓库`（A，一处根因覆盖 static 6 + B 组 5 条）
2. `fix(ci): checkout 取全历史与 tags`（B 组 p6 ×4）
3. `fix(test): wasm host 两条用例按文件自述补 skip 守卫`（B 组 ×2）
4. `fix(code): gate_select/gate_observe 识别盘符绝对路径；lsp 根外读；atomic trace 失败返回 False`（B 组 ×4）
5. `fix(code): verify_report 摘要去机器路径`（B 组 ×1）
6. `fix(test): doc_reachability 引用表路径校正`（B 组 ×2）
7. 派生面漂移：走冻结链重算（role_model/verify_report ×3）——**只在本地复验仍红时**才动
8. coverage 补测试（不排除文件、不降阈值）+ 作业隔离（C）
9. rust-parity workflow 删 `cargo test --version`（C）
10. net-engine 复基线（C，按 RUNBOOK）

## 四、本地验证口径（每轮）

```bash
cd D:/nf-wt-ci
bash verify.sh --full --no-cache     # 目标：PASS=76 / FAIL=0
```
