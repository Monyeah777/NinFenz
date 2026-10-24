---
id: AUD-0014
title: 决策模型驱动「扩展 / 深化 / 创新」——能力缺口候选池 + 真模型选 innovatie 项落地（决策面接入互操作导出）
date: 2026-09-22
scope: 作者指令「利用决策模型来进行 NF 项目内目前已有的功能的扩展深化创新等」——把能力缺口机械派生为第三类候选源，让真模型在 extend/deepen/innovate 三族里选择，并落笔其选定项；本件只记录可复现事实
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/workloop.py:3ee94f2c11939abba5507741c6b9b4dae8e8cab77c3bda38419678e31e097056
  - desktop/src/core/interop_export.py:cfabc28f442a8d43526d92fca8cb17ea74473f51de8f69e918042eb5062b24f8
  - scripts/nf.py:14c48492f9c92cbf2a79b47ff97a035bfc7e4e744fd88badeeab583e04331918
  - scripts/check_interop_schemas.py:f9c1add0ee80fb23a3913e32482027e9a4049c5ce70cb35b2b1be4afa075d091
  - docs/interop.md:f884a0533ed89aae8c83a2a44da491afb334c083dc05051158ac3a91e88e4f5c
  - desktop/tests/test_interop_export.py:2308d682b075fef25982c6577c67d41714980c94db1f4f538fee26ec7239a847
  - desktop/tests/test_decision_layer.py:5a8b93b3af9bb732e09954b8e7d6ac8511a97003ccb83f5679e8f23375dacb61

---
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

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 七件（回路模块 / 导出模块 / CLI / 外部校验工具 / 对外文档 / 两份单测）。
> **口径**：subjects **不含派生物**——`results/interop/*.json` 每次重生成都会变（本次 AUD-0014 初稿
> 曾误把它列作被审对象并因此假失效，已按既有口径移除）；派生物由 check33 入仓面逐字节断言自证。

## 一、把「扩展/深化/创新」变成**可核验的候选**（不靠想象）

新增第三种待办源 `capability-gaps`（`core/workloop.py`），三族候选**全部机械派生**：

| 族 | 判据（机械派生） | 本波实测候选 |
|---|---|---|
| **extend** | 已有只读面未接 MCP（CLI 只读治理面 24 个 vs MCP 工具 10 个） | `CAP-EXTEND-MCP-READONLY`（19 个未接） |
| **deepen** | 同一事实两处声明却无一致性判据 | `CAP-DEEPEN-DECL-CONSISTENCY`（实测抓到：CLI `--kind` 缺 `a2a`、`c2pa`） |
| **innovate** | 两个既有面之间尚未接线 | `CAP-INNOVATE-DECISION-INTEROP`（决策层 ⇄ 互操作导出未接） |

**关键设计**：候选**随状态自动撤单**——缺口被补掉，候选即消失（不是静态待办清单）。
本波实测：修掉 CLI 漏同步后 deepen 候选消失；决策面接好后 innovate 候选消失 → 池中只剩 extend 一条。

## 二、真模型的选择（Laya multilingual · 本地 HTTP）

`nf workloop --adapter systemone-http --source capability-gaps --top 3`（真模型跑在本地 8791）：

| 项 | 值 |
|---|---|
| 选定 | **`CAP-INNOVATE-DECISION-INTEROP`**（p=**0.5769**） |
| 风险 | 期望 **2.2065**（probs [0.006, 0.781, 0.213] → 押「中」） |
| gate_safe | **0.4464** —— 它正确识别出这项会碰回执锚定面（低） |

## 三、落笔（worker）与结果

1. **新增导出面 `decisions`（决策面）**：纯派生自 `protocol/decision_layer.json` + `results/audit/*.md`
   frontmatter → 外部工具链可读到「原语 / 应答契约 / 适配器（含是否在门禁路径、是否校准）/
   候选模型（含拉取状态与本地证据）/ 边界 / workloop 四条不可协商 / **公开裁决索引**（13 条）」；
   并**显式声明逐次工单不入公开面**（`STRATEGY §四` 计划内部消化，门禁判该声明在位）。
   互操作面 **11 → 12**；`results/interop/decisions.json` 入仓，check33 逐字节断言一致。
2. **顺带修掉侦察抓到的真 bug**：CLI `--kind` 手工列表**第二次**漏同步（缺 `a2a`、`c2pa`）→
   改为**派生自 `interop_export.KINDS`**（构造上消除该类错误）；并新增单测
   **逐个声明面实跑**（此前漏同步时 `--kind c2pa` 会直接报错）。
3. **外部校验口径登记**：`decisions` 面在 `check_interop_schemas` 记 `no-schema` 并写明理由
   （NF 自有形状，判据落本仓 check33）→ 外部核验面 **13 → 14**，全绿。

## 四、门禁与验收

| 判据 | 结果 |
|---|---|
| `bash verify.sh` | **PASS=61 · WARN=0 · FAIL=0**（check1-37 不变；决策面并入既有 check33 入仓面断言） |
| `python -m unittest discover -s desktop/tests -q` | **983 例全绿**（+2：CLI 派生逐面实跑 / 决策面内部边界） |
| `nf conformance` | **27/27 conformant** |
| `scripts/check_interop_schemas.py --fetch` | **14 面**：官方 schema 通过 5 + 上游源码字面量通过 1 + `no-schema` 7 + `unavailable` 1 |
| 回路收口 | `.rivet/private_archive/work_orders/WO-140e9166e433.close.json`（landed · PASS=61 · 27/27） |
| 候选池自收敛 | capability-gaps 由 3 → **1**（deepen/innovate 因缺口已补而撤单） |

## 五、遗留与不宣称

1. **extend 未做**：`CAP-EXTEND-MCP-READONLY`（19 个只读治理面未接 MCP）仍在池中——真模型本轮选了 innovate，
   按"模型定选"的约定不擅自扩大；下一轮可让模型在 extend 上选（或缩小到最有价值的 3–5 个面）。
2. **MCP 工具面仍只读**：任何新增工具必须保持只读（无写路径），该约束由 check33 与 `protocol/mcp_package.json` 共同守着。
3. **不做质量宣称**：决策面只证明"决策能力与公开裁决可被外部读"，不宣称模型决策质量；
   模型的置信度与概率已随面导出，但校准性未在自有留出集复核。
4. **候选池判据是"机械派生"而非"创意生成"**：三族候选只反映**可核验缺口**；真正的创新仍由 worker 落笔，
   模型负责挑与排序（这也是本轮回路的固定分工）。
