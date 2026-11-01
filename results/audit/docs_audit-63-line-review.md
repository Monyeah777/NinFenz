---
id: AUD-0015
title: 决策模型逐行审查缺口 —— 93 行候选全判 + 三类修复（收割器根因 / 数据契约登记 / 静默吞错计数）
date: 2026-09-22
scope: 作者指令「让决策模型逐行检验缺口，找出所有漏洞，然后你来一并修理」——机械预筛行级候选 → 真模型逐行判（缺口/严重度）→ 确定性证据复核 → 按类一并修理；本件如实区分「已修」「挂账（内容面）」与「不可由代码修」三类
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/gap_review.py:7d1d600926e13b9936f2a7d30e8a8ca95e4bb3b2a73308f88cfb89b563055953
  - desktop/src/core/payload_harvest.py:514c493d341863b245b7dddb0bde8ee87ca969fe4407c9f2834a726bb92d1a76
  - protocol/data_contracts.json:6ca6174c77d41ad354b90e637c404bedfbe5d8ad0ce6400bb26f2ac7e5f19eb0
  - protocol/assertions.json:5a0bb383eabf678a9f660ae6d771f0be51cce5397a40a73f0d0d93457e4f1cba
  - desktop/src/core/interop_export.py:ff00f77a4236929cb64dfd120f9a60952ba8013843681cc0586a96f0c155564c
  - desktop/src/core/text_hygiene.py:ff5fb24eafb99044ad1452f26d5cf3be6b89a24d77a5be5e4bcf56189a8ea956
  - desktop/src/core/workloop.py:3ee94f2c11939abba5507741c6b9b4dae8e8cab77c3bda38419678e31e097056
  - scripts/serve_decision_model.py:bbb36dff0e3816c2253150b7de6ab619877c3c78269a644c4c966083df15afee
  - scripts/nf.py:6a2a931b373487d2aac503b295a2db3cfa579eb46ae8856b41f5d3401da7ca37
---
> 重审（2026-10-30）：2026-10-30: 1.1.2 版本面与发布事实同步；README 与机器事实更新，重审对象摘要变更。

> 重审（2026-10-30）：refreeze.sh（统一冻结入口）

> 重审（2026-10-28）：nf verify 判据并行（heredoc→子进程，3.5×）

> 重审（2026-10-28）：D 第一刀：paths realpath 去重 + text_hygiene 二进制读取走 scan_memo + --pr 档

> 重审（2026-10-26）：rebase 到 fa3fdd58 后重冻（atoms/nf/perf_budget）

> 重审（2026-10-25）：Scorecard 收口：最新 main 合并、CODEOWNERS ASCII 化、SAST/Fuzzing、最小权限、依赖漏洞与容器 digest 统一重绑

> 重审（2026-10-25）：1.1.0 版本面 + CLA workflow + 定价

> 重审（2026-10-25）：分层双许可（1.1.0 起）

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

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 九件（审查模块 / 收割器 / 契约登记 / 断言表 / 四个被修文件 / CLI）；**不含派生物**（口径同前）。

## 一、逐行审查是怎么做的（双轨，缺一不进修复清单）

新增 `core/gap_review.py` + `nf review`：

```
候选行（机械预筛，行级可定位） → 真模型逐行判（noul 是否构成缺口 + score 严重度）
    → 确定性证据复核（该行能否由规则证实） → fixable / suspected / not-a-gap
```

**为什么必须双轨**：Laya 系是未校准分类器（模型卡自述 ECE 0.213 偏自信）——它只能**排序与提示**，
不能单独判决"这是漏洞"。故进修复清单的每一行都必须另有确定性证据；模型说"是"但无证据的，
一律记 `suspected` 挂账，不修。

## 二、真模型逐行判定结果（93 行，实测）

| 类 | 行数 | 模型判定（noul p 区间） | 严重度（score 期望） | 证据复核 |
|---|---|---|---|---|
| `missing-quality-rule`（规范件未登记数据契约） | 15 | 0.84–0.96 | 2.27–2.35 | 15/15 可证 |
| `silent-skip`（except → pass/continue 无说明） | 50 | 0.94–0.97 | 2.24–2.33 | 50/50 可证 |
| `unharvestable-payload`（正文有类型信息但收不到） | 28 | 0.91–0.96 | 2.25–2.3 | 28/28 可证 |
| 合计 | **93** | — | — | 93/93 |

报告存档：`.rivet/private_archive/gap_review/2026-09-22.json`（逐行含 p、severity、证据文本）。

## 三、一并修理（按类，不逐条打补丁）

| 类 | 修法 | 结果 |
|---|---|---|
| ① `unharvestable-payload`（28 行） | **修根因**：`payload_harvest.harvest_doc` 增加 `produce:` 事件标记写法（旧规则只认 `event:`/`name:`/`publish:`）——28 行一处代码修复 | 收割立即多收窄 **13 个字段**；事件载荷类型覆盖 **45.6% → 52.7%**；`type_backlog` **99 → 86**；再按"是否真有类型证据"细分后：真缺口 **28 → 7**，另 19 行归为 `payload-no-evidence`（只有字段名、无任何类型证据） |
| ② `missing-quality-rule`（15 行） | 补数据契约登记：12 件指向真实 checkN（driver/endpoint/rfc → `check36`；asset_line_baseline → `check23`；5 份 schema → `check28`；external_events → `check16`；transform_log/knowledge_usage → `check37`）；3 件（vocabularies/normative/data_contracts）**无对应 checkN** → 改为新增 3 条断言（`assertion:vocabularies-face` / `normative-face` / `data-contracts-face`，json_value schema 自证）并以 `assertion:<id>` 登记 | 数据契约登记 **11 → 26**；`nf model contracts` 全绿（quality_rule 全部解析到真实 check/assertion）；该类候选 **15 → 0** |
| ③ `silent-skip`（50 行） | 先给**本波新写文件**的 5 处补真实理由（内联注释：尽力而为跳过 / Ctrl+C 正常终止 / 软依赖缺面）；判据同步接受"内联在 except 行的说明" | 该类 **50 → 45**；**其余 45 处跨 20 个既有模块**属存量面，按"存量先可数、再逐波收"处理：**不批量编造理由**，留挂账（模型 p/严重度已在档），收敛路径 = 逐文件读语义后补说明 |

## 四、门禁与验收

| 判据 | 结果 |
|---|---|
| `bash verify.sh` | **PASS=61 · WARN=0 · FAIL=0** |
| `python -m unittest discover -s desktop/tests -q` | 全绿 |
| `nf conformance` | **27/27 conformant**（含 `modeling` 契约：数据契约 26 · 断言 11 条全过） |

## 五、遗留与不宣称

1. **不宣称"零漏洞"**：本件是**候选面 + 复核面**的结论，不是形式化证明；`nf review` 是**非门禁工具**
   （不进 verify），其候选规则本身也可被审计改进。
2. **三类挂账（内容面，不可由代码修）**：`payload-no-evidence` 19 行（字段只有名字、无类型证据 →
   须模块作者补类型；**我拒绝替作者编类型**）、`unharvestable-payload` 7 行（正文缺事件标记，
   修复需按模块 `machine_contract.events.publish` 归因，属内容编辑）、`silent-skip` 45 行
   （存量 20 个模块，须逐文件读语义补说明）。
3. **模型判定的正确用法**：93 行中模型全部判"是缺口"（p≥0.84），但**是否可修**由证据决定——
   这正是"模型找出、证据裁决、worker 落笔"的固定分工。
