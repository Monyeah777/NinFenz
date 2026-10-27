---
id: AUD-0020
title: 域包自由组合引擎（任意 n 元 × 任意组件）：五不变量 + 传递闭包 + 广度证明（5671 两两全合法）+ 可复算证书
date: 2026-09-23
scope: 作者目标「将所有域包达到任意几个域包可自由任意组合，包内组件（协议/管线/模块/资产）可自由任意组合，理论广度无限组合，深度质量保证，产出组合可机验」——本件记录：组合引擎与五不变量、传递闭包、广度证明实测、证书与门禁、以及引擎抓出并修掉的既有组合包真实缺口
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/pack_combo.py:5fe16225b1586d5ebf4c8faf1901f0225297dd9af7c2ba0778e86707d24ed525
  - desktop/src/core/quality_depth_scan.py:563059e8a929bbbba16d5d15a9c77d1f362f9518351860b5ca0682aeb07a23f9
  - desktop/src/core/doc_hygiene.py:5cc5d9d0fe0bea3f609d26759ac497aeb92363b0c6b045c1ca6cd67687bae850
  - scripts/nf.py:1174ad828e80be50c73e351142cd28d8610413f8134766ece3f14b8f0b9e860f
  - protocol/data_contracts.json:5f04df741065b77993b150f37c0c5c0a7ba3465acbabcca3ee39ac103b578132
  - docs/combos.md:4d25fe6d366687213df7090badd52b815bdf07f774df856e598d7cf8a1d130de
  - desktop/tests/test_pack_combo.py:38d6fbc122264bcd205e6d5cb8baac1a1a581f1cb8a43da2c12691e57314b0a6
  - community/校园西幻轻混组合包/protocol.yaml:093cc817ae089981b7cfe4aaf57ec7f5d2374455bb63fc8b7af06dc2d29a02a3

---
> 重审（2026-10-27）：S2p: verify split by responsibility -> nf_cmds/verify.py

> 重审（2026-10-27）：S2o: shell split by submode -> nf_cmds/shell.py (callables injected)

> 重审（2026-10-27）：S2n: assemble split by phase -> nf_cmds/assemble.py

> 重审（2026-10-27）：S2m: module split by subcommand -> nf_cmds/module.py

> 重审（2026-10-27）：S2l: library split by subcommand -> nf_cmds/library.py

> 重审（2026-10-27）：S2k: asset split by subcommand -> nf_cmds/asset.py

> 重审（2026-10-27）：S2j: knowledge split by subcommand -> nf_cmds/knowledge.py

> 重审（2026-10-27）：S2i: doctor split into check helpers -> nf_cmds/doctor.py

> 重审（2026-10-27）：S2h: domain handler split into subcommands -> nf_cmds/domain.py

> 重审（2026-10-27）：S2g: lazy json_doc -> common; combine/output/market -> nf_cmds/shelf.py

> 重审（2026-10-27）：S2f: sig/diff/telemetry/changelog/receipts/layers/attest/runtime/agent -> nf_cmds/misc.py

> 重审（2026-10-27）：S2e: integrate-family handlers -> nf_cmds/integrate.py

> 重审（2026-10-27）：S2d: govern-family handlers -> nf_cmds/govern.py

> 重审（2026-10-27）：S2c: library-family handlers -> nf_cmds/library_ops.py

> 重审（2026-10-27）：S2b: verify/meta handler group -> nf_cmds/surfaces.py

> 重审（2026-10-27）：S2a: shared CLI helpers -> scripts/nf_cmds/common.py

> 重审（2026-10-27）：S1: rebuild governance after CRLF->LF normalization

> 重审（2026-10-27）：S1: extract nf.py::_make_parser into scripts/nf_parser (surface byte-identical)

> 重审（2026-10-27）：Merge W12: check46-47 + bilingual glossary

> 重审（2026-10-27）：T12.2 英文术语层：新增 protocol/glossary.json entries（33 条双语术语）+ core/glossary.py + nf glossary check/render + docs/protocol/glossary.en.md；新增顶层命令 glossary 与 terminal FAMILIES/命令地图重生成；按冻结上限重冻 code/coupling 基线并重绑对象 digest

> 重审（2026-10-27）：Merge W11: content SRE + privacy/air-gap + CLI map

> 重审（2026-10-26）：W10: register concept graph index as data contract + assertion

> 重审（2026-10-26）：Merge W10: model check + concept index + agent contracts

> 重审（2026-10-26）：T9.2 导入器：新增 core/import_docx.py、core/import_dita.py 与 nf import docx|dita（scripts/nf.py 增长），按冻结上限重冻 code/coupling 基线；按审计协议重绑对象 digest

> 重审（2026-10-26）：Merge W8: JS second impl + registry CID + security scan

> 重审（2026-10-26）：Merge W7: contract semantics + content IR + reference runtime

> 重审（2026-10-26）：T7.2 内容 IR：新增 desktop/src/core/content_ir.py 与 nf ir check 命令（scripts/nf.py 增长），按冻结上限重冻 code/coupling 基线；按审计协议重绑对象 digest

> 重审（2026-10-26）：Merge t-m1/t-record/t-bench: M1 evidence rule, exec record, bench leaderboard

> 重审（2026-10-26）：Merge t-maturity: M0-M3 evidence-based maturity + registry projection

> 重审（2026-10-26）：Merge t-scope: scoped allowed_module_ids + --loose

> 重审（2026-10-26）：Merge t-identity: deliverable-contract first screen + demo/presets/library ordering

> 重审（2026-10-26）：Wave2: SSOT facts.json + domain gate + gate manifest

> 重审（2026-10-26）：rebase 到 fa3fdd58 后重冻（atoms/nf/perf_budget）

> 重审（2026-10-25）：Scorecard 收口：最新 main 合并、CODEOWNERS ASCII 化、SAST/Fuzzing、最小权限、依赖漏洞与容器 digest 统一重绑

> 重审（2026-10-25）：1.1.0 版本面 + CLA workflow + 定价

> 重审（2026-10-25）：跨平台收口：真实路径归一、守护状态读写锁、autostart 原子标记与机器路径短名脱敏

> 重审（2026-10-24）：夜间收口：Rust worker 安全、投稿配额、元数据、schema 与 postmortem 跨平台回执路径修复后按新输入重绑

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

> 重审（2026-10-23）：Rust 快线加速收口：新增常驻 worker / PyO3 原语 / Rayon 解析并行与 code_metrics 接线；被审判据语义未变，digest 随实现同步

> 重审（2026-10-22）：H1：nf verify 仓库信任门（重冻）

> 重审（2026-10-21）：1.0.5 收口 1

> 重审（2026-10-20）：release 1.0.4 1

> 重审（2026-10-20）：repo hygiene: junk dirs removed, LF normalized

> 重审（2026-10-20）：version governance + daemon leak fix

> 重审（2026-10-20）：D 盘迁移：跨盘 relpath 修复（nf.py 展示面 + trust_boundary 用例）

> 重审（2026-10-19）：nf.py 会话落点放行 .rivet（受限环境唯一可写临时区）

> 重审（2026-10-18）：工具名归一：6 个旧名 -> _list/_search/_read；旧名 alias；官方 tdqs 4.9 两次

> 重审（2026-10-18）：Glama coherence：收紧 spec_ls/registry_query 描述边界；asset_get 说明为协议资产五接口规范名

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

> 重审（2026-10-14 · 数字资产契约 S 档：包自述对账 / Frictionless 导出 / 可移植 schema）：被审对象随本波改动（组合包 INDEX 补登 SYSTEM_CARD 契约 / receipts 锚定面续扩 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / core/layer_model.py 由 nf layers --write 联动刷新职能投影 / code_metrics 基线重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 8 件（组合引擎、聚合扫描、文档卫生表、CLI、数据契约登记、公开文档、单测、被修的既有组合包声明）；**不含派生物**（`protocol/combo_certificates.json` 由引擎可复算，是投影而非源）。

## 一、内部差距（开工依据）

1. 组合能力此前只有**一个手工战例**（校园西幻轻混组合包：2 模块 + 2 条 references），
   没有任何**引擎**：任取两个域包同装会怎样，仓库里答不出来。
2. 100 个域包全部在 P40/P60 挂 default —— 组合时的**层位堆叠**规则、**事件闭包**、
   **依赖闭包**、**资产借阅**四条都没有判据，也没有产出面。
3. 「广度」当时是**不可证**的声称；没有任何机制能说明「任意组合都成立」。

## 二、组合引擎与五不变量（从零构建）

`core/pack_combo.py` + `nf combine plan|breadth|verify`：

| # | 不变量 | 判据字段 |
|---|---|---|
| 1 | 模块唯一可定位 | `module_missing_contract` 必须为空 |
| 2 | 依赖闭合 | `dependency_closure.dangling` 必须为空（inputs ⊆ 组合内 ∪ 官方核心 13 件） |
| 3 | 事件闭合 | `event_closure.unbridged` 必须为空（核心模块的 publish 计入；无人发布者记 `events_unpublished`） |
| 4 | 层位堆叠确定 | `layer_stacks` 按**规范包序 → 模块 id**，与调用者给序无关 |
| 5 | 资产可寻址 | `assets_borrowed` 每条须在源包 provenance 台账，`assets_unresolved` 为空 |

**传递闭包**（本波的关键设计）：`references` 借入的模块会**递归**拉入其 `inputs` 与所需事件的
发布方，逐步记 `why`（如「事件 confession_event 需要发布方（M91 订阅）」）。

## 三、广度证明（不靠枚举）

| 规模 | 数量 | 合法 | 说明 |
|---|---|---|---|
| 两两（全集） | 5671 | **5671** | C(107,2) 穷举 |
| 三元（定种子抽样） | 400 | **400** | seed=20260923 |
| 四元（抽样） | 200 | **200** | 同上 |
| 极限（全 107 包同装） | 1 | **合法** | 235 模块 / 0 悬挂 / 0 未桥 |

单次组合求解 < 2 ms（画像 + 索引进程级缓存），check32 `combos` 子扫描（证书复算 + 广度）≈ 3 s。

## 四、可机验产出（证书）

`protocol/combo_certificates.json` **13 条声明证书**（极限 1 / 跨段对 3 / 三元 3 / 四元 2 /
先例 2 / 跨段对 1 / 组件级混搭 1）。机检三层：① 过 `CERT_SCHEMA`（自家 JSON Schema 子集）；
② 按 `packs + extra_modules` **重算**逐字段比对（T4，含 digest）；③ 广度不变量全成立。
组件级战例：只取三个包的 P40 模块 + 一个跨包只读资产（`量化金融域包:QUANT_METRICS`）→ 合法。

## 五、五条不变量在真实数据上抓出的问题（引擎价值）

1. **既有组合包声明与事实不一致**：轻混包模块订阅 `confession_event` / `npc_action` /
   `relationship_change` / `production_output`，但 `references` 只声明了 M55 与 M17——
   发布方 M43 / M22 / M40 未在册。修法：补 3 条 references（**只读借阅**）+ 包版本
   `1.0.0 → 1.1.0`（additive）+ 02 §9.6 四步迁移记录（check30）。
2. **核心发布事件被漏算**：首版引擎未把「官方核心 13 件随任意组合装载」计入事件闭包，
   导致 `chaos_event` / `minute_tick` 等被误报未桥；修法：核心发布集入闭包（事件面 0 误报）。
3. **层栈顺序非规范**：按调用者给序排序 → 同一组合两次给序不同则摘要不同（T4 假失败）；
   修法：层栈一律按规范包序，`digest` 与给序无关。
4. **旧包 module_id_range 解析漏项**：校园/西幻用「行式裸号 + 行尾注释」写法，首版正则只认
   全限定带引号形式 → 模块集漏到 1 个；修法：两种写法并集 + 容忍注释。
5. **广度性能**：首版每次组合都重解析 235 个模块文档 → 广度跑 174 s；修法：画像/契约/索引
   进程级缓存 → **3.2 s**（含 5671 两两）。
6. **「同源多引用」被两处独立实现误判成环**：轻混包补 3 条校园引用后，
   `core/market_analyzer.dependencies` 与 `verify.sh` check15 ② 各自把「同一源包的多条
   references」当成多条边 → 报「依赖闭包成环」。修法：两处都按**包级依赖去重**
   （同源多引 = 一条边），并加回归测试 `test_multi_reference_same_source_is_one_edge`。
7. **投影测试硬编码引用条数**（`== 2`）：引用条数会随真实依赖增长 → 改为从声明件推导
   （`≥2` 且双源一致），与仓库既有「硬编码计数即误报」的修法同源。
8. **引用写法须类别限定**：校园包内 `情感:M22` 与官方 `事件:M22` 重号，references 里写裸
   `M22` 被 check15 ① 判「不在源包 modules[] 在列」→ 改 `情感:M22`（与源包声明一致）。

## 六、边界与不宣称

- 广度证明 = **两两全集 + 定种子抽样**，不是 2^107 全枚举；抽样覆盖三类交叉面（层位 / 事件 / 依赖），
  不宣称「已证明所有高阶组合」。
- 组合**不改源包**：借阅只读、模块不改号、资产不复制；组合不产生新内容资产。
- 证书只证明**结构合法与可复算**，不证明组合出的内容质量。
