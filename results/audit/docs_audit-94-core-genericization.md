---
id: AUD-0046
title: 官方核心语义通用化（03/04/05 去叙述、域中立；协议层与门禁同步）
date: 2026-10-13
scope: 作者指令「把管线/模块/资产牵扯到叙述的全部删除，按 NF 定位改成通用，工业级回炉重造」，并确认「语义通用化」方案 A（保留 id、语义通用化）。方法沿用本会话五阶段逆向流程。硬不变量：13 个模块 id、文件路径、事件名、inputs/outputs/interfaces 一律冻结，保 107 社区包依赖闭包不破。机读面逐件等价证明：机器边界逐键相同、contract.schema/pipeline.schema PASS、模块边界签名 digest 不变、world_model slot 仍可寻址。
verdict: pass
auditor: 本轮执行者
subjects:
  - 01_核心协议.md:c41235b97816da38d3a061d85823e60ecc677339e26b261daad2da8551efaf50
  - 02_联动注册表.md:8c4c72367cc196034a7800f668be9e5e82daa1099ee84bd173c09cb1d337c200
  - 06_Agent执行协议.md:5935ac3d9aa38a1eeb495238686877fd61ef8c0ff41a4495a3768974546e03ce
  - 07_官方核心出厂与社区预设导航.md:d958c1f28681f22a3fa99784e906646cf2803372ad6e6896f2f8bc25fb3e9391
  - 03_管线库/P00_通用文档生成管线.md:d02ba569b21ca459a131df465522dc4410585b78dac0412eea16fb10578b348b
  - 03_管线库/P01_标准管线.md:f8548e1c7179b63ab2ce573371e1831c983032be9c6b45214d0d62882b73d1a0
  - 03_管线库/P90_结构装配管线.md:078451643906e9a8a7b16b172b5af8561762258689a3087d3dd82539c30d4090
  - 04_模块库/通用类/M00_数据槽总线.md:a7b8ecab2c1eac96120eb4aae811c1e5b15d2b4c215c2df52a5e6e1fc9118440
  - 04_模块库/通用类/M10_节拍推进.md:5ff248d5843585e5132ae3a6a51c3f600f35cad893c5f8ff55b96d17292f1647
  - 04_模块库/通用类/M23_可见性边界.md:9635fe2d9f74a8f1d7e5060bfac3c44dc3545f81c9de515aae134205bb51f007
  - 04_模块库/通用类/M24_规则组合.md:1e5429032ca392f703c8123da4c4d0877bca0b60e1ad4b73744245a0329bc494
  - 04_模块库/通用类/M50_调度器.md:ddb590f6af181c677caccc39190a5a65b04751e9b0aec4bf5fb5ec27c6a9d524
  - 04_模块库/通用类/M80_输出质检门.md:b2dad838246b0f6287729131cd1aae464843691c1ede95bdcfb412a6eaf2cd48
  - 04_模块库/事件类/M06_流程状态机.md:926b752844c76852e748334522bd79b5fa90ff38bb83a197db1cfea5442e9edc
  - 04_模块库/事件类/M12_模板检索库.md:542679405444e17a41ddd5ed333022be359a1abc3a3311c1af014fe58ca34fed
  - 04_模块库/事件类/M13_实体交互.md:ceb1e8726acff0cd3951f544e2b9db9b045e72f8b9f8af905c31594ec843f368
  - 04_模块库/事件类/M20_知识条目库.md:cbbaf05a888bc6c7a95714f178dc9ffb9a6ecbb07deadf0738f7b7a284ce489e
  - 04_模块库/事件类/M22_事件编排.md:747a7dccdaf506b55ab457c08359f722a7775b1aca8821d92e9afe3e123a11f2
  - 04_模块库/世界类/M08_环境状态.md:3327f91dd0fb83336c45f0b939a3bde9f58ab3630383d5306f646ffc2dfd8a7d
  - 04_模块库/技术文档类/M90_结构装配.md:8e044fc382f526d15cb972fef07b25c358dc3b46e89bb3e659c9a95059de3750
  - 05_资产库/README.md:7f8d241a8e6ce0f2b65a8e37b7708fa260044aec78b44f1efa986f7b57bf49bb
  - 05_资产库/provenance.json:293d3d3dfd1bf25e0fdeaa32e4b14cc817ed974b4209fda45619c65a1473ab93
  - 05_资产库/用户自定义/README.md:03068b5931dba4a0ae92020f9eddcb058bba27a852b0cf9ea015413607374dbf
  - 05_资产库/用户自定义/STYLE_DNA.md:b7ebed51132f13d4f42d6b3e8b6c425a653e947531e5952d65aa49df8e0a4381
  - protocol/asset_keys.json:59d9fcfb03e4da3c21c1b23bc83c2c0518c6e0c94147b3a6aa3915700e2bd33f
  - desktop/src/core/registry.json:cdcb852579785d8817451398021e55441e635a857e0acd3557af9a86b030e7ca
  - verify.sh:5c6a3c1b051bd3b5990e981f56eb7cf31df7b192d34740534f221c3c072c899f

---
> 重审（2026-11-12）：M10 节拍推进顶尖化（outputs 补全为双事件 payload 并集 / io_types 按规则重推 / tick_day 发布订阅对账 / 三形态与 I3·I4 边界）+ 契约判据 test_module_m10_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M00 数据槽总线顶尖化（纯内部基座豁免依据 / 冻结槽位与 world_slots 对账 / 02 §4 依赖对账）+ 契约判据 test_module_m00_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M90 结构装配顶尖化（四形态 / 双声明同源 / P90 八层挂载对账 / fail-closed）+ 去叙述词；机械重绑。

> 重审（2026-11-12）：M90 结构装配顶尖化（四形态口径 / 机读块 ⇄ §2 Module 同源 / P90 八层挂载对账 / fail-closed 边界）+ 契约判据 test_module_m90_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M22 事件编排顶尖化（outputs/payload 补全为 narrative_event 注册字段全集 / 七订阅在册 / inputs 空显式声明 / I3·I4 边界）+ 契约判据 test_module_m22_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M20 知识条目库顶尖化（零事件+query 接口口径 / 双挂载 P70 active + P00 available 同源 / I3·I4 边界 / query 只读）+ 契约判据 test_module_m20_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M13 实体交互顶尖化（outputs/payload 补全为 interaction_update 注册字段全集 / 三形态 / I3·I4 边界 / M12 search 接口引用）+ 契约判据 test_module_m13_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M12 模板检索库顶尖化（零事件模块 interfaces 补全 search / 三形态口径 / I3·I4 只读边界）+ 契约判据 test_module_m12_contract；check12 权重增量重测、模块边界按新契约重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M06 流程状态机顶尖化（机读块 outputs/payload 补全为事件注册表全集 / 三形态口径 / I3·I4 边界 / 事件名在册）+ 契约判据；模块边界签名按新契约重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M08 环境状态模块顶尖化（三形态口径 / I3·I4 边界 / 机读投影口径 / 事件名在册）+ 契约判据 test_module_m08_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：P90 结构装配管线顶尖化（读法/机检 + 02 §7.1 同源）+ 去叙述词；本轮为机械重绑。

> 重审（2026-11-12）：P90 结构装配管线顶尖化（读法/机检段 + 02 §7.1 同源判据 + 空行收口）+ 契约判据 test_pipeline_p90_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：P01 标准管线顶尖化（读法/机检段 + 三处同源判据 + 空行收口）+ 修 P70 optional 与 02/registry 三处漂移；契约判据 test_pipeline_p01_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：P00 管线骨架顶尖化（读法/机检段 + 运行规则空行 + 派生后验收出口）+ 契约判据 test_pipeline_p00_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：07 出厂与预设导航顶尖化（读法段 + 节→机检映射 / 7 处标题空行 / AGENT_START 七段描述同源 / 机制段余量 M99 / §7 九项机检映射 + 状态列口径 / 日期同步）+ 契约判据 test_navigation_doc_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：06 Agent 执行协议顶尖化（读法段 + 节→机检映射 / §10 标题空行 / RFC Date 与最后更新同步）+ 契约判据 test_execution_protocol_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：02 联动注册表顶尖化（读法段 + 节→机检映射 / 7 处标题空行 / 两处跨文件引用精度 / §7 源文切片去 § 形态 / 日期同步）+ 契约判据 test_registry_doc_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：01 核心协议顶尖化（读法段 / 机检映射 / 编号桥 / 引用精度）；RFC Date 与最后更新同步为 2026-11-12。本轮为机械重绑。

> 重审（2026-11-12）：01 核心协议顶尖化（读法段 + 节→机检映射表 / 编号桥 / §引用精度 / 末尾分隔线 / 空行收口）+ 契约判据 test_core_protocol_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-10-24）：CI 并发锁、Gitee 诊断与 ADR-0008 改变 verify/脚本字节；重审理由：相应测试与冻结链已同步

> 重审（2026-10-23）：OTLP ID 判据与合作一致性稳定性修正：traceId/spanId 定长 hex，缺失真源诊断去 OS errno

> 重审（2026-10-22）：CI 三刀合入后重绑（诊断目录绝对化/fetch-tags/wasm skip）

> 重审（2026-10-22）：测试执行器、进程原子与 Windows shell 解析修复后重算代码度量基线与角色投影；既有审计结论不变

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

## 一、做了什么

- **04_模块库 13/13 语义通用化**：M00 数据槽总线 / 通用:M10 节拍推进 / M23 可见性边界 / M24 规则组合 / M50 调度器 / M80 输出质检门 / 事件:M22 事件编排 / M06 流程状态机 / M12 模板检索库 / M13 实体交互 / M20 知识条目库 / M08 环境状态 / M90 结构装配。
- **03_管线库 3/3**：P01 九层名通用化（装载/语境推进/实体状态/内容生产/决策/装配/一致性/素材/输出）；P00 骨架示例去叙述；P90 去叙事表述。
- **05_资产库**：README 改「机制资产 / 域包资产」两分；STYLE_DNA 去文学 DNA、改域中立 profile；provenance 三条 source 去域化；并补 STYLE_DNA 供应链登记（键词表 + 台账 + 文件头）。
- **协议层同步**：01 tags、02 模块表/挂载层名/执行序、06 §4 改可见性四层管线 + §5 改 profile 质检门、07、registry.json 名称三源一致。
- **门禁同步**：verify.sh check4/check5 判据键集随之泛化。
- **派生面重生成**：golden、LSP 逐字节夹具、verification-cards、verify_report、conformance_report、RECEIPTS、receipt_chain、interop×12、自包含样本（library/NF-TECHDOC-* 与 docs/examples/state-front/techdoc_front）与 library 回执。

## 二、验证

- 落定后 `bash verify.sh`：PASS=70 / FAIL=1——唯一失败为**并发会话的新增未跟踪件** `desktop/src/core/workflow_hardening.py`（引用不存在的 `nf verify-report` 子命令），不属本波范围，未改动。
- 本波范围内用例全绿：test_selfcontained_rebuild / test_lsp_transcript / test_audit / test_verification_cards / test_verify_report 共 30 例 OK；conformance 27/27 conformant。
- 12 份 pin 了旧 verify.sh digest 的审计件按仓规「重审并更新 digest」机械重绑（附重审说明），既有结论不变。

## 三、遗留

- 并发会话的 workflow_hardening 相关项由其自身收口。
- 标识符（narrative_event、quest_state、cognition.filter 等）迁移属 Phase 2，未在本次执行。
