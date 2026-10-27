---
id: AUD-0009
title: 外部协议清单吸收波（162 条 → 逐条实证 → 净吸收 15 条归并 10 项机制）——编码卫生 / 互操作导出 / 文档命令面 / JSON-RPC 结构约束
date: 2026-09-21
scope: 作者指示的七项任务（NF 深析 / 外部协议清单 ≥100 条 / 逐条与 NF 对比 / 转成可吸收项 / 直接执行吸收 / 每条抽象可相似点 / 连续运行）；本件只对本波落地的四项门禁新面与清单判定分布作实证建档
verdict: pass
auditor: 本轮执行者
subjects:
  - verify.sh:eacd4c758fde0471336c07cb789ebbad39868899cb1cc5cb4eb4d38bf3f5a615
  - .gitattributes:f6fb4175293c85a259d4c60564352c811dded74210c1ad54ec4bfc0376a4188a
  - desktop/src/core/text_hygiene.py:99b38bfbb8656ad653689c4cba93679970a78183019fd5f02e2380d87ec99ff3
  - desktop/src/core/interop_export.py:ff00f77a4236929cb64dfd120f9a60952ba8013843681cc0586a96f0c155564c
  - desktop/src/core/mcp_runtime.py:4929a1fe7b789ed86d8978f6c49ccf120ecc7a44e741f3e38dc79c8f1aa0b23d
  - desktop/src/core/prose_lint.py:6519b1dc812a4f7ec98b1f8847446f23373408a7ea47c366bb881185e4255a68
  - desktop/src/core/license_gate.py:602d29e257651283e5d51cd173568878ab7cb4daa385a79fd79e53cd37ff3889
  - desktop/src/core/doc_hygiene.py:5cc5d9d0fe0bea3f609d26759ac497aeb92363b0c6b045c1ca6cd67687bae850
  - desktop/src/core/endpoint.py:cebaf7f18f50d63c9d06c79e6172aae8dfea0efd84764ef884e28bda0387b8f4
  - desktop/src/core/purity_scan.py:fca0cb83b756f6ac1879d0f720dfe691ede17953421f947a4316040262a94e52
  - scripts/nf.py:f7e42286a7edd88948cbe13d2cb7cce45ad462d94584b4722918f7b0c847d6d5
  - scripts/check_external_links.py:1cbee65ba19a83fbcdf333e35b8d99c2e45f3b400f3a025860357baf7a806b02
  - scripts/check_interop_schemas.py:f9c1add0ee80fb23a3913e32482027e9a4049c5ce70cb35b2b1be4afa075d091
  - results/interop-schema-validation.md:e2546c6407416b61912ac351d14d20c171167e36be4d4d3461f6c2fceb56c0c9
  - docs/interop.md:f884a0533ed89aae8c83a2a44da491afb334c083dc05051158ac3a91e88e4f5c
  - docs/text-hygiene.md:36edf35f60bc669192443a8c16a4bcdc7c22408270fff5ea15308a16a756f986
  - docs/endpoint.md:4da6d07f9d0ed0a7166c028b1a4070a370f2edc9e70e700cce03c3d38b4e930f
  - docs/mcp.md:c4fa52d36097253e197304e6bf6e0512bc2708077fb8ef34865653fc764caa78
  - llms.txt:7e011303eae22d163cdbb085934f7264dd5922e1d5e8a5eefa1a139d7be74323

---
> 重审（2026-10-27）：S2r: daemon split -> nf_cmds/daemon.py

> 重审（2026-10-27）：S2q: preset/import split; _open_store -> common

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

> 重审（2026-10-27）：S2a: purity local-package detection + helper extraction

> 重审（2026-10-27）：S2a: shared CLI helpers -> scripts/nf_cmds/common.py

> 重审（2026-10-27）：S1: rebuild governance after CRLF->LF normalization

> 重审（2026-10-27）：S1: CLI scanners cover nf_parser

> 重审（2026-10-27）：S1: extract nf.py::_make_parser into scripts/nf_parser (surface byte-identical)

> 重审（2026-10-27）：Merge W12: check46-47 + bilingual glossary

> 重审（2026-10-27）：T12.2 英文术语层：新增 protocol/glossary.json entries（33 条双语术语）+ core/glossary.py + nf glossary check/render + docs/protocol/glossary.en.md；新增顶层命令 glossary 与 terminal FAMILIES/命令地图重生成；按冻结上限重冻 code/coupling 基线并重绑对象 digest

> 重审（2026-10-27）：Merge W11: content SRE + privacy/air-gap + CLI map

> 重审（2026-10-26）：Merge W10: model check + concept index + agent contracts

> 重审（2026-10-26）：Merge W9: gate43-45 + DOCX/DITA importers + PyPI packaging

> 重审（2026-10-26）：T9.2 导入器：新增 core/import_docx.py、core/import_dita.py 与 nf import docx|dita（scripts/nf.py 增长），按冻结上限重冻 code/coupling 基线；按审计协议重绑对象 digest

> 重审（2026-10-26）：Merge W8: JS second impl + registry CID + security scan

> 重审（2026-10-26）：Merge W7: contract semantics + content IR + reference runtime

> 重审（2026-10-26）：T7.2 内容 IR：新增 desktop/src/core/content_ir.py 与 nf ir check 命令（scripts/nf.py 增长），按冻结上限重冻 code/coupling 基线；按审计协议重绑对象 digest

> 重审（2026-10-26）：Merge t-m1/t-record/t-bench: M1 evidence rule, exec record, bench leaderboard

> 重审（2026-10-26）：Merge t-maturity: M0-M3 evidence-based maturity + registry projection

> 重审（2026-10-26）：Merge t-scope: scoped allowed_module_ids + --loose

> 重审（2026-10-26）：Merge t-compliance: regulatory profile 34 clauses + 9 assets + evidence pack

> 重审（2026-10-26）：Merge t-identity: deliverable-contract first screen + demo/presets/library ordering

> 重审（2026-10-26）：Merge t-techdoc: techdoc pack depth + new gate modules

> 重审（2026-10-26）：Wave2: SSOT facts.json + domain gate + gate manifest

> 重审（2026-10-26）：rebase 到 fa3fdd58 后重冻（atoms/nf/perf_budget）

> 重审（2026-10-25）：Scorecard 收口：最新 main 合并、CODEOWNERS ASCII 化、SAST/Fuzzing、最小权限、依赖漏洞与容器 digest 统一重绑

> 重审（2026-10-25）：1.1.0 版本面 + CLA workflow + 定价

> 重审（2026-10-25）：分层双许可（1.1.0 起）

> 重审（2026-10-25）：跨平台收口：真实路径归一、守护状态读写锁、autostart 原子标记与机器路径短名脱敏

> 重审（2026-10-24）：夜间收口：Rust worker 安全、投稿配额、元数据、schema 与 postmortem 跨平台回执路径修复后按新输入重绑

> 重审（2026-10-24）：CI 并发锁、Gitee 诊断与 ADR-0008 改变 verify/脚本字节；重审理由：相应测试与冻结链已同步

> 重审（2026-10-23）：OTLP ID 判据与合作一致性稳定性修正：traceId/spanId 定长 hex，缺失真源诊断去 OS errno

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

> 重审（2026-10-23）：Rust 快线加速收口：新增常驻 worker / PyO3 原语 / Rayon 解析并行与 code_metrics 接线；被审判据语义未变，digest 随实现同步

> 重审（2026-10-22）：CI 三刀合入后重绑（诊断目录绝对化/fetch-tags/wasm skip）

> 重审（2026-10-22）：H1：nf verify 仓库信任门（重冻）

> 重审（2026-10-22）：S1：scratch GC 只删 nf-<12hex> + 根标记（重冻）

> 重审（2026-10-22）：R2：MCP 内部错误脱敏（重冻·修订）

> 重审（2026-10-22）：R2：MCP 内部错误脱敏（重冻）

> 重审（2026-10-22）：测试执行器、进程原子与 Windows shell 解析修复后重算代码度量基线与角色投影；既有审计结论不变

> 重审（2026-10-21）：1.0.5 收口 1

> 重审（2026-10-20）：release 1.0.4 1

> 重审（2026-10-20）：repo hygiene: junk dirs removed, LF normalized

> 重审（2026-10-20）：version governance + daemon leak fix

> 重审（2026-10-20）：D 盘迁移：跨盘 relpath 修复（nf.py 展示面 + trust_boundary 用例）

> 重审（2026-10-19）：check39 挂载五分钟入口判据（docs/quickstart.md ↔ scripts/quickstart_check.sh），verify.sh 结构性新增子判据

> 重审（2026-10-19）：CRLF 归一后派生面重算：被审承重件 digest 校准，审计结论未变

> 重审（2026-10-19）：verify.sh 恢复并补 _NF_BG_TESTS_PID 声明

> 重审（2026-10-19）：verify.sh 补 _NF_BG_TESTS_PID 声明（set -u 下 pre-push 钩子炸点）

> 重审（2026-10-19）：nf.py 会话落点放行 .rivet（受限环境唯一可写临时区）

> 重审（2026-10-19）：EOL 归一 + 译件重签

> 重审（2026-10-19）：verify.sh 诊断目录/临时变量修复后重绑

> 重审（2026-10-19）：诊断目录兜底：TMPDIR/仓库内 .rivet/tmp

> 重审（2026-10-19）：full 重叠回退（实测更慢且内容面互扰）

> 重审（2026-10-19）：full 档也重叠 + 单分片内层线程按核数

> 重审（2026-10-19）：knowledge_order_read 去 annotation 重叠，补 filtered-order/count；tdqs 两次 4.9、全部工具 >=4.9

> 重审（2026-10-18）：工具名归一：6 个旧名 -> _list/_search/_read；旧名 alias；官方 tdqs 4.9 两次

> 重审（2026-10-18）：动态队列 + 常驻集收敛 + 分片上限 16

> 重审（2026-10-18）：重叠范围收窄到 quick

> 重审（2026-10-18）：TDQS 最终 4.8-4.9：补 local-only/no-auth、no offset、exact package、no pagination；12 工具均 >=4.8

> 重审（2026-10-18）：knowledge_order：分段 + no auth/network/rate/writes；本地 v4-pro 4.8

> 重审（2026-10-18）：quick 档测试与静态 check 重叠执行

> 重审（2026-10-18）：asset_read：删除 outputSchema 的 found（无匹配为错误），2 参数 schema 一致；本地 TDQS 4.8/4.9

> 重审（2026-10-18）：矩阵化落地后重绑一致性面

> 重审（2026-10-18）：CI 门禁矩阵化（32 片）

> 重审（2026-10-18）：TDQS lint：修复 4 个 titleIsMeaningful=false；asset_read 100 词标准版

> 重审（2026-10-18）：asset_read 第五轮：按 TDQS 50-100 词上限压到 100，保留 5 段与输出/参数/限制

> 重审（2026-10-18）：asset_read 第四轮：109 词 5 段 + 输出形状 + package 交互

> 重审（2026-10-18）：asset_read：补 package 只缩文件集不改 key 匹配（参数交互）

> 重审（2026-10-18）：asset_read 第四轮：恢复段落结构（5 段），目标 Conciseness 5

> 重审（2026-10-18）：asset_read 第三轮：84→74 词，压缩替代方案括号

> 重审（2026-10-18）：P3：缓存写走 atomic_write（脚本面纪律）

> 重审（2026-10-18）：asset_read 目标 5：再压到约 91 词，补 no glob/regex/fuzzy + package directory 语义

> 重审（2026-10-18）：asset_read 描述再压缩：去示例、缩短匹配句中句

> 重审（2026-10-18）：Glama 逐工具精修：asset_read 明确 key/package 意图与 when-not-use，去重只读尾句

> 重审（2026-10-18）：P3：缓存脚本去掉删除面（保 Rust 快线 purity 口径一致）

> 重审（2026-10-18）：Glama TDQS：删除 12 工具重复只读尾句，改显式 when-not-use；保留错误/空结果/扫描行为

> 重审（2026-10-18）：P2：分片数按核数自适应

> 重审（2026-10-18）：Glama coherence：新增 pattern_ls/asset_ls；asset_read 兼容别名；同步 12 工具面

> 重审（2026-10-18）：Glama coherence：asset_read 兼容别名说明（中/英/日）

> 重审（2026-10-18）：Glama coherence：asset_get→asset_read（旧名兼容别名）+ 协议边界描述；行尾规范为 LF

> 重审（2026-10-18）：Glama coherence：MCP 面 asset_get→asset_read（旧名保留兼容别名）；spec_ls/registry_query 描述边界

> 重审（2026-10-18）：Glama coherence：收紧 spec_ls/registry_query 描述边界；asset_get 说明为协议资产五接口规范名

> 重审（2026-10-18）：P3：判定缓存 + 分层档位（sink 登记）

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

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 本波承重件十九件（门禁 / EOL 声明 / 编码卫生 / 互操作导出 / MCP 硬化与帧纪律 / 文档命令面 / 许可表达式门 / 文档分类表 / 端点幂等判据 / sink 登记自洽 / CLI 入口 / 外链巡检重试面 / **外部 schema 校验工具与其取证报告** / 四份对外文档 / 机器入口）；任一件再改，本件结论即失效须重审。

## 一、开工依据（内部差距实证，不含外部论据）

按 STRATEGY §3.3（立项理由不得引用外部、质量论证不得引用外部背书），本波四条开项理由**全部来自仓内实证**（探针脚本 `.rivet/scratch/probe57*.py`，只读）：

1. **承载编码无判据**：全仓文本件/JSON 件此前无 BOM、行尾、键唯一、标识面同形四项检查——实测工作区 6 件被 Windows 侧写成 CRLF（`.gitignore` / `05_资产库/provenance.json` / 两件用户自定义资产 / 两件 E1 外部验证样本），而 `git hash-object` 与 `git rev-parse HEAD:` 逐件比对显示 **git 侧 blob 全为 LF**（漂移只在工作区）；另实测 `protocol/**` 存在重复键的可能性无法被任何门禁看见（无判据即为盲区）。
2. **声明面厚、导出面缺**：8 条服务端点契约 + 43 条事件载荷 + 48 条协议层回执 + 依赖登记面（hard/soft import）都是 NF 形状的 JSON，**无一条能直接喂给 OpenAPI/AsyncAPI/in-toto/SPDX 工具链**（外部读者只能读 NF 自述形状）。
3. **文档命令面无判据**：`driver.json` 只锚住三个指令档；README / ROUTES / 07 导航 / `docs/**` 里写的 `nf <子命令>` 写错时，门禁一条都不会红。
4. **协议边角条款无判据**：JSON-RPC 2.0 §4.2（params 必须结构化）与 §5（id 可判定须回显）在 MCP 运行时**静默放行**——实测 `params="raw"`、`params=[1]`、`id={...}` 三种请求全部按成功返回（错误请求被当成合法请求）。

## 二、清单与判定（162 条）

采集面 = GitHub 标准/规范仓与 awesome 索引 + 搜索引擎检索 + 标准组织公开目录（IETF / W3C / OASIS / ISO-IEC / Unicode / OpenSSF / SPDX / in-toto / CloudEvents 等）。**纪律声明**：外部标准不构成立项理由（禁令一），判定只认仓内实证；逐条台账（含每条的可相似点抽象）留内部档案 `57`，公开侧只落结果。

| 判定 | 条数 | 处置 |
|---|---|---|
| 已具备（不重做） | 74 | 写出 NF 侧实证件（协议件 / core 模块 / check 号），零改动 |
| 部分覆盖 | 18 | 主干已覆盖、边角未落；其中 23 条转成本波吸收 |
| 净吸收已落地 | 26 | 归并 20 项机制（第一轮 10 + 第二轮 4 + 第三轮 2 + 第四轮 4，见 §三） |
| 挂账候选 | 6 | 逐条写明触发条件（透明日志 / CycloneDX / VC 凭证 / C2PA / CID 寻址 / 内容分级——**幂等键、CWE、A2A 已分别由第二/三轮收掉**） |
| 不适面剔除 | 38 | 需运行时、网络服务或模型通道，或与「不产没人消费的东西」冲突（含以外部框架作判据的条目） |

## 三、本波交付（四项机制 + 一个入口 + 两份文档）

| 类 | 件 | 要点 |
|---|---|---|
| 机制 | `core/text_hygiene.py` + check33 第 9 面 | RFC 3629 / RFC 8259 §4 / RFC 7493 / UAX #15 / UTS #39 五条判据一次落地：UTF-8 严格可解码、无 BOM、行尾 LF、JSON 键唯一、标识面 NFC + 字符集（ASCII + CJK 汉字 + `$` 保留键前缀）；每条违规带修复指引 |
| 机制 | 仓库根 `.gitattributes` | `* text=auto eol=lf` + 二进制面显式声明（属性优先于 `core.autocrlf`，任何平台检出即 LF）；同门判据「声明在位」——EOL 纪律须有落点 |
| 机制 | `core/interop_export.py` + check33 第 10 面 | 纯派生四件：OpenAPI 3.1（8 端点 + NfError + RFC 9457 映射）、AsyncAPI 3.0（43 通道 + CloudEvents 属性）、in-toto Statement v1（48 subject + sha256）、SPDX 2.3 SBOM（4 包）；门禁判覆盖完整 + 形状合法 + 两次渲染逐字节一致 + 真源缺失 fail-closed |
| 机制 | `prose_lint.command_face` + check33 第 12 面 | 文档命令面 ↔ CLI 注册表 / MCP `TOOL_DEFS` 一致性；只判「当作命令呈现」的片段（行内代码 + 围栏块），不误伤散文 |
| 机制 | `core/mcp_runtime.py` 硬化 + check33 第 11 面 | JSON-RPC 2.0 §4.2：params 原始类型 → `-32600`、数组 → `-32602`；§4：id 须字符串/数字/null；§5：id 可判定则回显（`_err_at`） |
| 入口 | `scripts/nf.py interop`（`--list/--check/--kind/--out`） | 四种导出形状统一入口；`--check` 走门禁 |
| 文档 | `docs/interop.md`（how-to）· `docs/text-hygiene.md`（reference） | 入 `doc_hygiene` 三表（DOC_KINDS / REQUIRED_DOCS / INSTRUCTION_DOCS），头部标记与「最后更新」位齐 |
| 机制（第二轮） | `mcp_runtime.encode_message` + check33 第 13 面 | stdio 帧纪律（NDJSON 口径）：一条消息一行 + `U+2028`/`U+2029`/`U+0085` 行边界陷阱转义 + 通知不写行 |
| 机制（第二轮） | `protocol/endpoint_contract.json` 幂等面 + `endpoint.scan` 判据 | RFC 9110 §9.2.2：默认幂等 + `idempotency_exceptions`（`bench.evaluate` → 幂等键 required）；未声明幂等语义即 FAIL；派生面 `x-nf-idempotency` |
| 机制（第二轮） | `purity_scan` R6 自洽面 | 每条 sink 带 CWE 对齐（CWE-78/95/470/502）+ `SINK_ALLOW` 放行键须指向已登记 sink |
| 机制（第二轮） | `scripts/check_external_links.py` 退避重试 | `is_transient` / `retry_after_seconds` / `probe_with_retry`（只对瞬态重试、退避翻倍、尊重 Retry-After、4xx 一次定性）+ `--retries/--backoff` |
| 机制（第三轮） | `interop_export.slsa_provenance`（`nf interop --kind slsa`） | SLSA Provenance v1：本地门禁口径（`buildType` 自定义型别 + 版本头/基线句作外部参数 + 48 subject）；**「不构成 SLSA 等级声明」注记为门禁判据** |

> **自审发现并当场修掉的真缺陷（记档）**：SLSA 派生面首版把基线句读自 `protocol/score_baseline.json`——
> 该文件只有 `score/signals/metrics`，**没有 check 数 / PASS 数**，于是产出 `check1-0 PASS=0` 的
> 假基线（"看起来有条目、其实是 0"）。根因 = 参数源选错（拿了分数台账当基线真源）。
> 修法：改用 `core.quality_baseline.EXPECTED_CHECKS/EXPECTED_PASS`（基线句真源），
> 并新增门禁判据——基线句非法、为 0、或与 `quality_baseline` 期望值不一致即 FAIL。
> 实测修正后为 `check1-37 PASS=61`；`test_interop_export` 增断言钉住两处同源。
| 机制（第三轮） | `interop_export.a2a_agent_card`（`nf interop --kind a2a`） | A2A Agent Card：skills = 端点契约投影（8 条），`streaming` 由契约推出，未实装须显式注记 |
| 机制（第三轮） | `mcp_runtime.uri_template_issue` / `template_matches` + check33 第 13 面扩 | RFC 6570 一级子集 + **模板⇄真实 uri 覆盖**（5 模板合法、390 条真实 uri 零未覆盖） |
| 机制（第四轮） | `license_gate.expression_issue` | SPDX 许可表达式词法判定（AND/OR/WITH/括号/`+`/LicenseRef + 运算符位置与缺操作数） |
| 机制（第四轮） | `text_hygiene.semver_issue` + 域包 version 面 | SemVer 2.0.0 词法（前导零 / 缺段 / 空预发布段），7 个域包版本位在扫；资产自由槽版本边界写明 |
| 机制（第四轮） | `text_hygiene.VALUE_SOURCES` + `_resolve` | 标识**值**面词法（registry / vocabularies / provenance，95 个值）——堵「键查值不查」的同形后门 |
| 机制（第四轮） | `interop_export.prov_document`（`nf interop --kind prov`） | PROV-O 图：59 节点（53 实体 / 3 活动 / 3 代理），空面如实为空；门禁判节点唯一 + 关系在册 + 资产全覆盖 |
| 机制（第四轮收口） | `scripts/check_interop_schemas.py` + `results/interop-schema-validation.md` | **外部权威校验**（非门禁·联网）：openapi / asyncapi / sbom 三面过官方 meta-schema；slsa / intoto / a2a 官方无 JSON Schema → `no-schema` 如实记；prov 本机取不到 → `unavailable`。**外部校验抓出两处真缺陷并修复**：SBOM `created` 缺失（SPDX 2.3 必填）→ 取仓内声明日期最大值（非墙钟）；`documentComment` 不在词表 → 根级 `comment` |
| 测试 | 单测新增 59 例（总 940 例全绿） | 编码卫生 14 / 互操作 18 / 许可表达式 3 / 外部校验工具 5 / JSON-RPC 结构与帧纪律 7 / 文档命令面 3 / 端点幂等 1 / CWE 自洽 3 / 退避重试 3 / 资源模板 2 |

## 四、门禁与验收（实测）

| 判据 | 结果 |
|---|---|
| `bash verify.sh` | **PASS=61 · WARN=0 · FAIL=0**（check1-37 不变——语义全部并入 check33，符合 ADR-0002「门禁不注水」） |
| `python -m unittest discover -s desktop/tests -q` | **940 例全绿**（本波新增 59 例，分布见 §三末行） |
| 本波新模块覆盖率（`coverage` 实测） | `interop_export` 90% · `text_hygiene` 95% · `license_gate` 95%（合计 92%） |
| `python -m ruff check .` · `python -m compileall -q desktop/src scripts` | 零违规（All checks passed） |
| `nf doctor` | 16/16 通过（含「基线自描述一致 v2.27 · check1-37 PASS=61」） |
| `nf conformance` | conformant 27/27（报告已重写并重签） |
| `nf receipts` | 48 件逐条折叠到根，根与实时重算一致（`protocol/RECEIPTS.json` 重签） |
| `nf approve --verify` | 内容绑定批准有效（`protocol/approvals/protocol__conformance_report.json.json` 重批准） |
| `nf interop --check` | 绿（7 面：8 端点 / 43 通道 / 48 subject / 4 包 / 48 SLSA subject / 8 skills / 59 PROV 节点） |
| 编码卫生 | 580 文本件 / 65 JSON / 6634 键 · BOM 0 · CRLF 0 · 违规 0 |
| 文档命令面 | 64 文档 / 167 处命令提及 · 漂移 0（文档面含本波新增的两份对外文档） |

## 五、遗留与不宣称

1. **挂账 6 条**（透明日志 / CycloneDX / W3C VC / C2PA / CID 寻址 / 内容分级）——每条写明触发条件，不排期、不预设；幂等键、CWE 编码、A2A 卡片三条已分别由第二 / 第三轮收掉。
2. **导出面不入仓**：`nf interop` 输出走 stdout 或 `--out`，**不在 `protocol/generated/` 落盘**——落盘会扩张 `protocol/` 登记面（normative / 回执覆盖面）而无消费方；需要归档时由使用者显式 `--out`。
3. **行尾整改只做声明与判据**：未改任何文件内容（逐件 blob 哈希核验）；工作区漂移由 `.gitattributes` 属性在检出层消除。
4. **JSON-RPC 批量请求面**：仍按 `-32600` 拒绝（MCP 不要求批量；本运行时只做单消息），属**已知边界**而非缺口——若将来需要，按 §4 补数组应答语义。
5. **外部实测线仍封存**（STRATEGY §四封闭式发育期）：本波不含任何外部实测；E1/E2/E3 与 B1 通道维持发布后回填口径。
6. **清单数字以内部台账为准**：162 条逐条台账（含每条可相似点）留 `.rivet/private_archive/57_*`，公开仓只承载本件的判定分布与机制结论。
7. **采集面如实记档**：GitHub API 元数据（24 仓）+ RFC Editor 官方索引（8995 条解析，逐编号核对 28 条 RFC 标题）+ 规范原文取样落 `.rivet/private_archive/57_采集回执_GitHub与检索.md`；本轮**检索通道**（DuckDuckGo HTML/Lite、Wikipedia API）在本机网络口径下超时，标准在场性改由 GitHub 元数据与 RFC 原文回执承担——**不把「搜不到」当「不存在」**（见采集回执 §三口径说明）。
8. **退避重试仍是「非门禁工具面」**：外链巡检不进 verify 基线（STRATEGY 的静态可复现红线），重试只提升巡检的定性准确度，不改变门禁口径。
9. **本机网络口径实测（如实记）**：外链巡检 `--fetch` 在**本机**探测 20 条取样 → 失败 11 条，失败集中在 `github.com` / `raw.githubusercontent.com`（`URLError` / `TimeoutError`），而 `api.github.com` 与 `spec.openapis.org` / `rfc-editor.org` 可达——即**本机出口对部分 GitHub 域名不通**，不是链接死了（同一批 URL 在 CI 侧由 weekly workflow 复核）。附带一条自曝：**默认重试（2 次）会让不可达域的探测最坏耗时 ≈ 单条 34s**（10s 超时 ×3 + 退避 1.5/3s），30 条取样本机跑了 9 分钟仍未收口——受限网络下建议 `--retries 0 --timeout 4`（已实测 20 条 77s 收口）。这条写在这里而不是写进工具默认值：**重试是给瞬态故障的**，把默认值调小会削弱它对抖动的价值；取舍交给调用方。
