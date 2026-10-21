---
id: AUD-0033
title: 类型分批收敛第六批（terminal / assemble_plan / asset_ledger / atomic_write 归零）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」；承接 AUD-0032。开工依据为内部实测（mypy desktop/src 错误条数 68）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/terminal.py:37c4486281a7ba74eca28079fa4198d3cfb484457259996a082dc0c629edddef
  - desktop/src/core/assemble_plan.py:2c73997d32e042ac41ed642e63c9404497925868465f0f1d30b5115672c60f35
  - desktop/src/core/asset_ledger.py:245d911c417e3d37944a834e0a408ddf33b7491803edd7fe5bfaf132e8f8a6ba
  - desktop/src/core/atomic_write.py:f9c723fbc7dc1b05ec8da28c7af512cc038fed8345c562c7e285d273db9c98ce
  - protocol/code_metrics_baseline.json:54356415382fef20fb2e8f208f9252e29374416c51afc50c4c5fe09fc3220be8
---
> 重审（2026-10-21）：locales html 1

> 重审（2026-10-21）：readme head 1

> 重审（2026-10-21）：1.0.5 收口 1

> 重审（2026-10-20）：release line 0.x 1

> 重审（2026-10-20）：0.x renumber 1

> 重审（2026-10-20）：readme/tag 治理 1

> 重审（2026-10-20）：release 1.0.4 1

> 重审（2026-10-20）：compliance 1

> 重审（2026-10-20）：repo hygiene: junk dirs removed, LF normalized

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
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因 `assemble_plan`/`atomic_write`/`terminal` 行数增长按工具指引评审后重冻。

## 一、内部差距

> 重审（2026-10-14 · 终端基线并发与 argv 唯一性）：被审对象随本轮改动（`baseline_tmp_dir()` 改为按进程唯一；`baseline_argv_issues()` 补 argv 唯一性；基线表 20→19 行）而变，subjects 依「重审并更新 digest」处置——**机械重绑**，既有结论不变。
（开工依据）

- 承接 AUD-0032：`mypy desktop/src` 错误条数 68；本批取 `terminal`（25，最大块）+ `assemble_plan`/`asset_ledger`/`atomic_write`（各 3/3/6）。

## 二、交付

| 模块 | 修前 | 修法 |
|---|---|---|
| `desktop/src/core/terminal.py` | 25 | **根因是四张模块级声明表**（`ZONES`/`FAMILIES`/`FORMS`/`TERMINAL_BASELINE` + `SLASH_WORDS`）无标注，值被推成 `object` 并沿调用面扩散；补 `tuple[dict[str, Any], ...]` 后一次性消掉 17 条。余：`seen`/`history`/`commands` 标注、`self.active_form` 显式可空、两处表单取值改写 |
| `desktop/src/core/assemble_plan.py` | 3 | `questions`/`answers` 参数由 `List[str]` 改 `Sequence[str]`（默认 `()` 合法）；`pkg`/`pipeline` 显式可空；`if pkg is None or not matched` 收窄 |
| `desktop/src/core/asset_ledger.py` | 3 | `_load_for_update` 的 `ledger_path` 如实标 `str \\| None`（函数内本就 `or default_...`）；`issues` 标注 |
| `desktop/src/core/atomic_write.py` | 6 | 读回函数由「`**kwargs` 三元」拆成 binary/text 两分支（消 `open` 重载歧义）；`fcntl` 两行加 `# type: ignore[attr-defined]`（typeshed 平台面） |

## 三、验收证据（本机实测）

- `python -m mypy desktop/src --ignore-missing-imports` → 错误条数 **68 → 31**（四受改模块各自 rc=0）。
- `python -m unittest desktop.tests.test_terminal desktop.tests.test_nf_tui desktop.tests.test_assemble_build desktop.tests.test_asset_ledger desktop.tests.test_atomic_write` → **237 例**（中途一次 1 例红，见下）。
- **过程实证（值得记）**：`terminal` 两处表单取值首版写成 `active.get("answers") or {}`——空字典是假值，`or` 会返回**新字典**，于是 `_answer_form` 的写入不再落回 `self.active_form["answers"]`，`FormTest.test_session_form_flow_executes_after_confirm` 当场判红；改为 `active["answers"] if active else {}`（保留原对象引用）后转绿。这条正是「行为不变」承诺的看门判据。
- `python scripts/code_metrics.py` → 三模块行数增长按工具指引重冻。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. 余 **31 条**（`nf.py`/`scripts` 面与零散 core）；radon 复杂度未动。
2. `atomic_write` 的 `fcntl` 用**两处** `# type: ignore`（仓库首次引入该逃生口）：理由是 typeshed 的 `fcntl` 面随平台收窄，而该分支只在 Unix 执行；已就地写明，不建豁免表。
3. 62 §三·② 余量与 §二·2 .NET 重冻不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑↑ | 四模块 mypy 归零（含最大块 terminal）；237 例单测 + 全量 verify 双绿 |
| 动态可执行 | → | 不涉执行面 |
| 架构纯度 | → | 只改类型写法与取值方式（含一处别名回归的修正） |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
