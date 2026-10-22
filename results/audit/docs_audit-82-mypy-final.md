---
id: AUD-0034
title: 类型分批收敛收尾（desktop/src 剩余 31 条全部清零，24 模块）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」；承接 AUD-0033。开工依据为内部实测（mypy desktop/src 错误条数 31）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/silent_skip.py:7a9e953f959d31161f29dcb5de4ef755a63d31ff807bdf333403c4b048f07457
  - desktop/src/core/round_drill.py:0407fc814cbb7ea5bc610036a4cf3e4675977eaaf5b7fa11fa142e32d6504c0b
  - desktop/src/core/quant_metrics.py:ae2bd5a5b71531ee4cf4abe920f75a939a30a5bea105efa7aed011cc92369ce3
  - desktop/src/core/module_lifecycle.py:7b84396342e77fea32e6b54cd78e296f1dddf925937b8331dbcdebeb4e9ad1d0
  - desktop/src/core/market_analyzer.py:eb5edffc55470b5f4aa8e6151ab7bffded36a45ce3ecc69fcdc54de59071cbdf
  - desktop/src/core/protocol_golden.py:b37b80ee8691fd76ed2df41f5006285c92914449bdfd6a2210164c7bc1f3e353
  - desktop/src/core/knowledge_sig.py:2e1177ae8701b38cff3b26e92892b3cbef4a347a48b986dd8b1f95934f60323b
  - desktop/src/core/output_forms.py:3688d30b158493f56801ef84f6f0e60eff2cc670c7ebcf750ffd403599d1b68a
  - desktop/src/core/pipeline_loader.py:4c58b842a8b79abdce6917305f8f5c307e4334cfa377cb3dc1b9d6f226871588
  - desktop/src/core/community_inventory.py:1cd42c4d2588a5facbb26aa3b1216e39d8b0ba0e407694ef441ab9c51e38cf00
  - desktop/src/core/retriever.py:97409e06af9b66d2b30bfde8a660d90b661c008bfe002b0b0712b824c7f6c9c4
  - desktop/src/core/lazy_yaml.py:127a18733214df1a721ad9e2fad8c0bc8cc195a4ee2f7fc782a60f85eb24d641
  - desktop/src/core/json_schema.py:f3a4a6a14de5104e217af8b154505f9ca46fd6133081188209add78143e2b23e
  - desktop/src/core/export_schema.py:9052dc891be0c70ceb5b42544eceeceeeb4dee8c4f107b1ec660913cf922ad3d
  - desktop/src/core/orchestration.py:6c860bebc068000dbd8f7a68103b300ab662c0666c912159226f015cea43327c
  - desktop/src/core/machine_contract.py:8b1bb40cdacac3e1104baa90e4c16d433c4db58983144e30764dc61e08f6c541
  - desktop/src/core/decisions.py:ea111202d12e1079a85dec047e55f556496312a4cfb3da659e6b1ae1cf3b52c1
  - desktop/src/core/layer_model.py:7464fad8e9703b76b6582a641fb80c5a93c4bbf87b5d2aad191e610eafe64dd2
  - desktop/src/core/import_graph.py:2ea0fe79cf12e2f9bdb6078af0a08287ae062fc0f4f3e6136e3b240c0d11123a
  - desktop/src/core/bench.py:5d7ef263ca30a9888f2c32f4db2253406dfdc510b52fbb19958a3afefe9cf574
  - desktop/src/core/import_adapter.py:7b68a8c20b1a1cc4acf78ca0b27e0752d49d509d49916539ce4a7ad38622cf1b
  - desktop/src/core/daemon.py:2e028d8f43860579117497de3b5f856f5803cdcd873a58005e4b392b0042a7bd
  - desktop/src/core/decision_layer.py:f230aa31538f795d3a75a9cef9a109d323374cd8edbfc79c577df3e6378c31b7
  - desktop/src/core/exporter.py:d396f742ccf012331c855c4f52f0925daebc6100cadff30d4e1f510a9dff4c04
  - protocol/code_metrics_baseline.json:51e09a236e93e8513acf8a440f0568a625a2b029804c0ca58d1b46e3272ec577
---
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

> 重审（2026-10-19 · 逆向重构）：decisions.py 重写（值对象 + 规则表 + 结构化诊断，33 例）；subjects 按当前字节重绑

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


> 重审（2026-10-14 · ADR-0006）：`decisions.py` 的模块自述按「取代链互指由测层常驻判」更正（**行数不变**，仅同一行换文案），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因 7 个模块行数/圈复杂度增长按工具指引重冻。

## 一、结果

`python -m mypy desktop/src --ignore-missing-imports` 错误条数 **31 → 0**（默认口径）。

## 二、交付（按修法归类）

| 类 | 模块 | 修法 |
|---|---|---|
| 真标注错配 | `import_graph` | `parse` 标注写成 3 元组而实现返回 2 元组 `(deps, dyn)`、调用方也按 2 元组解包——三处只有两处一致；标注改为 `Optional[Tuple[frozenset, bool]]`，两处差错同消 |
| 变量复用解耦 | `round_drill`（allowed→allowed_set）· `orchestration`（tools→wf_tools）· `export_schema`（e→entry） | |
| 声明/集合显式类型 | `module_lifecycle` · `market_analyzer` · `pipeline_loader` · `community_inventory` · `retriever` · `knowledge_sig` · `silent_skip` · `decisions` · `machine_contract` · `exporter` · `decision_layer` | 补 `dict`/`list`/`Dict[str, Any]` 标注 |
| 可空收窄 | `bench`（局部 match 判空）· `daemon`（spec is None 守卫）· `import_adapter`（body 拆原始值）· `json_schema`（py: Any） | |
| 平台/属性 | `lazy_yaml`（os.sys→import sys）· `layer_model`（getattr(node, lineno, 0)） | |
| 数值文本 | `quant_metrics`（float(x or 空串)，与原 float(None) 同落 except） | |
| 键归 str | `output_forms`（str(f.get(category))）· `protocol_golden`（str(len(...))） | |

## 三、验收证据（本机实测）

- `mypy desktop/src` 错误条数 **31 → 0**。
- `python -m unittest`（本批相关 19 组）→ **282 例**（skipped=1）全绿。
- `python scripts/code_metrics.py` → 7 个模块行数或圈复杂度增长，按工具指引重冻。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. **范围限定**：本次清零的是 `desktop/src`（core 库）；`scripts/**` 与 `desktop/tests` 未纳入本线。
2. radon 复杂度仍为存量；62 §三·② 余量与 §二·2 .NET 重冻不在本件范围。
3. `import_graph` 的标注错配是真缺陷面（三处不一致），但运行时按实现走、未产生错误行为；本件只校准标注，不改运行路径。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑↑ | desktop/src mypy 归零；282 例单测 + 全量 verify 双绿 |
| 动态可执行 | → | 不涉执行面（两处守卫均收窄到原路径） |
| 架构纯度 | → | 只改类型标注/变量命名 |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
