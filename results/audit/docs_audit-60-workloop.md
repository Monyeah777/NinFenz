---
id: AUD-0012
title: 构建回路（决策模型挑活 → 生成式 worker 落笔 → 门禁验收）——「让模型替我干活构建 NF」的落地形态
date: 2026-09-22
scope: 作者澄清「让这些模型替我干活，来构建 NF」——把决策层从「NF 运行时的决策模块」改判为「构建 NF 过程里的决策者」；本件只对回路机制、工单契约与实测数据建档（不含任何真实模型推理结果）
verdict: pass
auditor: 本轮执行者
subjects:
  - verify.sh:5c6a3c1b051bd3b5990e981f56eb7cf31df7b192d34740534f221c3c072c899f
  - protocol/decision_layer.json:9330d4057f07647d67f15daa6f37c84913834b7eed65f4e360bf5c7c413e5e06
  - desktop/src/core/workloop.py:3ee94f2c11939abba5507741c6b9b4dae8e8cab77c3bda38419678e31e097056
  - desktop/src/core/decision_layer.py:b31b67d1feda7bd520aea978e19ab3e165c5524c058c24605e0dc5e800ff1d32
  - scripts/nf.py:f10e73e068c8920700f32819212dd63862cab626d0a171ddd1c616f7e261b00f
  - desktop/tests/test_decision_layer.py:551419122f09c1b77f73e7724919f67698bd6d939c3d556d9c8ef98274a76257
  - docs/decision-layer.md:cefef53f4a418ccbd7cc1f96a31850454685bcc4d959cabddceea94e1a9c30de

---
> 重审（2026-11-09）：快照25 两处红：--pack-checklist 进编码闸 + 矩阵判据支持裸模块名

> 重审（2026-11-09）：方法包可执行化：checklist 投影 + nf cognition --pack-checklist

> 重审（2026-11-08）：快照20 红修复：--pairs 入闸/json_doc/分组表接入探针/耦合重算

> 重审（2026-11-08）：口头置信触发策略（触发器非证据）+ CLI --threshold

> 重审（2026-11-08）：calibrate 文案收口

> 重审（2026-11-08）：cog calibrate CLI（可靠性表出口）

> 重审（2026-11-08）：Ingress 启动自检（四道闸探针，非空转判据）

> 重审（2026-11-08）：快照锁：json_doc/atomic_write/sink 登记/文档计数/编码闸门

> 重审（2026-11-08）：claim-check 直吃作业单（免手抄 evidence）

> 重审（2026-11-08）：主张→证据作业单（每个 required 一条 unknown 槽）

> 重审（2026-11-08）：快照红修复：job 描述/面信封/权重/耦合面

> 重审（2026-11-08）：全量门禁收口：json_doc/atomic_write/面判别键/dead-code/静默跳过/路径旗标/ingress 接线

> 重审（2026-11-08）：K1 作业账本 + K4 事件流 + K8 启动自检（P6 第二件）

> 重审（2026-11-08）：双核桥（commitment + 回灌 + 闭环）

> 重审（2026-11-08）：判据注册表 + 主张编译（证据义务清单/三态核对）

> 重审（2026-11-08）：元算子层（11 ops + 触发引擎 + 双 trace + 反仪式化）

> 重审（2026-11-08）：认知工作台 L0（discourse/15 moves/records/replay + nf cog）

> 重审（2026-11-08）：密钥透明目录 v0（版本根/追加链/包含证明/分叉见证）

> 重审（2026-11-07）：方法包 v0 收尾（风格/度量重冻）

> 重审（2026-11-07）：方法包 v0（3 个领域包 + 组合 + 研究计划接线）

> 重审（2026-11-07）：认知核研究层：方法库 + 切片计划器 + CLI（切片检索词/方法论路径/证据台账）

> 重审（2026-11-07）：命令树拆分（production 321→117 行 + 新组 evidence_face 207 行）

> 重审（2026-11-07）：门禁修：silent-skip 理由 / 两个文本参数登记 / --mode 复核

> 重审（2026-11-07）：cc_check 文本层：法规原文→意图草稿（规则抽取，四张账）

> 重审（2026-11-07）：吊销公钥信任锚（钉根 + 有界委派 + 过期/scope/链深判据）

> 重审（2026-11-07）：载体层：WebP/MP4/PDF 附加块 + PNG 像素水印（判据含 JPEG 不扛的期望行为）

> 重审（2026-11-07）：RFC 3161 可信时间戳（timestamp 模块 + CLI + 证据复验时间锚）

> 重审（2026-11-07）：revocations_seed 进二进制豁免 + 两份文档项数同步（62→65 / 34→43）

> 重审（2026-11-07）：ed25519 吊销签名（非对称：验证方只持公钥）+ 回归判据

> 重审（2026-11-07）：batch_target 登记修正（位置参数进文本面，不进旗标名单）

> 重审（2026-11-07）：nf evidence batch（目录逐件复验，整批不可用即失败）

> 重审（2026-11-06）：机器面 NF_HOME 可移植（nf.py 变更）

> 重审（2026-11-06）：CLI 命令树拆分 + 旗标字面读取（nf.py 变更）

> 重审（2026-11-06）：task-27 吊销新鲜度：revocations/evidence/nf.py 变更，重绑被审对象

> 重审（2026-11-06）：JPEG 载体 P0 硬化（nf.py/CLI 文案变化）+ 口径清理，重绑被审对象

> 重审（2026-11-06）：JPEG APP15 载体（扫描数据不变）+ 真 PNG 夹具判据

> 重审（2026-11-06）：Q0-r2：evidence verify 增 --policy-digest 期望比对（nf.py 参数面变化），重绑被审对象

> 重审（2026-11-06）：耦合面重冻（载体模块行数变化后 metrics 面漂移）

> 重审（2026-11-06）：cc_label PNG iTXt 载体（可读回/不改像素/CRC 合法）

> 重审（2026-11-06）：注册 --decision 参数进编码/路径闸门（其提交遗漏）

> 重审（2026-11-05）：Q0 决策证据绑定：scripts/nf.py 增 --decision 入口、evidence/attest/nf_verify 增 decision 绑定，重绑被审对象摘要

> 重审（2026-11-05）：容器面加固：路径安全闸门 / 重名判死 / 解压上限（攻击矩阵 33→35）

> 重审（2026-11-05）：cc_label sidecar 回退（nf-label-sidecar/1，绑定对象摘要）

> 重审（2026-11-05）：--compile 参数登记进编码/路径闸门

> 重审（2026-11-05）：cc_check 编译面 v0：意图 → 封闭词表策略（不可表达逐条挂账）

> 重审（2026-11-05）：G2 吊销分发件（签名 feed：签发/校验/合并，防回滚）+ nf.py 导入块排序

> 重审（2026-11-05）：label 声明层补登记（编码闸门/路径旗标）+ 删零引用函数

> 重审（2026-11-05）：cc_label 声明层（nf-label/1 IR）+ 供应链核对进发布结论

> 重审（2026-11-05）：G1 外部锚点：证据包可声明并可核对（防整链截断），双实现同口径 + 攻击矩阵 33 条

> 重审（2026-11-04）：分片 1/8 抽检修复：编码闸门/路径旗标名单补全、删零引用常量与函数、耦合基线重冻

> 重审（2026-11-04）：证据线 fail-closed 加固：chain 段必填 / 吊销表坏件判 invalid（攻击矩阵 25→29）

> 重审（2026-11-04）：抽检第二个分片：原子写纪律（包/报告走 atomic_write，临时写例外登记）

> 重审（2026-11-04）：check12 修复波：JSON 面登记 / json_doc 收敛 / Rust 回执去重同步 / 基准 JSON 纯净

> 重审（2026-11-04）：本地 HTTP 面 v0（nf serve --http 三端点）落地 + 端点契约登记 local.*

> 重审（2026-11-04）：cc_resolve（契约面反查）+ 一条链复现脚本落地

> 重审（2026-11-04）：cc_replay 轨迹 + cc_check 单对象策略体检落地（新模块 check_policy）+ 回执去重

> 重审（2026-11-04）：证据复验器扩三种形态 + 攻击矩阵基准（26 项校验路径与基准落地）

> 重审（2026-11-04）：证据包缺省落点改到临时目录（不往仓库落盘）+ CCOS ABI v0 收口

> 重审（2026-11-04）：CCOS ABI v0 + 证据包校验器落地（scripts/nf.py 与 core/terminal.py 摘要变更；并修复本分支既有漂移）

> 重审（2026-10-30）：新增契约级 Git 演进时间线；结构化 Markdown YAML 字段与 JSON schema 差异纳入影响度

> 重审（2026-10-30）：全仓审计口径复核：显式 legacy 清单、subjects 根内解析、Path 参数闸门、惰性导入与 manifest 可复算

> 重审（2026-10-29）：CLI 命令树无损分组、meta-cockpit 接线与恢复分支全量验证后重绑；既有结论不变

> 重审（2026-10-29）：恢复分支全量验证：接线 meta-cockpit 公共模块、清理零引用、修复 ReDoS/CLI 闸门/公开文档路径后重绑；既有结论不变

> 重审（2026-10-25）：跨平台收口：真实路径归一、守护状态读写锁、autostart 原子标记与机器路径短名脱敏

> 重审（2026-10-24）：夜间收口：Rust worker 安全、投稿配额、元数据、schema 与 postmortem 跨平台回执路径修复后按新输入重绑

> 重审（2026-10-24）：CI 并发锁、Gitee 诊断与 ADR-0008 改变 verify/脚本字节；重审理由：相应测试与冻结链已同步

> 重审（2026-10-23）：OTLP ID 判据与合作一致性稳定性修正：traceId/spanId 定长 hex，缺失真源诊断去 OS errno

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

> 重审（2026-10-23）：Rust 快线加速收口：新增常驻 worker / PyO3 原语 / Rayon 解析并行与 code_metrics 接线；被审判据语义未变，digest 随实现同步

> 重审（2026-10-22）：CI 三刀合入后重绑（诊断目录绝对化/fetch-tags/wasm skip）

> 重审（2026-10-22）：H1：nf verify 仓库信任门（重冻）

> 重审（2026-10-22）：测试执行器、进程原子与 Windows shell 解析修复后重算代码度量基线与角色投影；既有审计结论不变

> 重审（2026-10-21）：1.0.5 收口 1

> 重审（2026-10-20）：release 1.0.4 1

> 重审（2026-10-20）：repo hygiene: junk dirs removed, LF normalized

> 重审（2026-10-20）：version governance + daemon leak fix

> 重审（2026-10-20）：D 盘迁移：跨盘 relpath 修复（nf.py 展示面 + trust_boundary 用例）

> 重审（2026-10-19）：check39 挂载五分钟入口判据（docs/quickstart.md ↔ scripts/quickstart_check.sh），verify.sh 结构性新增子判据

> 重审（2026-10-19）：verify.sh 恢复并补 _NF_BG_TESTS_PID 声明

> 重审（2026-10-19）：verify.sh 补 _NF_BG_TESTS_PID 声明（set -u 下 pre-push 钩子炸点）

> 重审（2026-10-19）：nf.py 会话落点放行 .rivet（受限环境唯一可写临时区）

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

> 重审（2026-10-18）：Glama coherence：收紧 spec_ls/registry_query 描述边界；asset_get 说明为协议资产五接口规范名

> 重审（2026-10-18）：P3：分层档位 + 判定缓存 + 受影响测试选择

> 重审（2026-10-18）：P2：check12 分片并行（verify_tests 执行器 + 权重基线）

> 重审（2026-10-17）：步骤5：在场/关键词组收敛到 _decl_check（等价性 15 例逐字节一致）

> 重审（2026-10-17）：步骤4 收口：attest --selfcheck 接线 + 站点/覆盖率分母同步

> 重审（2026-10-17）：步骤4：新增 check41/42（构建隔离 + 不可伪造 provenance）与对应判据模块

> 重审（2026-10-17）：拆聚合门：check32/33/35/36 失败逐条透出（只动 bash 呈现层）

> 重审（2026-10-17）：能力面挂账：assertions.json 增 capability_vocabulary/index + 每条断言 capability

> 重审（2026-10-17）：整批毫秒路径深入：nf verify 增 --jobs（每 check 独立子进程跑 --only N --json，按 check 号排序合并）；机器面增 messages 使并行结果可重放文案；实测 18.6s→6.4s（2.9x）且人读面/机器面与串行逐字节一致；新增 test_verify_parallel_checks 4 条判据（等价+排序+fail-closed）

> 重审（2026-10-17）：门禁提速收口：check39 剪枝定为 target/obj（刻意不剪 bin——实测零收益且可能承载入库脚本）；check39 7.15s→4.06s，差分 6/6

> 重审（2026-10-17）：门禁提速：check39 遍历再剪构建产物目录（target/bin/obj）——engine/rust/target 一处 22454 目录（gitignore），只含产物不含源；实测目录 24712→1949、遍历 4.36s→0.28s（15.5×），判定逐项等价（禁名命中与 desktop/src/ui 在场性一致），差分 6/6 通过；nf verify 冷跑 17.8s→16.3s

> 重审（2026-10-16）：门禁提速（收口）：修 check30 批量化引入的两处路径归一缺陷（git quotepath 非ASCII转义 + Windows glob 反斜杠）——被 test_check30_bump 当场抓出；另打破 gate_engine↔subcheck_cache 模块环（依赖倒置，只回稳定字段字典），并补两处静默兜底理由

> 重审（2026-10-16）：门禁提速：check30 的 127 次 git diff 合并为一次全量调用后按块取（实测 2.016s→0.196s，42 件逐字节等价）；连同 check39 遍历优化，22 条已迁入合计 30.6s→19.1s、nf verify 冷跑 28.7s→17.8s

> 重审（2026-10-16）：门禁提速：check39 遍历由 os.walk 换单遍 os.scandir（同层剪枝 + follow_symlinks=False，省掉每条目一次 lstat 与整棵被排除子树）；实测 10.34s→6.70s，结果集逐字段一致（24712 目录/7221 py），差分 6/6 通过

> 重审（2026-10-16）：子 check 缓存（步骤①）：新增 core/subcheck_cache.py（观测读面+目录项快照+内容寻址，fail-closed）+ gate_faces 增目录列举收集器；实测审计：观测开销 1.4–2.2x，大树遍历 check 命中收益被快照成本吃掉

> 重审（2026-10-16）：L-D 并行结论：默认保持串行（并行结论不稳定：共享守护单例 + 派生面可写），verify_parallel.py 保留为开发侧工具；verify.sh 字节已变，重绑 digest

> 重审（2026-10-16）：L-D 并行收尾：check12 默认按核数并行（上限 16）+ 守护卫生；相关派生面重冻后重绑

> 重审（2026-10-16）：L-D 并行接线：check12 改走 scripts/verify_parallel.py（模块级并行，8 路实测 1255→409 s）+ 守护卫生（只收本次拉起的）；verify.sh 字节已变，重绑 digest

> 重审（2026-10-16）：门禁提速批（续）：拆 gate_native 让引擎回到行数闸门内 + check37 走 runpy 进程内执行，gate_inproc 增 run_script；被审对象字节已变，按本仓流程重绑 digest

> 重审（2026-10-15）：门禁提速批：测试面进程内化（check12 热点）+ 新增 gate_engine/gate_labels 单进程门禁引擎 + 派生基线重冻；被审对象字节已变，按本仓 rebind 流程重绑 digest

> 重审（2026-10-14）：引入 nf audit rebind 命令（core/audit.py + CLI + 顺序纪律 + 两处面收敛）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI + 顺序纪律）：重审并更新 digest 机器化

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI）：重审并更新 digest 口径机器化，替换手搓脚本

> 重审（2026-10-14 · 数字资产契约 S 档：包自述对账 / Frictionless 导出 / 可移植 schema）：被审对象随本波改动（组合包 INDEX 补登 SYSTEM_CARD 契约 / receipts 锚定面续扩 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 本波承重件七件（门禁 / 决策层声明（含 workloop 块）/ 回路模块 / 决策端口 / CLI / 单测 / 对外文档）；任一件再改，本件结论即失效须重审。
> **口径**：subjects 不含派生物（`protocol/RECEIPTS.json`、`protocol/generated/*` 等重签即变，由 check31/check33/check35 自证）。

## 一、判定改口（承接 AUD-0011）

AUD-0011 把 Laya / Open-Jev 接成 **NF 运行时**的决策端口；作者 2026-09-22 澄清真意是
**让模型替人干构建 NF 的活**——于是本波把定位改判为**构建过程的决策者**，并保留运行时段口
（两者共用同一 `core/decision_layer.py`，不是两套代码）。

**能力边界（决定分工，不可含糊）**：Laya 是编码器分类（ModernBERT-large + 决策头）、
Open-Jev 是非自回归 + 决策头 —— **都不会写代码或正文**。因此回路三段分工：

```
决策模型：挑下一个工作项 / 判改动面风险 / 定「能否在不碰回执锚定件的条件下完成」
   ↓（工单：目标 + 证据 + 落点 + 完成判据 + 验收命令）
生成式 worker（人 / Codex / 生成式模型）：按工单落笔
   ↓
NF 门禁：verify.sh 全绿 + nf conformance conformant（唯一验收口）
```

## 二、本波交付

| 类 | 件 | 要点 |
|---|---|---|
| 模块 | `desktop/src/core/workloop.py` | 待办真源 = **公开声明件**（`type_backlog.json` 104 未定型字段 + `pipeline_advisory.json` 102 advisory）；`state()` 快照 / `items()` 工作项 / `questions()` 类型化提问 / `plan()` 出工单 / `write_order()`+`close()` 内部档案记档 / `scan()` 回路体检 |
| 提问契约 | 每轮 = 1×`choice`（挑活）+ N×`score`（风险：低/中/高）+ N×`noul`（能否安全做） | **请求自带候选证据**（id/title/detail/where）——这类模型只对给定 state 作答，不给候选正文它们无从判断（本波自查修正过一次） |
| 工单契约 | `nf-workorder/1` | 必带 `goal/evidence/where/done_when/accept/worker_role`；`accept` 固定为门禁命令；`decision.note` 明写「决策层只给选择与概率；**它不写内容**」 |
| 入口 | `nf workloop` | `--list`（候选面）/ 默认出工单 / `--write`（落 `.rivet/private_archive/work_orders/`）/ `--close --outcome --gate --note`（收口记档） |
| 四条不可协商 | `protocol/decision_layer.json: workloop.non_negotiables` | ① 决策层不生成内容；② 工单只落内部档案（计划类产品内部消化）；③ 落笔方必须是 worker；④ 验收只认门禁 |
| 门禁 | check33 第 16 面 | 待办真源非空且 id 唯一 / 工作项六字段齐 / 问题形状合规（复用 decision_layer 判据）/ **stub 工单确定性** / 所选在候选集内 / 工单目录在内部档案前缀下 |
| 测试 | `test_decision_layer.py` +6 例（合计 18） | 回路体检零 issue / 工作项来自公开声明 / 工单确定性与验收命令 / 工单只落内部档案 + 收口 / 适配器不可用即 abstained / 空真源 → `empty` |
| 文档 | `docs/decision-layer.md` 增「构建回路」节 | 含分工图、命令、四条不可协商、实测数据 |

## 三、实测（本仓 2026-09-22）

| 判据 | 结果 |
|---|---|
| `nf workloop --list` | 待办 **206 项**在册（未定型字段 104 + advisory 102） |
| `nf workloop --top 5` | 工单成形：`WO-c9618c9f6e8a` · 所选 `TB-001:beat_tick.buffered` · `gate_safe=1.00` · `risk_level=2.00`（stub `calibrated=false`，只是排序信号） |
| 确定性 | 同输入两次工单**逐字段一致** |
| 落点纪律 | 工单/收口件只落 `.rivet/private_archive/work_orders/`（公开仓零新增过程件） |
| fail-closed | `--adapter systemone-http` 缺 endpoint → 回路 `abstained` + reason |
| `bash verify.sh` | PASS=61 · WARN=0 · FAIL=0（check1-37 不变；回路并入 check33 第 16 面） |

## 四、遗留与不宣称

1. **仍未拉取/运行真实模型**：`pulled=false` 不变 —— 本波验证的是**回路机制**（挑活 → 工单 → 验收），
   不是模型质量；真实模型的挑选结果属外部运行事实，须拉取后另立实证。
2. **stub 的风险评估无信号**（均匀分布）：它只按关键词计分，`calibrated=false` 已标注；
   要真判断风险必须接真模型（`--adapter systemone-http`）或换 `openai-json`（同样 `calibrated=false`）。
3. **回路不自动落笔**：本波按 `STRATEGY §四`（计划内部消化）坚持"工单只落内部档案"，
   公开仓只收**结果形态**（代码 + 收口注记 + audit）。
4. **待办真源的口径**：回路只认公开声明件里的待办（type_backlog / pipeline_advisory）；
   其他缺口（如外部输入队列）若需入回路，须先成为**声明件**（不新造私有队列）。

## 五、首轮回路实战（落笔记录 · 2026-09-22）

回路第一次**真关环**（决策层挑活 → 生成式 worker 落笔 → 门禁验收 → 收口）：

| 段 | 事实 |
|---|---|
| 决策 | `WO-c9618c9f6e8a`，所选 `TB-001:beat_tick.buffered`（`gate_safe=1.00`，stub `calibrated=false`） |
| 落笔（worker = 本轮执行者） | 查明根因：该字段无从定型**不是**缺证据，而是 M94 正文用 `produce:`，而收割器只认 `event:`/`name:`/`publish:` → 在 M94 §4 补**机读事件契约**（`event: beat_tick` + `payload: { tick: number, day: number, minute: number, origin: string, buffered: boolean }` + 语义注记，全部与 §3 同源） |
| 机制反应 | `nf module types --harvest --write` 收窄 **2 字段**（`origin→string`、`buffered→boolean`，note 标「正文 payload 收割，证据可溯」）；事件载荷类型覆盖 **42.9% → 44.0%**；`type_backlog` **104 → 102** 项 |
| 连带精化 | `nf module types --write` 按同一证据链回溯补标 **15 件**模块 `io_types`：**35.4% → 41.7%**（91/218 字段） |
| 门禁反应 | `module-signature` 报 15 件边界漂移（类型精化 = 接口面变化）→ 按设计**显式重冻结** `protocol/module_signatures.json`（48 模块）；旧审计（AUD-0002 等）摘要重绑 |
| 验收 | `bash verify.sh` **PASS=61 · WARN=0 · FAIL=0**；`nf conformance` **27/27 conformant**；unittest **981 例全绿** |
| 收口 | `.rivet/private_archive/work_orders/WO-c9618c9f6e8a.close.json`（outcome=landed · gate=PASS=61 · 27/27） |
| 下一步 | 回路随即产出下一张工单 `WO-c04a3bb64192`（`campus_anonymous_gift.item`）——待办真源变化后候选面自动前移 |

**方法论收获（写进机制而非日记）**：① 类型缺口有三种，只有第三种需要「补内容」——**缺证据**（正文没写）、
**证据不可读**（写法不在收割器语法内，如本例的 `produce:`）、**证据冲突**（正文与注册表不一致，只报告不改）；
② 类型精化会触发边界签名重签，这是**设计意图**（接口面变了就要留痕），不是噪声——本波按提示显式重冻结，
而非为省事放宽判据。
