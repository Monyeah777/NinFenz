---
id: AUD-0011
title: 决策层端口（typed-decision 三原语）与 Jev / Laya 候选模型实证
date: 2026-09-22
scope: 作者指令「拉取 jev 或 laya 这种模型作为决策层」——名称实证、契约提炼、端口落地、候选声明与拉取脚手架；本件只对本波落地的决策层机制与声明面作实证建档（不含任何真实模型推理结果）
verdict: pass
auditor: 本轮执行者
subjects:
  - verify.sh:eacd4c758fde0471336c07cb789ebbad39868899cb1cc5cb4eb4d38bf3f5a615
  - protocol/decision_layer.json:9330d4057f07647d67f15daa6f37c84913834b7eed65f4e360bf5c7c413e5e06
  - protocol/normative.json:c1bbc14c92cea6bd66ff6cb54fdcf91bf3072f66adee7027f1d3f42e70fe1825
  - protocol/data_contracts.json:5f04df741065b77993b150f37c0c5c0a7ba3465acbabcca3ee39ac103b578132
  - desktop/src/core/decision_layer.py:b31b67d1feda7bd520aea978e19ab3e165c5524c058c24605e0dc5e800ff1d32
  - desktop/src/core/receipts.py:b0f11db30f4d4b6c0b480ea1657bb8af0f98519523a7ee3e28b7ac8de4c37a69
  - desktop/src/core/doc_hygiene.py:5cc5d9d0fe0bea3f609d26759ac497aeb92363b0c6b045c1ca6cd67687bae850
  - desktop/tests/test_decision_layer.py:551419122f09c1b77f73e7724919f67698bd6d939c3d556d9c8ef98274a76257
  - scripts/nf.py:54c94730f04b3282f37a543f9e1a3f7a502e396963cc07f36d5b3af5da1f61bb
  - scripts/pull_decision_model.py:477a77f3a2d8b0ce6c9e5985a7fd12c4678f7a33fa496d23abb28ab884dc3df1
  - docs/decision-layer.md:cefef53f4a418ccbd7cc1f96a31850454685bcc4d959cabddceea94e1a9c30de

---
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

> 重审（2026-10-26）：Merge W9: gate43-45 + DOCX/DITA importers + PyPI packaging

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

> 重审（2026-10-18）：工具名归一：6 个旧名 -> _list/_search/_read；旧名 alias；官方 tdqs 4.9 两次

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

> 重审（2026-10-14 · 数字资产契约 S 档续）：被审对象随本波改动（protocol/normative.json 并入可移植 schema / CONFORMANCE.md IDL 集 8→9），subjects 依「重审并更新 digest」机械重绑；既有结论不变。

> 重审（2026-10-14 · 数字资产契约 S 档：包自述对账 / Frictionless 导出 / 可移植 schema）：被审对象随本波改动（组合包 INDEX 补登 SYSTEM_CARD 契约 / receipts 锚定面续扩 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / core/layer_model.py 由 nf layers --write 联动刷新职能投影 / code_metrics 基线重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 本波承重件十一件（门禁 / 决策层声明 / 两份登记册 / 端口模块 / 回执覆盖面 / 文档分类表 / 单测 / CLI / 拉取脚手架 / 对外文档）；任一件再改，本件结论即失效须重审。
> **口径**：subjects **不含派生物**——`protocol/RECEIPTS.json` 每次重签都会变，绑进审计只会制造假失效；
> 它由 check35 回执门自证（协议层回执件数 49 在本件正文里作证据引用）。

## 一、名称实证（先求证，不猜）

「jev」「laya」都查到真实模型（HuggingFace API + GitHub 检索实测）：

| 名称 | 落点 | 性质 |
|---|---|---|
| `laya` 系 | `convaiinnovations/laya`（apache-2.0 · ModernBERT-large 421M · 1823 likes）· `laya-multilingual`（mmBERT-base 322M）· **`laya-typed-decisions`**（421M · ctx 1024） | **非自回归 System-1 决策模型族**（typed-decisions / calibrated-decisions / routing 标签） |
| `jev` 系 | `ZefanCai/Open-Jev-9B`（apache-2.0 · Qwen3.5-9B 的 **LoRA + 决策头**）· `com-kotobalabs/open-jev-deberta-v3-large` | 同为 typed-decision，带 `/v1/systemone` 服务口径 |
| 排除 | `mizoreww/laya-mlx`(3972★) 是 MLX 端口；`receptron/laya`(181★) 与决策无关；LayaAir 是游戏引擎 | 与"决策层"无关，不入候选 |

## 二、契约提炼（决定怎么接，而不是抄）

两者共用同一套类型化决策原语（各自模型卡实证）：`choice`（候选集概率 + argmax）/ `noul`（是非概率）/
`score`（有序等级分布 + 期望值）；**非自回归**（只评调用方给的候选、不生成正文）、
**服务不执行动作**、概率以 proper scoring rule 训练（故有 `calibrated` 语义）。

## 三、本波交付

| 类 | 件 | 要点 |
|---|---|---|
| 声明 | `protocol/decision_layer.json` | 三原语 + 应答契约（概率和 ≈1 / 长度对齐 / argmax 在候选集内 / `meta.non_gate`）+ 3 适配器（只有 `stub` 声明 `in_gate_path`）+ 3 候选（含来源/许可/实证/`pulled=false`）+ 5 条边界；**按登记三要件入册**：`normative.json` + `data_contracts.json`（quality_rule=**check33**）+ `receipts.py` 覆盖面（48 → **49 件**） |
| 端口 | `desktop/src/core/decision_layer.py` | 纯标准库：形状校验（请求/应答双向）· 离线确定性 `stub` · `systemone-http`（Jev/Laya 系本地服务）· `openai-json`（聊天模型，`calibrated=false`）· `fingerprint` 可回放 · **任一失败 → `abstained` + reason（fail-closed）** |
| 入口 | `nf decide` | `--dry-run`（面体检）/ `--adapter` / `--endpoint` / `--json`；stub 走门禁口径、外部适配器为非门禁任务 |
| 脚手架 | `scripts/pull_decision_model.py` | 候选/许可/实证可列；**默认只打印 argv（不经 shell）**；`--run --yes` 才下载；缺 `hf` CLI 即 fail-closed 给修复指引 |
| 测试 | `desktop/tests/test_decision_layer.py`（12 例） | 声明完整 / 只有 stub 在门禁路径 / stub 确定性与 `calibrated=false` / 请求形状三负例 / 应答形状四负例（概率和、argmax、漏答、non_gate）/ fail-closed 三路 / 拉取脚手架四条 |
| 文档 | `docs/decision-layer.md` | 入 `doc_hygiene` 三表；含候选实证表与"本机未跑通真实模型"的边界声明 |

## 四、门禁与验收

| 判据 | 结果 |
|---|---|
| `bash verify.sh` | PASS=61 · WARN=0 · FAIL=0（check1-37 不变；决策层面并入 check33 第 15 面） |
| `nf decide --dry-run` | 面体检通过（原语 3 · 适配器 3 · 候选 3 · stub ok） |
| `nf decide --adapter stub` | 三原语各回一条（choice→argmax / noul→p(true) / score→期望值），`calibrated=false` |
| `nf decide --adapter systemone-http`（无 endpoint） | `abstained` + reason ✔ fail-closed |
| `nf receipts` | 协议层回执 **49 件**（新增 decision_layer.json 在册）；`nf conformance` conformant 27/27 |
| 纯度自检（R6） | **本波自查抓掉自己的一处 `subprocess(shell=True)`**（拉取脚手架执行路径）→ 改 argv 列表执行，零 sink 违规 |

## 五、遗留与不宣称

1. **未拉取、未运行任何真实模型**：三个候选 `pulled=false`；本环境不下载数 GB 权重、无 GPU 对照——
   文档与声明**不含任何性能声明**。真实推理结果属外部运行事实，须作者拉取后另立实证。
2. **中文 state 的默认建议**：`laya-multilingual`（322M，100+ 语言）优先于英文专用的
   `laya-typed-decisions`；后者指标更工整但**仅英文**（模型卡自述 specialist、ECE 0.213 过自信）。
3. **`calibrated=true` 不是质量保证**：只表示该系模型以 proper scoring rule 训练；
   用前须在自己的留出集上复核校准（模型卡亦如此建议）。
4. **决策层不进内容生产链**：它只回答被问的类型化问题；正文仍由协议 + 模块 + 资产承担
   （`STRATEGY`「定内容，不定模型」照旧）。
