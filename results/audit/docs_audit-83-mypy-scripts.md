---
id: AUD-0035
title: 类型收敛扩面到 scripts（19 条清零，8 个脚本）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」；承接 AUD-0034（desktop/src 已清零）。开工依据为内部实测（mypy scripts 错误条数 19）。
verdict: pass
auditor: 本轮执行者
subjects:
  - scripts/rebuild_selfcontained_sample.py:51732ee527c918a6ee2effe4236fb3702ceb474ebed4856ea6aa2ee0c059e5d2
  - scripts/fde_sample_run.py:2826c24da2e3a0e771918eb7fdd56a14e57c893ec4ddaa739f56046a97316d6f
  - scripts/serve_decision_model.py:bbb36dff0e3816c2253150b7de6ab619877c3c78269a644c4c966083df15afee
  - scripts/interop_thirdparty_kit.py:803def645cab2f98a6ef27eed82a8463dcc4ed908b7885c9944158771d3d8900
  - scripts/build_verification_cards.py:370f465c17eb18e4ef928194351c759bf33af75e5c1cd5b85abfc2a4b1d39655
  - scripts/geo_export.py:6ff73fdbd8d6ecd7bb6add47c79cba31dfd76c86ae1c7984824ba4e6f28d8eca
  - scripts/nf.py:034e516c46a37b3ed93e26cc197ee51e785c5453d08e4ef2d403204971c309e5
  - scripts/check_external_links.py:1cbee65ba19a83fbcdf333e35b8d99c2e45f3b400f3a025860357baf7a806b02
  - protocol/code_metrics_baseline.json:fa5b451c33c2d10f74490dc5113b2e5d9444096040dd658a6c652f66ee9355d0
---
> 重审（2026-11-08）：terminal 族登记 cog + 终端投影刷新 + CRLF 归一

> 重审（2026-11-08）：SAST 修净（token 常量改名 / 去 except-pass）

> 重审（2026-11-08）：Ingress 网关（认证/白名单/限流/同意/回执）

> 重审（2026-11-08）：工具清单派生自真实 TOOL_DEFS（D-04 关账）

> 重审（2026-11-08）：预注册评测协议 + harness（D-05 关账，新增 D-06 真实测量债）

> 重审（2026-11-08）：闭包台账（21 条断言 → 真实判据 → 反例 → 状态）+ 审计脚本

> 重审（2026-11-08）：K1 作业账本 + K4 事件流 + K8 启动自检（P6 第二件）

> 重审（2026-11-08）：MCP 兼容头（工具清单 _meta 增强 + 签名钉根 + 吊销 + 调用回执）

> 重审（2026-11-08）：ADR 注册表 + 16 份文档台账 + 分层依赖判据（P0 补账）

> 重审（2026-11-08）：双核桥（commitment + 回灌 + 闭环）

> 重审（2026-11-08）：原子目录 v2 + 不变量 A1–A5 + 候选健康 B1–B5

> 重审（2026-11-08）：判据注册表 + 主张编译（证据义务清单/三态核对）

> 重审（2026-11-08）：元算子层（11 ops + 触发引擎 + 双 trace + 反仪式化）

> 重审（2026-11-08）：认知工作台 L0（discourse/15 moves/records/replay + nf cog）

> 重审（2026-11-08）：几何提示同步探针（尺寸反解 + 双假设 + 偏移搜索；谱峰不变反例）

> 重审（2026-11-08）：同步层探针（同步字平铺 + 网格搜索，负结果可复算）

> 重审（2026-11-08）：DCT 水印探针（QIM vs 关系嵌入，q70/q50 实测）

> 重审（2026-11-08）：密钥透明目录 v0（版本根/追加链/包含证明/分叉见证）

> 重审（2026-11-08）：水印基准收口（纯度为软导入）

> 重审（2026-11-08）：水印鲁棒性基准（16 攻击 × BER）+ 文档实测表

> 重审（2026-11-07）：方法包 v0 收尾（风格/度量重冻）

> 重审（2026-11-07）：方法包 v0（3 个领域包 + 组合 + 研究计划接线）

> 重审（2026-11-07）：认知核研究层：方法库 + 切片计划器 + CLI（切片检索词/方法论路径/证据台账）

> 重审（2026-11-07）：向量面收口：三形态跨实现同判 + 信封 subject 三摘要面

> 重审（2026-11-07）：命令树拆分（production 321→117 行 + 新组 evidence_face 207 行）

> 重审（2026-11-07）：门禁修：silent-skip 理由 / 两个文本参数登记 / --mode 复核

> 重审（2026-11-07）：纯度修：去掉 __import__，改正常 import

> 重审（2026-11-07）：Go 客户端补齐 cc_check/cc_label/cc_attest/cc_replay/cc_diff/cc_resolve（6 份向量集）

> 重审（2026-11-07）：Go 客户端补 receipts/attest 两形态；向量集扩到 28 条（三形态）

> 重审（2026-11-07）：cc_check 文本层：法规原文→意图草稿（规则抽取，四张账）

> 重审（2026-11-07）：吊销公钥信任锚（钉根 + 有界委派 + 过期/scope/链深判据）

> 重审（2026-11-07）：载体层：WebP/MP4/PDF 附加块 + PNG 像素水印；Pillow 软依赖登记

> 重审（2026-11-07）：载体层：WebP/MP4/PDF 附加块 + PNG 像素水印（判据含 JPEG 不扛的期望行为）

> 重审（2026-11-07）：RFC 3161 可信时间戳（timestamp 模块 + CLI + 证据复验时间锚）

> 重审（2026-11-07）：快照落点纯函数化 + 3 条隔离判据（同盘/出树/日志）

> 重审（2026-11-07）：revocations_seed 进二进制豁免 + 两份文档项数同步（62→65 / 34→43）

> 重审（2026-11-07）：G3 诚实闭环：time_proof/time_basis + 显式 warning

> 重审（2026-11-07）：ed25519 吊销签名（非对称：验证方只持公钥）+ 回归判据

> 重审（2026-11-07）：度量重冻（nf.py +1 行：登记面修正）

> 重审（2026-11-07）：batch_target 登记修正（位置参数进文本面，不进旗标名单）

> 重审（2026-11-07）：度量重冻（nf.py +3 行：batch 派发）

> 重审（2026-11-07）：nf evidence batch（目录逐件复验，整批不可用即失败）

> 重审（2026-11-07）：verification_report 记 built_for_date（涉时判据按基准日重算）

> 重审（2026-11-07）：instruction_evidence 临近过期提前 7 天 WARN + 重录 verify/release

> 重审（2026-11-06）：快照清理站点补成文理由 + 文档项数 47→51

> 重审（2026-11-06）：快照日志/清理收口（重绑）

> 重审（2026-11-06）：快照模式：内层日志边跑边落盘 + 陈旧快照自动清理

> 重审（2026-11-06）：sink 基线 21→22（并发会话新增快照 run 目录清理站点）+ keep-snapshot 旗标

> 重审（2026-11-06）：快照临时目录隔离 + 文档项数（release_conclusion/docs 变更）

> 重审（2026-11-06）：机器面 NF_HOME 可移植（nf.py 变更）

> 重审（2026-11-06）：bash 身份守卫（WSL 空输出不再冒充判据红）+ Windows 两坑入文档

> 重审（2026-11-06）：CLI 命令树拆分 + 旗标字面读取（nf.py 变更）

> 重审（2026-11-06）：FRESH 词表接线（evidence.py 变更）

> 重审（2026-11-06）：task-27 吊销新鲜度：revocations/evidence/nf.py 变更，重绑被审对象

> 重审（2026-11-06）：快照内层独立 NF_HOME + 读点改 json_doc

> 重审（2026-11-06）：快照内只判 HEAD（脏树信号仅用于活树）+ 取消不崩

> 重审（2026-11-06）：快照落点改仓库同盘 + TEMP 重定向（防满盘 ENOSPC）

> 重审（2026-11-06）：纯度放行表扩容后度量基线重冻

> 重审（2026-11-06）：发布结论器加 --snapshot（HEAD 快照里跑，免疫并发改动）

> 重审（2026-11-06）：release_conclusion P2 修复：allow-dirty 与分片 drift 守卫兼容，度量重冻后重绑

> 重审（2026-11-06）：并发会话遗留的派生面重冻（中途哨兵入库）

> 重审（2026-11-06）：JPEG 载体 P0 硬化（nf.py/CLI 文案变化）+ 口径清理，重绑被审对象

> 重审（2026-11-06）：JPEG APP15 载体（扫描数据不变）+ 真 PNG 夹具判据

> 重审（2026-11-06）：Q0-r2：evidence verify 增 --policy-digest 期望比对（nf.py 参数面变化），重绑被审对象

> 重审（2026-11-06）：耦合面重冻（载体模块行数变化后 metrics 面漂移）

> 重审（2026-11-06）：载体 IR 读点改走 core.json_doc（未校验读点棘轮）

> 重审（2026-11-06）：cc_label PNG iTXt 载体（可读回/不改像素/CRC 合法）

> 重审（2026-11-06）：常驻集加 test_cli_error_framing（参数登记面 100 s 换 36 分钟）

> 重审（2026-11-06）：注册 --decision 参数进编码/路径闸门（其提交遗漏）

> 重审（2026-11-05）：Q0 决策证据绑定：scripts/nf.py 增 --decision 入口、evidence/attest/nf_verify 增 decision 绑定，重绑被审对象摘要

> 重审（2026-11-05）：发布结论器新增静态棘轮步（style/度量/耦合/SAST，约 12 s）

> 重审（2026-11-05）：攻击矩阵重名用例：构造期抑制 zipfile 重名 UserWarning（机器面逐字节一致）

> 重审（2026-11-05）：并发会话风格债收口（6 处 E501/RUF100/UP031/UP012 修掉，style 基线 9923→9921）

> 重审（2026-11-05）：容器面加固：路径安全闸门 / 重名判死 / 解压上限（攻击矩阵 33→35）

> 重审（2026-11-05）：label_sidecar 删零引用 helper（死代码判据）

> 重审（2026-11-05）：cc_label sidecar 回退（nf-label-sidecar/1，绑定对象摘要）

> 重审（2026-11-05）：隔离静态判据（打桩面）+ 三个机器判据进常驻集

> 重审（2026-11-05）：证据判定向量集（跨语言一致性锚点）+ 文档

> 重审（2026-11-05）：http_api 行数上限重冻 266→267

> 重审（2026-11-05）：HTTP 403 分支补 drain（回 4xx 前先读掉请求体）

> 重审（2026-11-05）：--compile 参数登记进编码/路径闸门

> 重审（2026-11-05）：cc_check 编译面 v0：意图 → 封闭词表策略（不可表达逐条挂账）

> 重审（2026-11-05）：发布结论器新增新鲜度步（行数上限随之重冻 328→365）

> 重审（2026-11-05）：受影响选片 v2（四类规则 + 文档目录前缀 + 硬兜底面）+ 纯函数判据

> 重审（2026-11-05）：G2 吊销分发件（签名 feed：签发/校验/合并，防回滚）+ nf.py 导入块排序

> 重审（2026-11-05）：label 声明层补登记（编码闸门/路径旗标）+ 删零引用函数

> 重审（2026-11-05）：cc_label 声明层（nf-label/1 IR）+ 供应链核对进发布结论

> 重审（2026-11-05）：G1 外部锚点：证据包可声明并可核对（防整链截断），双实现同口径 + 攻击矩阵 33 条

> 重审（2026-11-05）：威胁模型 v0（能证明/不承诺/缺口）+ 发布结论前置 payload 闸门 + 站点 npm 数字自动改写

> 重审（2026-11-04）：发布结论器：分区与并发分离（缺省 8 片顺序跑）+ 根 llms-full 同步（站点数字口径）

> 重审（2026-11-04）：发布结论器：失败分片留输出尾部（诊断可复现）

> 重审（2026-11-04）：发布结论器改用受控进程原子（不再自起 subprocess）+ 缺省串行

> 重审（2026-11-04）：发布结论器：SAST nosec 标注 + 缺省改串行（并发只给独立 runner）

> 重审（2026-11-04）：H1 修复：--trust-repo 环境变量不再泄漏（信任门不再被绕过）+ 新增回归判据

> 重审（2026-11-04）：发布结论复跑器（release_conclusion）+ 文档落地

> 重审（2026-11-04）：分片 1/8 抽检修复：编码闸门/路径旗标名单补全、删零引用常量与函数、耦合基线重冻

> 重审（2026-11-04）：零依赖复验器同步 fail-closed 口径（chain 必填 / 吊销坏件）+ 一致性判据补三例

> 重审（2026-11-04）：证据线 fail-closed 加固：chain 段必填 / 吊销表坏件判 invalid（攻击矩阵 25→29）

> 重审（2026-11-04）：抽检第二个分片：原子写纪律（包/报告走 atomic_write，临时写例外登记）

> 重审（2026-11-04）：check12 修复波：JSON 面登记 / json_doc 收敛 / Rust 回执去重同步 / 基准 JSON 纯净

> 重审（2026-11-04）：本地工作台页（/verify 静态页 + CSP）落地

> 重审（2026-11-04）：code_metrics 基线重冻后重绑（HTTP 面 raise 文案微调）

> 重审（2026-11-04）：本地 HTTP 面 v0（nf serve --http 三端点）落地 + 端点契约登记 local.*

> 重审（2026-11-04）：cc_resolve（契约面反查）+ 一条链复现脚本落地

> 重审（2026-11-04）：cc_replay 轨迹 + cc_check 单对象策略体检落地（新模块 check_policy）+ 回执去重

> 重审（2026-11-04）：零依赖单文件复验器（--evidence 三形态）落地 + 风格基线重冻

> 重审（2026-11-04）：code_metrics 基线重冻后重绑审计摘要（证据复验器扩形态与基准）

> 重审（2026-11-04）：证据复验器扩三种形态 + 攻击矩阵基准（26 项校验路径与基准落地）

> 重审（2026-11-04）：证据包缺省落点改到临时目录（不往仓库落盘）+ CCOS ABI v0 收口

> 重审（2026-11-04）：CCOS ABI v0 + 证据包校验器落地（scripts/nf.py 与 core/terminal.py 摘要变更；并修复本分支既有漂移）

> 重审（2026-10-30）：新增契约级 Git 演进时间线；结构化 Markdown YAML 字段与 JSON schema 差异纳入影响度

> 重审（2026-10-30）：全仓审计口径复核：显式 legacy 清单、subjects 根内解析、Path 参数闸门、惰性导入与 manifest 可复算

> 重审（2026-10-29）：CLI 命令树无损分组、meta-cockpit 接线与恢复分支全量验证后重绑；既有结论不变

> 重审（2026-10-29）：恢复分支全量验证：纯度修复、零引用清理、public API 接线、ReDoS/CLI 闸门/文档路径与模板示例修复

> 重审（2026-10-29）：恢复分支全量验证：接线 meta-cockpit 公共模块、清理零引用、修复 ReDoS/CLI 闸门/公开文档路径后重绑；既有结论不变

> 重审（2026-10-25）：决策/交接/复盘外置：公开面只留模板（ADR-0000）

> 重审（2026-10-25）：D1 常量时间比较 + N2/L2 发布面白名单化

> 重审（2026-10-25）：跨平台收口：真实路径归一、守护状态读写锁、autostart 原子标记与机器路径短名脱敏

> 重审（2026-10-24）：CI 收口：修复 workflow cargo 版本探测、补齐 Rust parity 的 Python 固定依赖、移除 Rust 死代码，并扩展报告临时根脱敏覆盖。

> 重审（2026-10-24）：CI 跨平台稳定性修复：角色投影只认 Git 跟踪面、报告路径脱敏、ReDoS 负例与 GUIDANCE 豁免判据同步，重审当前测试与门禁对象。

> 重审（2026-10-24）：夜间收口：Rust worker 安全、投稿配额、元数据、schema 与 postmortem 跨平台回执路径修复后按新输入重绑

> 重审（2026-10-24）：夜间收口：Rust worker 安全、投稿配额、元数据与 schema 修复后按新输入重绑

> 重审（2026-10-24）：2026-10-24 投稿写面收口：Gitee 改为作者白名单，加入日配额与跨平台空目录占位，重绑投影响应文件

> 重审（2026-10-24）：DOC-004 收口：协议回执纳入 closed 复盘件，修复 closed 状态无法满足锚定判据的循环

> 重审（2026-10-23）：A2 同族修复：gate_observe 盘符/UNC 判仓外

> 重审（2026-10-23）：A 类跨平台修复（尾点占位/盘符路径）后重绑

> 重审（2026-10-23）：完整性锚点去缓存：批准与产物清单直接分块哈希，修复同 mtime/size 陈旧假命中

> 重审（2026-10-23）：终局稳定性：原子写 sink 收敛、测试隔离修复、验证卡册与 payload 重签

> 重审（2026-10-23）：I/O/内存/IPC 审计整改最终重绑：索引池、持久 IPC、原生绑定、缓存预算、OTLP 与协议防护

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护；最终生成链重绑

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

> 重审（2026-10-23）：Rust 快线加速收口：新增常驻 worker / PyO3 原语 / Rayon 解析并行与 code_metrics 接线；被审判据语义未变，digest 随实现同步

> 重审（2026-10-22）：H1：nf verify 仓库信任门（重冻）

> 重审（2026-10-22）：C1：判据缓存移出仓库（用户级+回退标记）（重冻·修订）

> 重审（2026-10-22）：C1：判据缓存移出仓库（用户级+回退标记）（重冻）

> 重审（2026-10-22）：S1：scratch GC 只删 nf-<12hex> + 根标记（重冻）

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

> 重审（2026-10-19）：nf.py 会话落点放行 .rivet（受限环境唯一可写临时区）

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

> 重审（2026-10-18）：Glama coherence：收紧 spec_ls/registry_query 描述边界；asset_get 说明为协议资产五接口规范名

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

> 重审（2026-10-14）：引入 nf audit rebind 命令（core/audit.py + CLI + 顺序纪律 + 两处面收敛）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI + 顺序纪律）：重审并更新 digest 机器化

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI）：重审并更新 digest 口径机器化，替换手搓脚本

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
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因 4 个脚本行数或圈复杂度增长按工具指引重冻。

## 一、结果

`python -m mypy scripts --ignore-missing-imports` 错误条数 **19 → 0**。

## 二、交付

| 脚本 | 修法 |
|---|---|
| `scripts/nf.py` | ① `argparse._`/`ngettext` 两处**有意猴补**补 `# type: ignore[attr-defined(,assignment)]`（原 ignore 只盖 assignment）；② daemon bench 的 `rows` 显式 `List[Dict[str, Any]]`；③ `signal.SIGPIPE` 改 `getattr(..., None)` 判空（Windows 无该信号，原靠 except 兜住，行为等价） |
| `scripts/check_external_links.py` | `breaker` 参数如实标 `Optional[DomainBreaker]`（函数内已 `breaker=None 即不熔断`）；报告接收端显式 `Dict[str, Any]`——7 条一并消 |
| `scripts/rebuild_selfcontained_sample.py` | 标记行改为显式循环取 `group`（消 `Match\\|None`）；管线段收尾围栏变量 `cl`→`close_idx`（与上文同名变量解耦） |
| `scripts/fde_sample_run.py` | `module_from_spec` 前补 `spec is None` 守卫（带修复指引） |
| `scripts/serve_decision_model.py` | 进程内单例 `AGENT: Any = None`（加载前恒为 None，`predict` 前由 500 兜底） |
| `scripts/interop_thirdparty_kit.py` | 循环变量 `e`→`ent`（避开同函数 `except ... as e` 的变量删除语义） |
| `scripts/build_verification_cards.py` | 基线两处 `re.search` 结果判空（缺常量即带修复指引退出） |
| `scripts/geo_export.py` | 绑定行显式 `List[Dict[str, Any]]` 后再排序（消 `object` 算术） |

## 三、验收证据（本机实测）

- `mypy scripts` 错误条数 **19 → 0**。
- `python -m unittest`（本批相关 4 组）→ **65 例全绿**。
- `python scripts/code_metrics.py` → 4 脚本按工具指引重冻。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. `desktop/tests` 仍有 66 条 mypy（测试面，未纳入本线）；radon 复杂度仍为存量。
2. `nf.py` 的两处 `# type: ignore` 是**猴补 stdlib** 的必要逃生口（模块级补丁，typeshed 不可能知道）；已在**紧邻注释**里写明短路理由，不建豁免表。
3. 62 §三·② 余量与 §二·2 .NET 重冻不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑ | `scripts` mypy 归零；65 例单测 + 全量 verify 双绿 |
| 动态可执行 | → | 两处守卫收窄到原路径，信号分支语义等价 |
| 架构纯度 | → | 只改类型标注/取值方式 |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
