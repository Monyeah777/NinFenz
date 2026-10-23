---
id: AUD-0005
title: 作者裁决四项执行 —— 概念图判据面 / 运行时裸号歧义 / 投稿闸门声明化 / 资产货架口径
date: 2026-09-20
scope: 收口四项作者裁决的挂账（均取自本会话外挂账队列）：判据面缺口、命名空间运行时歧义、投稿闸门可见性、资产货架单层口径；四项皆「既有 check 内追加断言」，不新增 check 序号、不改 Schema
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/concept_graph.py:cc629a762576347a6065da4be34ff6c6902ec4ee7299663119abbc153bd50211
  - desktop/src/core/intake.py:23007fd42c627df44dcce7ffa6873a28f5679a68f3b00351f32e728bb25dcbe0
  - desktop/src/core/asset_ledger.py:245d911c417e3d37944a834e0a408ddf33b7491803edd7fe5bfaf132e8f8a6ba
  - scripts/ai_domain_closure.py:431d764da2ef56538eb1c473fe4f45d5ffa8191450638036f147ae7d66a3ae73
  - library/intake.json:e74dda33084b749836de3f8dc3fa83c430b885feec1465b1a94e94aa886d37a8
  - verify.sh:5c6a3c1b051bd3b5990e981f56eb7cf31df7b192d34740534f221c3c072c899f

---
> 重审（2026-10-24）：merge ADR-0008 plus overnight CI evidence and intake quota changes

> 重审（2026-10-24）：CI 并发锁、Gitee 诊断与 ADR-0008 改变 verify/脚本字节；重审理由：相应测试与冻结链已同步

> 重审（2026-10-23）：OTLP ID 判据与合作一致性稳定性修正：traceId/spanId 定长 hex，缺失真源诊断去 OS errno

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

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

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 四项执行的**承重件**（任一件再改，本件结论即失效，须重审）。

> 重审（2026-09-21 · D1-D5 修复波）：`ai_domain_closure.py` 自检样例按资产登记通用化（闭包语义不变）——结论复核不变，subjects 依「重审并更新 digest」处置。

## 一、执行清单（四项 · 逐项给判据与回归）

### ① 概念图内部一致性入判据面（原 AUD-0002 §二 缺口）

| 面 | 落地 |
|---|---|
| 实现 | 新增 `desktop/src/core/concept_graph.py`：**图语义单一实现**（闭包 / 缺失清单 / 就绪清单 frontier / 确定性拓扑 / 违反边 / 别名解析 / 分支映射 + 健康体检 `problems()` + 全仓扫描 `scan()`） |
| 门禁 | 作为**既有 check32 的子扫描**接入（`quality_depth_scan.scan()` 的 `concept_graph` 项）——判据：无环 / 无悬空 / 边有溯源 / 层位合法 / 节点 id 唯一 / 别名唯一 / 分支完备；无图资产**中性通过**（不误伤既有包与用户资产） |
| 同源 | 只读求值器 `scripts/ai_domain_closure.py` 改为 `from core.concept_graph import ...`，不再自带一套算法（门禁与工具同解，杜绝双源漂移） |
| 回归 | `desktop/tests/test_concept_graph_gate.py` 12 例：仓库真源零 issue（47 节点 / 87 边）+ 门禁与求值器同源四断言 + 中性两例 + **七类图缺陷负例**（环 / 悬空 / 重复别名 / 未归支 / 缺溯源 / 节点 id 重复 / 层位越界）+ 缺陷带资产路径前缀 |

### ② 运行时裸号歧义收口（原 AUD-0002 §六 缺口）

| 面 | 落地 |
|---|---|
| 实现 | `verify.sh check14 ⑤` 段内追加三条断言（**不新增 check 序号**）：① 同一裸号不得属两个及以上社区包；② 同包内文件名裸号不得重复；③ 包自有裸号若被官方核心 / 他包占用，则本包管线不得以**裸号**引用（须全限定 `<类别>:Mxx`） |
| 依据 | 运行时模块索引（`pipelinerun._module_files`）以文件名裸号为键、`setdefault` 先到先得——实测战例：`AI系统:M01/M02` 曾把西幻 P03 的裸号引用解析改指本包（advisory 台账可见、门禁全绿） |
| 文档 | `02 §8.3` 增「裸号索引不变量」条（含战例与三条断言） |
| 回归 | `desktop/tests/test_module_namespace.py` 7 → **12 例**（取 check14 **真件**在独立树上跑）：跨包重号 / 同包重复 / 裸号引用歧义三负例 + 「各包裸号互不相同的单包自引」与「改用全限定即清零」两正例对照 |

### ③ 投稿闸门声明化（原 AUD-0004 §三 观察 + AUD-0003 §五 挂账）

| 面 | 落地 |
|---|---|
| 声明面 | 新增机读声明 `library/intake.json`（`schema: nf-intake/1`；通道 `gitee` = `open`、`github` = `author_only`+白名单；`after_action: lifecycle`；每通道带须出现在须知的 `index_label`） |
| 执行面 | 两个入库机器人**运行时读声明**（`library_ingest.load_gate()`，Gitee 机器人复用）：`open` 直投 / `author_only` 校白名单 / **`paused` 一键关闸**；声明不可读即 **fail-closed 暂停**（不静默放行）——闸门从此不再隐藏于代码常量 |
| 判据面 | 新增 `desktop/src/core/intake.py` 做**三方一致**断言（声明 ⇄ `library/INDEX.md` 投稿须知措辞 ⇄ 两个机器人引用声明件），并入**既有 check34** |
| 人读面 | `library/INDEX.md` 投稿须知增「闸门声明（机读真相）」条（通道措辞与声明逐字一致） |
| 回归 | `desktop/tests/test_intake_gate.py` 11 例：仓库真源两通道零 issue + 机器人已接线 + **九类负例**（缺声明 / JSON 坏 / schema 错 / updated 非法 / 缺 after_action / channels 空 / mode 越词表 / author_only 无白名单 / index_label 未出现在须知 / 机器人未引用）+ `paused` 合法开关例 |

### ④ 资产货架口径统一（原 AUD-0004 §三.①）

| 面 | 落地 |
|---|---|
| 实现 | `asset_ledger.verify_shelf_shape()`：货架（`community/*/assets`、`05_资产库/用户自定义`）**不得含子目录**；`verify_root()` 聚合该项（`nf asset verify` 与 **verify check23** 同步生效） |
| 依据 | 三面扫描（密度 / 键表投影 / 行数基线）非递归，台账面 `os.walk` 递归——子目录会造成「台账可见、三面不可见」（静默丢口径） |
| 文档 | `05_资产库/README.md` 增「单层货架不变量」条（含修复指引：分组用键表 / 一包多文件） |
| 回归 | `desktop/tests/test_asset_ledger.py` 15 → **20 例**（单层通过 / 包货架子目录被抓 / 用户货架同样覆盖 / `verify_root` 聚合与 shelves 统计 / 仓库真源四货架实测单层）；2026-10-03 台账扫描面收口时补 **+2 例 ignored-copy 回归**（被 `.gitignore` 覆盖的副本不得被读成第二份货架，含「未忽略的必须读到」反向对照）→ 共 **23 例**，本件被审对象 digest 同步重绑 |

## 二、门禁与验收

| 判据 | 结果 |
|---|---|
| `bash verify.sh` | PASS=61 · WARN=0 · FAIL=0（check1-37 常驻；四项均为**既有 check 内追加**，无新增 check 序号、无 Schema 改动） |
| `python -m unittest discover -s desktop/tests -q` | 全绿（本波新增 28 例：概念图 12 + 裸号 5 + 闸门 11 + 货架 5 减去既有重复计数，见各测试文件） |
| `python -m ruff check .` · `python -m compileall -q desktop/src scripts` | 零违规 |
| `nf pipeline dryrun --all` · `nf score` | 9 条管线零 hard；评分 100.00 无回归 |
| 资产面 | `nf asset verify` 闭合（含新货架不变量）；台账 / 键表投影 / 行数基线三面同步重签 |

## 三、边界与遗留

- 四项**均未新增表达力**（除 ③ 的声明件是新机制面，但其消费方 = 既有两个机器人与其须知，即「有人消费才产」）与**未放宽任何判据**：①②④ 只加判据/不变量，③ 把隐蔽常量变成可机检的三方一致。
- 仍开放（不在本波）：多包组合的裸号跨包引用白名单化（当前以「不得裸号引用」收口）；资产货架若未来需要嵌套分组，需按「表达力扩展」另提裁决（本波守单层不变量）。
