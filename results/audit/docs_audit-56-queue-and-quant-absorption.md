---
id: AUD-0008
title: 六项裁决一次收口（各取最优解）+ 六个量化项目吸收与域包深化（第 4/5 件资产、3 个新概念）
date: 2026-09-20
scope: ① 执行作者裁决队列六项（闭包跨域形态 / 证据强度入判据 / 多语言入口 / 外链巡检 / 跨包裸号白名单 / 货架嵌套），每项给出最优解与理由；② 对六个量化开源项目做机制借鉴筛选与净吸收，用于量化金融域包深化
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/concept_graph.py:cc629a762576347a6065da4be34ff6c6902ec4ee7299663119abbc153bd50211
  - verify.sh:d724f3a0a8ccde43ded229085dc5e3d985ec9d5f069ee298d815000743fad542
  - README.en.md:048547b43c0024cc856ce1c396803bc00b7a6a167cd7956a0ddea4e8641c04f0
  - scripts/check_external_links.py:1cbee65ba19a83fbcdf333e35b8d99c2e45f3b400f3a025860357baf7a806b02
  - community/量化金融域包/assets/DATA_CONTRACT.md:3815cd420ce535b571149a1ca0725b2d5c1757660e83d0edd8ed1d5c14ed2af1
  - community/量化金融域包/assets/STRATEGY_SPECS.md:9174638b5caf2d5d8586b80d07ed9aeca5d221e16f01ec19ce0e4c0f50859e65
  - community/量化金融域包/assets/QUANT_GRAPH.md:331d63943effe51462440c41832202df3b8e6bb2553734472947ac77927e094c
  - .github/workflows/external-links.yml:e1a67faaeac1712bb77c9c36bf7133e68b6e705e8c4e296b40024825939f261b

---
> 重审（2026-10-30）：refreeze.sh（统一冻结入口）

> 重审（2026-10-28）：默认并行度 10→14

> 重审（2026-10-28）：tests-only 默认并行度 8→10（实测 285 s 拐点）

> 重审（2026-10-28）：D 第一刀：paths realpath 去重 + text_hygiene 二进制读取走 scan_memo + --pr 档

> 重审（2026-10-28）：tests-only 默认 8 片 + PermissionError 退避重试

> 重审（2026-10-27）：verify.sh: checks 档缓存 put/get 一致（mode=checks）

> 重审（2026-10-27）：checks-only 独立档位缓存（verify_cache mode=checks）

> 重审（2026-10-25）：Scorecard 收口：最新 main 合并、CODEOWNERS ASCII 化、SAST/Fuzzing、最小权限、依赖漏洞与容器 digest 统一重绑

> 重审（2026-10-25）：REUSE 3.3 合规（MIT-NOTICE + 徽章 + CI 作业）

> 重审（2026-10-25）：英日 README 双许可表述

> 重审（2026-10-24）：CI 并发锁、Gitee 诊断与 ADR-0008 改变 verify/脚本字节；重审理由：相应测试与冻结链已同步

> 重审（2026-10-23）：合并远端 README badge 后重绑审计摘要：仅文档变化

> 重审（2026-10-23）：OTLP ID 判据与合作一致性稳定性修正：traceId/spanId 定长 hex，缺失真源诊断去 OS errno

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

> 重审（2026-10-22）：CI 三刀合入后重绑（诊断目录绝对化/fetch-tags/wasm skip）

> 重审（2026-10-22）：H1：nf verify 仓库信任门 + README.en/ja 安全声明（重冻）

> 重审（2026-10-22）：测试执行器、进程原子与 Windows shell 解析修复后重算代码度量基线与角色投影；既有审计结论不变

> 重审（2026-10-21）：locales html 1

> 重审（2026-10-21）：readme head 1

> 重审（2026-10-21）：1.0.5 收口 1

> 重审（2026-10-21）：README 官方源声明与演示帧重建

> 重审（2026-10-20）：canonical notice 1

> 重审（2026-10-20）：0.x renumber 1

> 重审（2026-10-20）：readme/tag 治理 1

> 重审（2026-10-19）：check39 挂载五分钟入口判据（docs/quickstart.md ↔ scripts/quickstart_check.sh），verify.sh 结构性新增子判据

> 重审（2026-10-19）：verify.sh 恢复并补 _NF_BG_TESTS_PID 声明

> 重审（2026-10-19）：verify.sh 补 _NF_BG_TESTS_PID 声明（set -u 下 pre-push 钩子炸点）

> 重审（2026-10-19）：EOL 归一 + 译件重签

> 重审（2026-10-19）：verify.sh 诊断目录/临时变量修复后重绑

> 重审（2026-10-19）：诊断目录兜底：TMPDIR/仓库内 .rivet/tmp

> 重审（2026-10-19）：full 重叠回退（实测更慢且内容面互扰）

> 重审（2026-10-19）：full 档也重叠 + 单分片内层线程按核数

> 重审（2026-10-18）：动态队列 + 常驻集收敛 + 分片上限 16

> 重审（2026-10-18）：重叠范围收窄到 quick

> 重审（2026-10-18）：quick 档测试与静态 check 重叠执行

> 重审（2026-10-18）：asset_read 第五轮：按 TDQS 50-100 词上限压到 100，保留 5 段与输出/参数/限制

> 重审（2026-10-18）：P2：分片数按核数自适应

> 重审（2026-10-18）：P3：分层档位 + 判定缓存 + 受影响测试选择

> 重审（2026-10-18）：P2：check12 分片并行（verify_tests 执行器 + 权重基线）

> 重审（2026-10-17）：步骤5：在场/关键词组收敛到 _decl_check（等价性 15 例逐字节一致）

> 重审（2026-10-17）：步骤4：新增 check41/42（构建隔离 + 不可伪造 provenance）与对应判据模块

> 重审（2026-10-17）：拆聚合门：check32/33/35/36 失败逐条透出（只动 bash 呈现层）

> 重审（2026-10-17）：门禁提速收口：check39 剪枝定为 target/obj（刻意不剪 bin——实测零收益且可能承载入库脚本）；check39 7.15s→4.06s，差分 6/6

> 重审（2026-10-17）：门禁提速：check39 遍历再剪构建产物目录（target/bin/obj）——engine/rust/target 一处 22454 目录（gitignore），只含产物不含源；实测目录 24712→1949、遍历 4.36s→0.28s（15.5×），判定逐项等价（禁名命中与 desktop/src/ui 在场性一致），差分 6/6 通过；nf verify 冷跑 17.8s→16.3s

> 重审（2026-10-16）：门禁提速（收口）：修 check30 批量化引入的两处路径归一缺陷（git quotepath 非ASCII转义 + Windows glob 反斜杠）——被 test_check30_bump 当场抓出；另打破 gate_engine↔subcheck_cache 模块环（依赖倒置，只回稳定字段字典），并补两处静默兜底理由

> 重审（2026-10-16）：门禁提速：check30 的 127 次 git diff 合并为一次全量调用后按块取（实测 2.016s→0.196s，42 件逐字节等价）；连同 check39 遍历优化，22 条已迁入合计 30.6s→19.1s、nf verify 冷跑 28.7s→17.8s

> 重审（2026-10-16）：门禁提速：check39 遍历由 os.walk 换单遍 os.scandir（同层剪枝 + follow_symlinks=False，省掉每条目一次 lstat 与整棵被排除子树）；实测 10.34s→6.70s，结果集逐字段一致（24712 目录/7221 py），差分 6/6 通过

> 重审（2026-10-16）：L-D 并行结论：默认保持串行（并行结论不稳定：共享守护单例 + 派生面可写），verify_parallel.py 保留为开发侧工具；verify.sh 字节已变，重绑 digest

> 重审（2026-10-16）：L-D 并行收尾：check12 默认按核数并行（上限 16）+ 守护卫生；相关派生面重冻后重绑

> 重审（2026-10-16）：L-D 并行接线：check12 改走 scripts/verify_parallel.py（模块级并行，8 路实测 1255→409 s）+ 守护卫生（只收本次拉起的）；verify.sh 字节已变，重绑 digest


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 本波承重件（判据实现 / 门禁 / 双语入口 / 巡检工具 / 三件资产）；任一件再改，本件结论即失效须重审。

## 一、六项裁决：逐项最优解与理由

| # | 挂账 | **选定解** | 理由（内部口径） |
|---|---|---|---|
| ① | 模块级闭包跨域形态（三选一） | **a) 保持现状 + 落规则**：闭包是**机制面**能力（`core/concept_graph.py` + 只读求值器 `--asset` + check32 子扫描），**内容面**随域包；域包可自带模块级闭包但**不跨包共享、不上提通用模块** | 当前**无该消费者**——第二域包（量化金融）已由通用面满足（`--asset` 直接可用）；上提通用模块 = 空转机制 + 跨包契约耦合；b) 引入跨包 references 会改 AI系统域包契约（参数化图键）而无收益。已写入 `02 §8`（概念图与闭包求值形态规则） |
| ② | 证据强度是否入判据 | **入，但只判可判定部分**：门禁要求 ① 图声明 `provenance_strength ∈ {external, domain-logic, inferred}`；② `external` 须有非推断图例键；③ 节点 `provenance` 的**每个键都须在图例在册** | 「证据是否真的充分」不可判定（硬判=造假判据）；可判的是**声明在场 + 与图例自洽**。顺带修掉真缺口：此前只查 provenance 非空、**不查键是否在图例**（图例漂移会静默）。落点在既有 check32 子扫描内 |
| ③ | 多语言入口面 | **开「最小英文入口 + 一致性判据」**：新增 `README.en.md`（机读事实：协议件 / 三条装载路径 / 质量凭证 / 许可），`llms.txt` 加锚点；**check34 增双语机读锚点一致性断言**（期望值取自 `quality_baseline`，不写字面量） | 外部实证：某清单双语面无判据 → 中文面腐烂到英文面 ~54%。NF 的解法 = 开面的同时**带判据**；范围控制在「机读事实 + 装载路径」，不做全量翻译（避免双源维护面爆炸） |
| ④ | 外链巡检是否开 | **开，但只作「非门禁独立任务」**：`scripts/check_external_links.py`（默认只解析、`--fetch` 才联网、`--write` 落 `results/`；**拒绝写入 `protocol/`**） | NF 门禁须静态可复现（同输入同输出）→ 外链可达性不进 verify 基线；同时补上「对外链接无巡检」的真空，且不脆化门禁 |
| ⑤ | 跨包裸号引用白名单化 | **不立（挂账关闭）**：`check15 ①` 已断言 references 的 module_id 须在源包在列，`check14 ⑤c①` 又保证同一裸号**全库唯一** → 裸号引用无歧义，白名单属重复机制 | 已写入 `02 §8`（跨包裸号引用无需额外白名单条）——机制不重复立，是本仓「零冗余」的直接应用 |
| ⑥ | 资产货架嵌套分组 | **保持单层不变量 + 给规范替代与触发条件**：分组用「键表 + 一包多文件 + 资产内条目键」；**触发条件** = 单包 > 30 件内容资产或出现明确子域分组消费方，届时另提裁决（属表达力扩展，须同时改密度 / 投影 / 基线三面） | 今天无嵌套需求（三货架子目录均为 0）；单层不变量已在 check23 硬门，规范替代写进 `05_资产库 README`，触发条件把「什么时候该重新讨论」写明 |

## 二、六仓勘验与净吸收（机制借鉴 → 逐条实证）

| 仓 | 许可 | 形态 | 判定 | 落点 |
|---|---|---|---|---|
| `QUANTAXIS`（573 文件） | **MIT** | 中国市场量化框架：`QAData/QAFetch/QADataBridge`（数据桥）/ `QAEngine` / `QAFactor` / `QAIndicator` / `QAMarket` / `QAPubSub`（发布订阅）/ `QASchedule`（调度）/ `QAStrategy` / `QIFI`（**统一交易接口对象**）/ `QARSBridge` | **部分吸收（机制观察）** | ① 「统一交易接口/账户对象」→ 新资产 `DATA_CONTRACT` §5（账户 / 委托 / 成交对象）+ 新概念 `Q30 交易对象与账户口径`；② 调度与发布订阅 → **已具备**（NF M50 调度 + 事件总线） |
| `zvt`（580 文件） | **MIT** | 数据—因子—记录器分层：`src/zvt/{domain, recorders, factors, contract, trader, sched, tag, informer, ml, api}` | **部分吸收（机制观察）** | 「领域对象 + 记录器 + 合约元数据」→ `DATA_CONTRACT` §3（合约与标的元数据）+ §6（数据源抽象与标准化）+ 新概念 `Q28` |
| `QuantDinger`（961 文件） | Apache-2.0 | 「AI 交易操作系统」：`backend_api_python` + **`mcp_server`** + `docs/{AGENT_QUICKSTART, MCP_SETUP, openapi.yaml, agent-openapi.json}` | **已具备（不重做）** | 给 agent 的接入面（MCP + OpenAPI + agent 快速开始）↔ NF `nf serve`（MCP）+ `llms.txt` + `docs/agent/AGENT_START.md` + `protocol/endpoint_contract.json`；其「想法→策略→回测→模拟→实盘→监控」全链 ↔ 本域图 Q09–Q20 已覆盖 |
| `OpenBB`（2191 文件） | **AGPL-3.0** | 开放数据平台：`openbb_platform/{core, extensions, providers}`（provider 抽象 + 核心 + 扩展插件） | **仅机制观察（不传导结构）** | 「provider 抽象 + 标准字段模型」是多源接入的公认机制 → 新概念 `Q28 数据源抽象与标准化` 的**存在性**观察；但 AGPL-3.0 属强 copyleft → **不入资产图例、不引用其结构**，概念与边仍标 `domain-logic` |
| `QuantEcon.py`（270 文件） | **MIT** | 经济学数值库：`quantecon/{game_theory, markov, optimize, random, util}`（Markov DP / LQ / ARMA / 谱分析…）+ 教程 | **部分吸收（概念面）** | 数值方法与动态规划是域内独立能力面 → 新概念 `Q29 数值方法与动态规划`（**独立成支，不并入组合优化 prereqs**——弱工具依赖不立边） |
| `quant-trading`（177 文件） | Apache-2.0 | 策略示例集：每策略一脚本 + `data/` + 主题项目（Monte Carlo / Oil Money / Ore Money / Smart Farmers） | **部分吸收（内容形态）** | 「策略示例集」形态 → 新资产 `STRATEGY_SPECS`（**自撰规格**：7 例 × 适用概念 / 必要前置 / 口径清单；只给规格不给代码、不给收益承诺） |

**纪律声明**：以上判定不构成立项理由（本波依据 = 作者指示 + 域包深化需求）；外部文本零复制；AGPL 仓不入图例；入图例与否由许可与证据类型决定，逐条写明。

## 三、本波交付（量化域包深化 + 机制三项）

| 类 | 件 | 要点 |
|---|---|---|
| 资产 | `DATA_CONTRACT.md`（第 3 件） | 五条契约纪律 + 行情 11 字段 + 标的合约 7 字段 + 基本面 / 另类 5 字段 + 账户交易对象 5 组 + 数据源抽象 4 项 + 三个口径陷阱（复权 / 停牌 / 退市） |
| 资产 | `STRATEGY_SPECS.md`（第 4 件） | 7 个策略族规格（趋势 / 均值回归 / 配对 / 多因子 / 事件 / 期权 / 日内），每例给「适用概念 + 必要前置 + 口径清单」，并强制两条偏差口径 |
| 概念图 | `QUANT_GRAPH` 30 概念（+3） | `Q28` 数据源抽象与标准化（data 支）/ `Q29` 数值方法与动态规划、`Q30` 交易对象与账户口径（research 支）；新增 `provenance_strength: domain-logic`；边只立「必须」依赖（弱工具依赖不立边） |
| 包登记 | `protocol.yaml` assets 2 → 4 + registry 同步 | check14 ⑦ 元素级自证 |
| 机制 | `concept_graph.py` 证据面判据 | 声明词表 + 图例自洽 + 节点 provenance 键在册（两张图同步加声明：AI系统 = `external`，量化金融 = `domain-logic`） |
| 机制 | 双语入口 + 一致性判据 | `README.en.md` + `llms.txt` 锚点 + check34 双语机读锚点断言（期望值取自 `quality_baseline`） |
| 机制 | 外链巡检工具（非门禁） | `scripts/check_external_links.py`（默认只解析；`--fetch` 联网；拒绝写 `protocol/`） |
| 文档 | `02 §8` 两条新规则、`05_资产库 README` 规范替代与触发条件 | 挂账 ①⑤⑥ 的规则化落点 |

## 四、门禁与验收

| 判据 | 结果 |
|---|---|
| `bash verify.sh` | PASS=61 · WARN=0 · FAIL=0（**不新增 check 序号、不改 Schema**：六项与吸收项全部落在既有 check14/23/32/34 内） |
| `python -m unittest discover -s desktop/tests -q` | 全绿（本波新增 24 例：双语入口 4 + 外链工具 6 + 量化包 14 更新；概念图门禁测试计数更新为 2 图 77 节点） |
| `python -m ruff check .` · `python -m compileall -q desktop/src scripts` | 零违规 |
| 资产面 | `nf asset verify` 闭合（台账 3 · 托管资产 7 · 孤儿头 0）；量化包 assets 2 → 4 双源一致 |
| 事件 / 管线 / 市场 | `nf events` 43 零缺口；`nf pipeline dryrun --all` 10 条零 hard；`nf market --list` 列出量化金融域包 |
| 跨域求值 | `--asset …/QUANT_GRAPH.md --target Q17` 仍可复现；`frontier(--branch research)` 现含 Q29 |

## 五、遗留与不宣称

1. `Q29/Q30/Q28` 的边仍为 `domain-logic`（无实现类来源证据）——量化图整体维持 `domain-logic` 强度声明，不因本次吸收而升格。
2. 外链巡检**未接入任何自动化**（本地/定时任务自行调用）；如需定时跑，属运维面，不在本仓门禁内。
3. 英文入口只覆盖机读事实与装载路径，**不是**中文文档的全量翻译（避免双源维护面爆炸）——`README.md` 仍是权威版本。
4. 六个项目的**代码与数据零吸收**（只取机制观察与形态）；AGPL 仓连结构也不传导。

## 六、跟进（同日 · 三条挂账一并执行）

| 挂账 | 处置 | 实测 |
|---|---|---|
| ① 量化图证据强度升格 | **取回权威来源当外部锚**：Crossref REST API 取回 **10 条**经典工作元数据（Markowitz 1952 / Sharpe 1964·1966 / Black-Scholes 1973 / Fama-French 1993 / Jegadeesh-Titman 1993 / Kyle 1985 / Almgren-Chriss 2001 / Harvey-Liu-Zhu 2015 / Cont 2001，含 DOI 与年份），arXiv 摘要页取回 **3 条**（Deep Learning for Portfolio Optimization 2020-05-27 / Momentum Transformer 2021-12-16 / Deep Learning for Limit Order Books 2016-01-08）；据此给 **14/30 节点**挂外部来源键，资产新增 §6 外部证据表与取回失败清单 | 强度声明 `domain-logic` → **`mixed`**；判据同步升级为**四级阶梯 + 覆盖自洽**（`external` 须全覆盖 / `mixed` 须部分覆盖 / `domain-logic` 须零外部键）。AI系统域包实测 **external（47/47 全覆盖）**，量化金融 **mixed（14/30）**——都是机检结论，不是自述 |
| ② 外链巡检接自动化 | 新增工作流 `.github/workflows/external-links.yml`：`workflow_dispatch` + **每周一 cron**；权限最小化（`contents: read`）；先跑离线 scan（恒绿）再跑 `--fetch`（失败即 job 红）；报告上传为 artifact（**不写回仓库**） | 网络抖动可手动重跑；门禁基线不受影响（外链巡检始终在 verify 之外）。**首跑即抓出工具自身三处缺陷并当场修正**：① 行内代码里的 URL 带尾随反引号未剥离；② 骨架示例 URL（含 `{路径}` 占位符）被当死链；③ 非 ASCII 路径未百分号编码 → urllib `UnicodeEncodeError`。修正后复测 **20/20 取样链接全部可达、0 失败**，并补 2 例单测（占位符跳过 / 尾引号剥离） |
| ③ 英文入口扩到全量 | `README.en.md` 重写为**逐节镜像**（5 个 H2 与 `README.md` 一一对应：AI/Agent 入口 / 快速开始 / 能力与资产 / 协议链导航 / 版本块），并顺带**校正中文 README 的能力块陈旧数字**（44 模块 · 8 管线 · 5 社区包 · 55 档/165 键 · 馆藏 2 件 → 48 模块 · 10 管线 · 7 社区包 · 60 档/326 键 · 概念图 2 · 馆藏 3 件）；check34 增两条断言：**H2 章节数一致** + **中文入口引用的 ASCII 名 .md 件在英文入口同样出现** | 单测同步加 2 例；「双语面腐烂」类事故因此变成门禁可拦 |

**取回失败与修正如实记录**：arXiv API 端点返回 406（改走摘要页）· Merton 1973 的 DOI 失效（1 条未取回）· MIT OCW `/pages/calendar/` 重定向环、`/pages/lecture-notes/` 讲座清单为前端渲染、QuantEcon 站点返回 JS 桩 → **课程体系序未取回**，故量化图仍无 orderings（不造序）· 一次 arXiv ID 猜测取回无关论文（1904.08900 = CornerNet-Lite）**已弃用不入图例**。
