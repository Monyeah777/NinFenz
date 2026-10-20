---
id: AUD-0026
title: 文档面 i18n 扩容（mcp/terminal/layers 三份指南 en/ja）+ 演练扩面（跨管线串号 / 资产键编造 / 回合级 R1–R4 样本）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——对应 62 计划 §二·3 文档面 i18n 扩容与 §三·② 演练仿真扩面；开工依据为内部差距实证（文档面仅 2 份指南有译件；失范类型与回合级样本覆盖不全），不引外部背书。
verdict: pass
auditor: 本轮执行者
subjects:
  - protocol/locales.json:f3c161634feafbeeecc0b3aea8bde8a3733fa45b01bc42bc5713e6206f4afc34
  - docs/locales.md:cf3a21039dad98832b3cd92ead92adaa6559b38bd9c96006fea87f0af81a6dc7
  - docs/en/locales.md:348a2b32a6f04cf830cb332b47b0b05f59265332c2fe37ec79ee63c0563168fa
  - docs/ja/locales.md:7f870e599fc00ab10c998eb115350b7ceda21655a2ebfcf870f6a2b8300e5f34
  - docs/en/mcp.md:0653be472bb4888c814d3fc3696e7d882b35c6e49b965cf09b84d41d34c8d6f0
  - docs/ja/mcp.md:a7a248172cc0119e023b1ed7e5e2c254b3b3db3d357f76e7e6a322e41538ddf2
  - docs/en/terminal.md:b99ee9b83dd9bcc433b97408785e85b8f265d797eb144abc09c8e0bcae97d046
  - docs/ja/terminal.md:ae1b37be3309ff21f7bd2096b0295ee073e493ec7bb402c3672ef9f5a72d168e
  - docs/en/layers.md:f92b4dcea20068c253a2a7455d21fb63bbf3c9493e80f81cb6460d4e464d6c20
  - docs/ja/layers.md:1f3edfbad694b98228bb720574a54267f7b3b544fbc89436179d77950fde3d57
  - docs/44_M1_执行演练扩展.md:12e58d6ae4d1cab23faaaff5e98d0a0bc9a6455c7a17552bab0d57e0cf30866c
  - docs/45_M2_回合级drill.md:55bf60d989aba4fe653bd30396b59c12af587151a3b100da9b65f3d2979429e0
  - desktop/src/core/execution_drill.py:61337ffd5f93bca3cc2519e0f84c9f02f15d44c55ee74ed14acadc63538dd48b
  - desktop/src/core/drill_fidelity.py:a53d9366287ab64431787b2d5b389c3179f22b0cd6c0ca7a091cb86ac07ae190
  - desktop/tests/test_execution_drill.py:f9df38b1f586fd4a705e608bf849b510ed217c8b38fd1dd68ab78176b2dcb02d
  - desktop/tests/test_round_drill.py:0a0997e935ce8cd417a7400fbaf2c897853e82297867f25165c9889117667a1a
  - desktop/tests/fixtures/execution/p04_drill_cases.json:9237e2713bab59df20ed8cc4df18f8a4f9bd1fe0437a4acf642b03ccdd9c5d07
  - desktop/tests/fixtures/execution/rounds/bad_r2.json:9498fba916ea03db23cd75fb9279335ad92127850aab54adb73f5032f6b20d24
  - desktop/tests/fixtures/execution/rounds/bad_r3.json:985bc52b5a755bb6ca33a94817cb706beb9bfe6d9d13f7933f7bbcfe0ca46e8a
  - desktop/tests/fixtures/execution/rounds/gap_ok.json:55d09b1102f7729f31439fd68cf8ad25c7e0db55e0a9064db713a0ee582d4914
  - protocol/code_metrics_baseline.json:adaad308850f8dc6592d1c07415847c27444d8838e00e8e5b40ea5634874c82a
---
> 重审（2026-10-20）：compliance style fix

> 重审（2026-10-20）：notices generator hardened

> 重审（2026-10-20）：third-party notices + community provenance gate

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

> 重审（2026-10-19）：EOL 归一 + 译件重签

> 重审（2026-10-19）：度量重冻（conformance_scan +11 行：非仓库目录跳过）

> 重审（2026-10-19）：full 档也重叠 + 单分片内层线程按核数

> 重审（2026-10-19）：重测试再切分（机器面 16 片 / JSON 面 4 片）+ 内层线程 8/jobs

> 重审（2026-10-18）：工具名归一：6 个旧名 -> _list/_search/_read；旧名 alias；官方 tdqs 4.9 两次

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

> 重审（2026-10-18）：Glama coherence：新增 pattern_ls/asset_ls；asset_read 兼容别名；同步 12 工具面

> 重审（2026-10-18）：Glama coherence：asset_read 兼容别名说明（中/英/日）

> 重审（2026-10-18）：Glama coherence：asset_get→asset_read（旧名兼容别名）+ 协议边界描述；行尾规范为 LF

> 重审（2026-10-18）：Glama coherence：MCP 面 asset_get→asset_read（旧名保留兼容别名）；spec_ls/registry_query 描述边界

> 重审（2026-10-18）：P3：缓存脚本收口（suppress 清理面）

> 重审（2026-10-18）：P3：判定缓存 + 分层档位（sink 登记）

> 重审（2026-10-18）：P3：分层档位 + 判定缓存 + 受影响测试选择

> 重审（2026-10-18）：Glama 上架：docs/mcp.md 增加容器/Glama 一节，英文/日文译件同步并重签 locales；根 Dockerfile 按 check41 钉基座 digest

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
> subjects 不含派生物：`protocol/RECEIPTS.json`、`protocol/conformance_report.json`、`protocol/generated/*`、`results/interop/*`、`protocol/approvals/*` 均为可复算投影或每次重签即变；`protocol/drill_fidelity.json` 由 `scripts/drill_fidelity.py` 从样本重算，同样不入绑定。

## 一、内部差距

> 重审（2026-10-14 · 终端基线并发与 argv 唯一性）：被审对象随本轮改动（`baseline_tmp_dir()` 改为按进程唯一；`baseline_argv_issues()` 补 argv 唯一性；基线表 20→19 行）而变，subjects 依「重审并更新 digest」处置——**机械重绑**，既有结论不变。
（开工依据）

1. **文档面 i18n 只覆盖 2 份指南**（`docs/locales.md` 自述「发布」与「本地化」），而对接方第一跳 `docs/mcp.md`、agent 人机入口 `docs/terminal.md`、架构面 `docs/layers.md` 仍单语——注册机制（文件即真源 + 声明式增长）已立，缺的是译件本身。
2. **执行失范类型只有 4 类**（句子级 fabricated_id / browse_repeat / no_citation / semantic_misalignment），62 计划点名的「跨管线串号」「资产键编造」无判据——编号真实但属其它管线、资产键编造会**静默通过**。
3. **回合级样本只覆盖 R1**（`bad.json` 同时命中 R1/R3；R2 与 R4 跳号无语料）——**样本集覆盖 ≠ 断言集覆盖**。

## 二、交付

| 面 | 落点 |
|---|---|
| 文档面译件 | 新增 `docs/en/{mcp,terminal,layers}.md` + `docs/ja/{mcp,terminal,layers}.md`（逐节镜像；代码块/命令/路径/内联锚点逐字保留） |
| 语言面注册 | `protocol/locales.json` 文档译件 2 → 5 份（10 件译件）；`docs/locales.md` 及两语译件覆盖面声明同步；`nf locales --write` 重签 source_sha256 |
| 句子级失范扩容 | `core/execution_drill.py` 增 `cross_pipeline_id`（跨管线串号：编号真实但属其它管线）与 `fabricated_asset_key`（资产键编造）两条硬断言；`RULE_LAW` 4 → 6 条（L1×1 / L2×3 / L3×1 / L4×1，无越级） |
| 演练语料 | `p04_drill_cases.json` 8 → 12 例（+2 失范 +2 变异对照），新规则各有「命中 + 不误报」成对样本 |
| 回合级覆盖 | `rounds/` 新增 `bad_r2.json`（R2）/ `bad_r3.json`（R3）/ `gap_ok.json`（R4 跳号仅 WARN、verdict 仍合规） |
| 判据 | `test_execution_drill` / `test_round_drill` 增例；判级映射断言 4 → 6；`drill_fidelity._exec_sets` 透传 other_ids/asset_keys |
| 量化 | `protocol/drill_fidelity.json` 重算：执行 60 例 + 回合 5 例 = **65/65（100%）** |
| 文档 | `docs/44_M1_执行演练扩展.md` / `docs/45_M2_回合级drill.md` 口径同步 |
| 基线 | `protocol/code_metrics_baseline.json` 重冻（新增规则使 `execution_drill` 行数/圈复杂度上升，按工具指引「确需上调须评审后重冻」执行） |

## 三、验收证据（本机实测）

- `python scripts/verify_run.py`（= `bash verify.sh`）→ **PASS=72 · WARN=0 · FAIL=0**。
- `nf locales` → zh/en/ja · 文档译件 **10 件** · rc=0。
- `python scripts/drill_fidelity.py --write` → 总保真 **100%（65/65）**。
- `python -m core.execution_drill p04_drill_cases.json` → 12 例全过（失范无漏报、guard 无误报）。
- `python -m unittest desktop.tests.test_execution_drill desktop.tests.test_round_drill desktop.tests.test_drill_fidelity` → **18 例全绿**。
- `nf conformance --write` → conformant **27/27**；`nf receipts --scope protocol --write` 根一致（57 件）；`python scripts/verify_report.py --write` → 判据 28 条 PASS 27 / FAIL 0 / WARN 1。

## 四、遗留与设计偏差

1. 62 计划 §三·② 的三条方向**只完成两条**：失范类型补 2 类（仍缺「量化门违反」，须先定「门」的数值口径，未编造）、回合级 R1–R4 样本补齐；**多语协议执行未做**——`execution_drill` 的决策/引用/推进正则仍是中文口径，扩多语须先立词法面。
2. 译件属**译者责任**（机制不做机器翻译）；判据只保证「声明的都在场且不过期」。译件与原文不逐行等长（原文硬换行），但标题层级、代码围栏、命令与内联锚点已机械核对一致。
3. 62 计划 §二·2`.NET 线重冻`**本地未完成**：实测卡在引擎与 Python 真源漂移（prose_lint cli 106↔107、深化面 FAIL 2↔0），非夹具重签可了结；实测与复现路径见内部档 `.rivet/private_archive/62_附录_dotnet重冻本地实测_2026-10-05.md`（不入库）。
4. 62 计划 §二·1「首例发布」、§三·① 存量复杂度/类型收敛未在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑ | locales 判据现覆盖 5 份指南；drill 断言 6 条各有判级映射；code_metrics 重冻有本件评审记录 |
| 动态可执行 | ↑↑ | 两类新失范在真语料上「命中 + 不误报」成对；回合级 R1–R4 样本覆盖，保真度 100% |
| 架构纯度 | → | 新判据落在既有 `execution_drill` 单一实现内，不新增模块/check 序号 |
| 资产密度 | ↑ | +6 份译件、+4 条演练语料（含一组新对照） |
| 文档可执行性 | ↑ | 对接方第一跳 mcp / 终端 / 台阶三份指南补齐 en/ja；演练口径随实现同步 |
