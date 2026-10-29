---
id: AUD-0021
title: 组合包产物化（4 个组合包落成可装载协议包）+ 广度证明扩到五元/六元（参与面 111 包）+ 声明证书 13 → 17
date: 2026-09-24
scope: 作者目标「任意几个域包可自由组合、包内组件可自由组合、理论广度无限、深度质量保证、产出组合可机验」的收口面——本件记录：组合包产物化机制与 4 个产物包、参与面包含组合包的广度证明（含五元/六元）、证书台账刷新，以及台账去重口径
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/pack_combo.py:5fe16225b1586d5ebf4c8faf1901f0225297dd9af7c2ba0778e86707d24ed525
  - scripts/nf.py:331dfa1333f0e685bb16f916b31d14a077df435fffdc3d903aef35a33561711a
  - docs/combos.md:4d25fe6d366687213df7090badd52b815bdf07f774df856e598d7cf8a1d130de

---
> 重审（2026-10-29）：four-state check registry on latest main

> 重审（2026-10-28）：nf verify 判据并行（heredoc→子进程，3.5×）

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


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 3 件（组合引擎、CLI、公开文档）；**不含派生物**——4 个组合包目录由
> `nf combine materialize` 可复算，`protocol/combo_certificates.json` 由 `certify` 可复算，
> 按口径不入审计绑定。

## 一、内部差距（开工依据）

1. 组合引擎能把任意组合**判合法**，但判完就没了：结果只活在证书里，**装不出来**——
   没人能拿一个「检索栈组合」当包去装载（缺协议声明、缺管线、缺层栈、缺产出面）。
2. 广度证明的参与面是**域包集合**，组合包自身（带 `references` 的借阅型包）从未进入抽样：
   「组合包能不能当组合成员」在仓库里没有证据。
3. 广度只到四元；五元/六元是否存在交叉面退化（层位堆叠、事件闭包、依赖闭合）没有抽样证据。

## 二、组合包产物化（从「判合法」到「装得起来」）

`nf combine materialize --packs <包名,…> [--id <组合包名>] [--category …] [--write]`：

| 产物面 | 内容 | 判据 |
|---|---|---|
| `protocol.yaml` | `module_id_range: []`（**0 自有模块**）+ `references` 逐条 `asset_readonly: true` + `mount_layers` 写 `available`（`default` 留空） | check14 六项 + check15 references 闭合 |
| `pipelines/Pxxx_*装配流管线.md` | 派生自 P00 骨架；`allowed_modules` = 官方核心 ∪ 借阅模块 | 管线 dry-run 零 hard |
| `assets/` + `outputs/`（8 面） | 借阅索引 / 系统卡 / 层栈图（Vega-Lite）/ 装载序图（Mermaid）/ 依赖图（GraphML）/ 三件 schema / **T4 组合证书** `COMBO_CERT.json` | 全面 ≥T2；T4 由 check32 `combos` 复算 |
| 登记三要件 | 02 §8 段（`模块（0）`）+ `verify.sh` DOMAIN 名单 + `registry protocols[]` | check14 ⑦ / check32 名录 ↔ 登记一致 |

**已落 4 包**：`组合包-检索栈`（P109，借阅 6 模块）· `组合包-数据管线`（P108，8）·
`组合包-受监管行业`（P110，8）· `组合包-轻混与保险`（P111，9）。四包**机验产出占比 1.0000**。

**设计要点（本波定下）**：① 层栈写 `available` 而非 `default`——组合包与源包同层时
`default` 会撞车，`available` 表示「可装载但默认不挂」，把选择权交回装载方；
② 组合包**不改源包**（模块不改号、资产不复制），借阅永远只读；
③ 组合包不新增内容资产——它的产出面是**结构合法性**，不是内容质量背书。

## 三、广度证明：参与面 111 包 + 五六元抽样

`breadth` 的参与面取 `community/` 下**全部已登记协议包**（100 域包 + 4 组合包 + 既有社区包 = **111**），
组合包按 `references` 摊平后跑同一套不变量。实测（seed=20260923）：

| 规模 | 数量 | 合法 |
|---|---|---|
| 两两（全集） | 6105 | **6105** |
| 三元 | 400 | **400** |
| 四元 | 200 | **200** |
| 五元（本波新增） | 120 | **120** |
| 六元（本波新增） | 60 | **60** |
| 极限（全 111 包同装） | 1 | **合法 · 235 模块 · 0 悬挂 · 0 未桥** |

check32 `combos` 子扫描的不成立判据同步扩到五元/六元（任一规模出现非法即 FAIL）。

## 四、证书台账（13 → 17）与去重口径

新增 4 条**组合包产物化证书**：输入 = 该组合包 `references` 的源包集合 + 被借模块集合
（如 `组合包-轻混与保险` = 4 源包 / 9 借入模块，重算后 27 模块、合法）。
极限证书刷新为 **111 包**（235 模块），被取代的 107 包旧快照**清出台账**：
去重键 = **组合输入本身**（`packs + extra_modules`），不是摘要——引擎升级会改摘要，
按摘要去重会留下历史快照（上一波实测 26 条里 13 条过期）。
台账当前 **17 条**，`nf combine verify` 逐条复算 **0 失败**。

## 五、边界（不宣称）

- 广度是**两两全集 + 定种子二至六元抽样**，不是 2^111 全枚举；不变量在抽样上成立
  不等于逐条枚举，但已覆盖层位堆叠 / 事件闭包 / 依赖闭合 / 资产借阅四类交叉面。
- 组合证书只证明**结构合法与可复算**，不证明组合出的内容质量；内容质量仍由各包口径与 T4 面承担。
- 产物化组合包的「质量」= 可装载 + 可机验，不宣称其为**推荐装配**（推荐与否不在判据内）。
