---
id: AUD-0044
title: 复杂度收敛第七批（json_schema._check 84→按关键字类拆分）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」复杂度面；承接 AUD-0043。开工依据为内部实测（radon desktop/src：≥C 312 / ≥D 92 / F 13；下一点 = `json_schema._check` 84）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/json_schema.py:f3a4a6a14de5104e217af8b154505f9ca46fd6133081188209add78143e2b23e
  - protocol/code_metrics_baseline.json:227e6b52a03c68feb9878b75e8220b8d3b64b3a054fe444426356ce736cc0346
---
> 重审（2026-10-26）：Merge W8: JS second impl + registry CID + security scan

> 重审（2026-10-26）：W7 cleanup: remove remaining dead imports (gate_profile/quality_gate)

> 重审（2026-10-26）：W7 cleanup: remove dead imports/locals in semantics/gate_profile

> 重审（2026-10-26）：Merge W7: contract semantics + content IR + reference runtime

> 重审（2026-10-26）：T7.2 内容 IR：新增 desktop/src/core/content_ir.py 与 nf ir check 命令（scripts/nf.py 增长），按冻结上限重冻 code/coupling 基线；按审计协议重绑对象 digest

> 重审（2026-10-26）：Merge t-m1/t-record/t-bench: M1 evidence rule, exec record, bench leaderboard

> 重审（2026-10-26）：Merge t-maturity: M0-M3 evidence-based maturity + registry projection

> 重审（2026-10-26）：Merge t-scope: scoped allowed_module_ids + --loose

> 重审（2026-10-26）：Merge t-measure: gate defect bench (new scripts/results/tests)

> 重审（2026-10-26）：Merge t-identity: deliverable-contract first screen + demo/presets/library ordering

> 重审（2026-10-26）：Merge t-techdoc: techdoc pack depth + new gate modules

> 重审（2026-10-26）：Wave2: SSOT facts.json + domain gate + gate manifest

> 重审（2026-10-26）：scan_memo 键含 mtime/size（修跨改文件吃旧值）

> 重审（2026-10-26）：scan_memo 可吞说明 + read_text_strict 接线 + 耦合面刷新

> 重审（2026-10-26）：风格基线收紧 + 共享扫描面（scan_memo）

> 重审（2026-10-26）：asset_contract 用 partial 绑定（消 B023）

> 重审（2026-10-26）：verify_report 共享扫描面（scan_memo）+ role_model/asset_contract/conformance/redos 复用

> 重审（2026-10-26）：rebase 到 fa3fdd58 后重冻（atoms/nf/perf_budget）

> 重审（2026-10-25）：Scorecard 收口：最新 main 合并、CODEOWNERS ASCII 化、SAST/Fuzzing、最小权限、依赖漏洞与容器 digest 统一重绑

> 重审（2026-10-25）：安全收口：仓库信任根收紧、IPC/MCP/插件/投稿读取资源上限与路径包含性加固重审

> 重审（2026-10-25）：D1 常量时间比较 + N2/L2 发布面白名单化

> 重审（2026-10-24）：CI 收口：修复 workflow cargo 版本探测、补齐 Rust parity 的 Python 固定依赖、移除 Rust 死代码，并扩展报告临时根脱敏覆盖。

> 重审（2026-10-24）：CI 跨平台稳定性修复：角色投影只认 Git 跟踪面、报告路径脱敏、ReDoS 负例与 GUIDANCE 豁免判据同步，重审当前测试与门禁对象。

> 重审（2026-10-24）：夜间收口：Rust worker 安全、投稿配额、元数据与 schema 修复后按新输入重绑

> 重审（2026-10-24）：2026-10-24 投稿写面收口：Gitee 改为作者白名单，加入日配额与跨平台空目录占位，重绑投影响应文件

> 重审（2026-10-24）：DOC-004 收口：协议回执纳入 closed 复盘件，修复 closed 状态无法满足锚定判据的循环

> 重审（2026-10-23）：A2 同族修复：gate_observe 盘符/UNC 判仓外

> 重审（2026-10-23）：A 类跨平台修复（尾点占位/盘符路径）后重绑

> 重审（2026-10-23）：完整性锚点去缓存：批准与产物清单直接分块哈希，修复同 mtime/size 陈旧假命中

> 重审（2026-10-23）：终局稳定性：原子写 sink 收敛、测试隔离修复、验证卡册与 payload 重签

> 重审（2026-10-23）：I/O/内存/IPC 审计整改最终重绑：索引池、持久 IPC、原生绑定、缓存预算、OTLP 与协议防护

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护；最终生成链重绑

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

> 重审（2026-10-23）：Rust 快线加速收口：新增常驻 worker / PyO3 原语 / Rayon 解析并行与 code_metrics 接线；被审判据语义未变，digest 随实现同步

> 重审（2026-10-22）：H1：nf verify 仓库信任门（重冻）

> 重审（2026-10-22）：C1：判据缓存移出仓库（用户级+回退标记）（重冻·修订）

> 重审（2026-10-22）：C1：判据缓存移出仓库（用户级+回退标记）（重冻）

> 重审（2026-10-22）：S1：scratch GC 只删 nf-<12hex> + 根标记（重冻）

> 重审（2026-10-22）：R2：MCP 内部错误脱敏（重冻）

> 重审（2026-10-22）：基线修复：契约面只认仓库件 + doc 可达性 worktree-aware（重冻）

> 重审（2026-10-22）：rust 代码+串行段+TTL 修复合入后重绑

> 重审（2026-10-22）：rust FFI 契约面合入后机械重绑（2026-10-22）

> 重审（2026-10-22）：测试执行器与进程隔离修复后重算代码度量基线与角色投影；既有审计结论不变

> 重审（2026-10-21）：diag shard 1

> 重审（2026-10-21）：locales html 1

> 重审（2026-10-21）：readme head 1

> 重审（2026-10-21）：1.0.5 收口 1

> 重审（2026-10-20）：release line 0.x 1

> 重审（2026-10-20）：0.x renumber 1

> 重审（2026-10-20）：readme/tag 治理 1

> 重审（2026-10-20）：compliance 1

> 重审（2026-10-20）：version governance + daemon leak fix

> 重审（2026-10-20）：D 盘迁移：跨盘 relpath 修复（nf.py 展示面 + trust_boundary 用例）

> 重审（2026-10-20）：drill 正例对照（注入必红/原版必绿）后重算

> 重审（2026-10-20）：删除死代码后重算

> 重审（2026-10-20）：drill 误报清零（判定词边界+否定/历史语境）后重算

> 重审（2026-10-20）：风格全量收口（E501/UP006/UP031/SIM117）+ 权重补齐后重算

> 重审（2026-10-20）：风格棘轮收口（生成器级修复）+ 权重补齐后重算

> 重审（2026-10-20）：drill 真实转录裁定 + Rust asset_contract 三面接线后重算

> 重审（2026-10-19）：gate_labels 真值缓存指纹 + heredoc 修复

> 重审（2026-10-19）：摘取 W5 三修复并重冻度量基线后，被审承重件 digest 校准（结论未变）

> 重审（2026-10-19）：摘取 W1 纯度修复后重绑 atomic_write.py 被审对象 digest（结论未变）

> 重审（2026-10-19）：CRLF 归一后派生面重算：被审承重件 digest 校准，审计结论未变

> 重审（2026-10-19 · 逆向重构）：decisions.py 重写（值对象 + 规则表 + 结构化诊断，33 例）；行数重冻连带基线变更，subjects 按当前字节重绑

> 重审（2026-10-19）：度量重冻（nf.py +6 行：会话落点例外）

> 重审（2026-10-19）：度量重冻（conformance_scan +11 行：非仓库目录跳过）

> 重审（2026-10-19）：full 档也重叠 + 单分片内层线程按核数

> 重审（2026-10-19）：重测试再切分（机器面 16 片 / JSON 面 4 片）+ 内层线程 8/jobs

> 重审（2026-10-18）：LSP 时间窗判据进串行段

> 重审（2026-10-18）：串行段扩到内容快照族

> 重审（2026-10-18）：队列改动后重冻度量

> 重审（2026-10-18）：动态队列 + 常驻集收敛 + 分片上限 16

> 重审（2026-10-18）：mcp_runtime 增长后重冻度量上限（评审：+16 行，MCP 工具面扩充）

> 重审（2026-10-18）：CI 门禁矩阵化（32 片）

> 重审（2026-10-18）：P2：判定同根改跨进程比对 + 常驻集去掉 npm payload

> 重审（2026-10-18）：P2：串行段落地后重冻度量基线

> 重审（2026-10-18）：P3：缓存写走 atomic_write（脚本面纪律）

> 重审（2026-10-18）：P3：缓存脚本去掉删除面（保 Rust 快线 purity 口径一致）

> 重审（2026-10-18）：P2/P3 收口：CI 契约改 full 档 + 规模棘轮

> 重审（2026-10-18）：P3：缓存脚本收口（suppress 清理面）

> 重审（2026-10-18）：P3：判定缓存 + 分层档位（sink 登记）

> 重审（2026-10-18）：P3：分层档位 + 判定缓存 + 受影响测试选择

> 重审（2026-10-18）：P2：check12 分片并行（verify_tests 执行器 + 权重基线）

> 重审（2026-10-17）：步骤4 收口：attest --selfcheck 接线 + 站点/覆盖率分母同步

> 重审（2026-10-17）：步骤4：卡册扩段D（check41/42）+ 生成器识别段名直写

> 重审（2026-10-17）：步骤4：新增 check41/42（构建隔离 + 不可伪造 provenance）与对应判据模块

> 重审（2026-10-17）：能力面挂账（回退一致性面 detail，保留能力校验）

> 重审（2026-10-17）：能力面挂账：assertions.json 增 capability_vocabulary/index + 每条断言 capability

> 重审（2026-10-17）：并行的守护隔离：三种粒度（整个 NF_HOME / 只 cache 共享 / 只状态文件）实测全部与既有测试契约冲突，已全部撤回；保留 storage.cache_root() 单点派生（行为等价）与 daemon.state_path 的「为何不加覆盖」结论注释

> 重审（2026-10-17）：并行测试套件结论：撤回每模块独立 NF_HOME（实测 NF_HOME 124MB/10387 件、且 test_quality_depth_scan 依赖 cache 热度：冷 home 下扫描器调用 9 次 vs 基线 8 ⇒ 隔离净亏）；改为把 test_cli_json_face / test_cli_error_framing 补入独占串行段（二者遍历整条 CLI 面，daemon bench 直打守护单例）

> 重审（2026-10-17）：并行测试套件：每模块独立 NF_HOME（根治守护单例互踩——实测 test_cli_json_face 的 daemon bench 因共享 home 拿到降级 dict 而红）

> 重审（2026-10-17）：并行子 check 收口：verify_checks 的 JSON 解析改走 core.json_doc（未校验裸 reads 棘轮判红）+ 清未用 import；两处均为我引入并被既有判据抓出

> 重审（2026-10-17）：整批毫秒路径深入：nf verify 增 --jobs（每 check 独立子进程跑 --only N --json，按 check 号排序合并）；机器面增 messages 使并行结果可重放文案；实测 18.6s→6.4s（2.9x）且人读面/机器面与串行逐字节一致；新增 test_verify_parallel_checks 4 条判据（等价+排序+fail-closed）

> 重审（2026-10-16）：守护毫秒级路径第二根因修复：嵌套会话（nf verify→check39→shell --verify --deep）的 session_watch.release() 无条件拆掉守护自己的监听并清响应缓存 ⇒ 代际恒 None、缓存永久停用；改为显式所有权栈（attach 记录「自己装的+装载前外层」，release 恢复外层且不动其缓存）+ test_watch 两条守门判据

> 重审（2026-10-16）：门禁提速（收口）：修 check30 批量化引入的两处路径归一缺陷（git quotepath 非ASCII转义 + Windows glob 反斜杠）——被 test_check30_bump 当场抓出；另打破 gate_engine↔subcheck_cache 模块环（依赖倒置，只回稳定字段字典），并补两处静默兜底理由

> 重审（2026-10-16）：子check缓存订正：①目录项哈希不做 mtime 记忆（实测 Windows 同瞬新增条目 mtime 不变⇒假命中，按 ADR-0002 否决该优化并立守门判据）②快照默认不收祖先目录（check39 目录面 24718⇒命中复核 10.6s vs 重算 10.12s，净亏）③过滤解释器自身路径（check33 曾报 948 条仓外字节码读⇒永久不可缓存）

> 重审（2026-10-16）：守护响应缓存修复：watch._IGNORED_DIRS 增 .rivet（本仓内部档案区，实测 1.7GB/24403 件、每次会话都在写 ⇒ 缓存永远命中不了）与 __pycache__；实测 .rivet churn 不再推进代际，响应缓存稳定 0.11s

> 重审（2026-10-16）：子 check 缓存（步骤①）：新增 core/subcheck_cache.py（观测读面+目录项快照+内容寻址，fail-closed）+ gate_faces 增目录列举收集器；实测审计：观测开销 1.4–2.2x，大树遍历 check 命中收益被快照成本吃掉

> 重审（2026-10-16）：派生面重冻（verify.sh 注释增补后）

> 重审（2026-10-16）：本波（L-D 并行）：新增 scripts/verify_parallel.py（并行跑法）+ dotnet 判据补运行时探测；派生基线随之重冻，按本仓流程重绑 digest

> 重审（2026-10-16）：门禁提速批（补3）：删掉 gate_native 未使用的 _banner（死代码判据抓到）+ 同步 Rust 侧 SINK_ALLOW（gate_inproc.py:exec）；被审对象字节已变，重绑 digest

> 重审（2026-10-16）：门禁提速批（补）：gate_inproc/gate_engine 的静默兜底补成文诊断（silent-skip 判据要求）+ gate_labels docstring 改 raw 修无效转义；被审对象字节已变，重绑 digest

> 重审（2026-10-16）：门禁提速批（收尾）：清掉拆件后残留的未用导入（typing.*）+ 修 PENDING 重复键 8（F601 抓出）+ 新文件按现代语法归一；被审对象字节已变，重绑 digest

> 重审（2026-10-16）：门禁提速批（续）：拆 gate_native 让引擎回到行数闸门内 + check37 走 runpy 进程内执行，gate_inproc 增 run_script；被审对象字节已变，按本仓流程重绑 digest

> 重审（2026-10-15）：门禁提速批：测试面进程内化（check12 热点）+ 新增 gate_engine/gate_labels 单进程门禁引擎 + 派生基线重冻；被审对象字节已变，按本仓 rebind 流程重绑 digest

> 重审（2026-10-14）：预推收口二：CoT 自述改口径 + 快路径末尾 ** 语义对齐 pathlib（实测 66217 vs 0）

> 重审（2026-10-14）：收口：长行/导入序/静默跳过理由/风格基线重冻（评审）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI + 顺序纪律）：重审并更新 digest 机器化

> 重审（2026-10-14 · 数字资产契约 S 档：包自述对账 / Frictionless 导出 / 可移植 schema）：被审对象随本波改动（组合包 INDEX 补登 SYSTEM_CARD 契约 / receipts 锚定面续扩 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / core/layer_model.py 由 nf layers --write 联动刷新职能投影 / code_metrics 基线重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 L11 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / desktop/src/core/layer_model.py 接 L11 / docs/layers.md 生成区刷新 / protocol/code_metrics_baseline.json 按工具指引重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因该模块行数增长按工具指引重冻。

## 一、内部差距（开工依据）

- `json_schema._check` 复杂度 **84（F）· 单函数 142 行**：JSON Schema 子集的**十一类关键字**（unsupported 登记 / $ref / type / const+enum / 字符串 / 数值 / 数组 / 对象 / allOf·anyOf·oneOf / not）全在一个递归函数里。

## 二、交付

| 面 | 落点 |
|---|---|
| 按关键字类拆 | `_collect_unsupported` · `_check_ref` · `_check_type` · `_check_const_enum` · `_check_string` · `_check_number` · `_check_array`（+`_check_unique_items`/`_check_prefix_items`/`_check_items`）· `_check_object`（+`_check_required_fields`/`_check_property`/`_check_property_names`）· `_check_combinators`（+`_report_combinator`）· `_check_not`；`_check` 本体（**5·A**）只做深度守卫 + 分派 + 汇总 |
| 回退单点化 | 新增 `_obj` / `_arr`（`or {}` / `or []` 回退） |

## 三、验收证据（本机实测）

- `radon cc desktop/src/core/json_schema.py`：`_check` **84(F) → 5(A)**；各关键字校验器最大 10。
- `radon cc desktop/src`：**≥C 312 → 311 · ≥D 92 → 91 · F 13 → 12**；全量最大圈复杂度 **84 → 83**（`pack_combo.combine`）。
- `python -m unittest desktop.tests.test_output_forms desktop.tests.test_trust_boundary desktop.tests.test_schema_reference` → **65 例全绿**。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. **行为等价性**：纯分派重构，递归语义（`_depth+1`、`root_schema`/`unsupported` 透传、错误顺序）逐条保持；65 例单测双覆盖（输出形态 + 信任边界）全绿。
2. **指标方法学（七批定论）**：radon 把每处 `or` 记一个分支，因此「满屏 `or {}`」的文件天然虚高；**按面拆必须配合回退单点化**才能净降 ≥C。
3. 余量：全仓仍有 **12 个 F**，最大 83（`pack_combo.combine`）；`render_markdown` D(26) · `prov_document` D(30) · `openapi_doc` D(25) 等生成器为下一批候选。
4. 62 §三·②「量化门违反」与 §二·2 .NET 重冻不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑↑ | 最大圈复杂度 150→83（七批累计）；65 例单测 + 全量 verify 双绿 |
| 动态可执行 | → | 不涉执行面 |
| 架构纯度 | ↑↑ | 「一类关键字一个校验器」；递归本体退化为分派器 |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
