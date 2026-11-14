---
id: AUD-0048
title: 契约级演进时间线
date: 2026-10-30
scope: 扩展 nf diff --history，在不新增顶层命令的前提下从 Git 历史重建 01/02/06/07、协议声明与 protocol/schema 的结构化演进；补齐 Markdown YAML 字段路径与 JSON schema 结构差异
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/contract_history.py:e452d6d8a0d9849dece08210e7af2acbf554440e8871f8d656f745f533d06646
  - desktop/src/core/contract_text.py:01b784e63dd19425b3609ae3792b6c8d9f40366acb5806f71d10759c96de8fd6
  - desktop/src/core/knowledge_sig.py:06409878244907e1135846a71aae76e5d66303534a7e611b8870a1edd307c35e
  - scripts/nf.py:f7aaad82e7a3476fdc4278c60c39698d639800ecdba9d8949bc91f9868144f8c
  - desktop/tests/test_knowledge_sig.py:4705091a139b4fc4da9a61bc816e30eeec3221688f3d923e43afc3b11609c17e
  - desktop/tests/test_nf_cli.py:18c407b6780205e50997d99ab9ea967e6ee066b2dca5d087e9eeea632d311804
  - docs/迁移指南-基于nf-sig-diff.md:02115fdf6e19c01142bc8f2561613ca421318db755769dedbd11498b6149c7b8
  - changes/unreleased/20261030-contract-history.md:4aa6c0df999193ab102115105c450ddae136dfa32c47d07fdebfe271f1059398
---
> 重审（2026-11-14）：WP-15 check45 接线与 G1 收口（机械重绑）

> 重审（2026-11-14）：WP-11 trust bundle 入仓（机械重绑）

> 重审（2026-11-13）：迁移指南顶尖化（签名文档 4 / 历史面 15（4 根+2 protocol+9 schema）/ 影响度 3 值 / 命令三形态 + 现状对照 / 复现）+ 契约判据 test_migration_guide_doc_contract。

> 重审（2026-11-09）：方法包声明可跑入口 runnable，清单与文档共用（含入口存在性判据）

> 重审（2026-11-09）：证人核对接入生产路径：session.step(root=) + CLI 传 ROOT

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


# 契约级演进时间线

## 开工依据

仓内已有 `nf sig` 与双文件 `nf diff`，也有版本迁移指南和 CHANGELOG，但没有面向正式契约的
持久演进视图：两次契约修改之间只能手工找 Git 提交、逐个导出文件再比较，无法直接回答
“这份契约何时发生 additive/bump、当时对应哪次提交”。

独立读者侧验证器、轨迹回放与社区包分级均已在仓内存在，故本轮不重复建设这三面。

## 落地面

- `nf diff --history N <契约路径>` 从 Git 历史按旧→新重算签名，输出提交、日期、摘要、
  影响度与结构化变更；`--json` 返回 `nf-contract-history/1`。
- 允许面：`01/02/06/07` 协议文档、`protocol/CONFORMANCE.md`、`protocol/EXTENSION.md` 与
  `protocol/schema/*.json`；路径经过仓库包含性判据。
- Markdown 在既有章节、引用、版本签名上增加 YAML 字段路径；字段删除进入需评审/`bump`。
- JSON 比较规范结构路径：移除、类型/版本变化、`required` 增加判 `bump`；普通字段新增判
  `additive`；正文/描述类值变化判 `editorial`。
- 命令只读，不生成迁移记录；既有迁移四步与 check30 仍是 bump 的处置门禁。

## 验证

| 检查 | 结果 |
|---|---|
| `tests.test_knowledge_sig` | 10/10 PASS（时间线、JSON required、YAML 字段删除、路径拒绝、文本/文件签名等价） |
| 受影响组合 | 233/233 PASS（terminal / changelog / CLI JSON face / nf CLI / knowledge sig） |
| 真实 01 时间线 | 3 次提交可复原；2 次正文更动判 editorial |
| 真实 `contract.schema.json` | 3 次提交可复原；host_consumed 新增判 additive；`$id` 变化判 bump |
| 风格 / 规模 / 耦合 | 定向扫描通过；新增模块均在冻结上限内 |

## 遗留与边界

- 历史读取不跨文件改名推断；路径改名前的提交明确拒绝，不伪造连续签名。
- `--history` 限 1..200 个最近提交，避免无界读取；需要更长历史时分段核查。
- 该时间线是变更事实与影响度工具，不是迁移批准器；bump 仍须作者/维护者按协议留档。
