---
id: AUD-0023
title: 出口自动化四路落地 —— 自述数字实算 / 他证通道 / 标准目录 GEO 出口 / FDE 中游打样
date: 2026-09-24
scope: 作者指令「自述数字自动化，互操作性从他证，标准目录做 GEO 出口，FDE 打样」（定位澄清：不是作者去做 FDE，而是让 NF 成为 FDE 的 AI infra 中游标准）。四路均为「结果态入公开仓库」；计划/过程留本地档案（STRATEGY §四）。他证一律只建通道、不主动外联（外部实测线维持封存）。
verdict: pass
auditor: 本轮执行者
subjects:
  - verify.sh:d724f3a0a8ccde43ded229085dc5e3d985ec9d5f069ee298d815000743fad542
  - scripts/nf.py:6a2a931b373487d2aac503b295a2db3cfa579eb46ae8856b41f5d3401da7ca37
  - desktop/src/core/repo_stats.py:3bc955c22bef31d7b93313b4fe2694934c048e8ee84b9ef81c0e9805c7982a87
  - desktop/src/core/quality_baseline.py:7c1f06bc581a2400b1248df63e07a98dfffba2b92ca8070a71082abcc317d1e4
  - scripts/interop_thirdparty_kit.py:803def645cab2f98a6ef27eed82a8463dcc4ed908b7885c9944158771d3d8900
  - scripts/geo_export.py:6ff73fdbd8d6ecd7bb6add47c79cba31dfd76c86ae1c7984824ba4e6f28d8eca
  - scripts/fde_sample_run.py:2826c24da2e3a0e771918eb7fdd56a14e57c893ec4ddaa739f56046a97316d6f
  - protocol/CONFORMANCE.md:006b56748b6daaf2419be40a65247d90efd6291e87ccd61c6527ed1526b6b4e4
  - docs/fde-stack.md:79633a484dcf01cd92c03deac96d7b59f85489c1aa0ec4ad5489768d2702da8a
  - docs/fde-sample/README.md:c17984ad90f50d39131fd932c37915b978e28bf606f9c397128de1c8417e4168
  - docs/interop-thirdparty.md:637dff4598a4b8ff21f81090c20b625269cea49903d396a3fc2968f2f1e1f2fc
  - results/interop-thirdparty-status.md:e57c95980dd8b36bf137d23db0cf3c93ba8aee5221d2d26f2a6c782c30df0469

---
> 重审（2026-10-30）：2026-10-30: 1.1.2 版本面与发布事实同步；README 与机器事实更新，重审对象摘要变更。

> 重审（2026-10-30）：refreeze.sh（统一冻结入口）

> 重审（2026-10-28）：默认并行度 10→14

> 重审（2026-10-28）：nf verify 判据并行（heredoc→子进程，3.5×）

> 重审（2026-10-28）：tests-only 默认并行度 8→10（实测 285 s 拐点）

> 重审（2026-10-28）：D 第一刀：paths realpath 去重 + text_hygiene 二进制读取走 scan_memo + --pr 档

> 重审（2026-10-28）：tests-only 默认 8 片 + PermissionError 退避重试

> 重审（2026-10-27）：verify.sh: checks 档缓存 put/get 一致（mode=checks）

> 重审（2026-10-27）：checks-only 独立档位缓存（verify_cache mode=checks）

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


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物：`protocol/repo_stats.json`、`docs/standards/*`、`protocol/geo_export.json`、
> `docs/fde-sample/evidence/*` 均为可复算投影（由脚本重跑逐字节可还原），按口径不入审计绑定。

## 一、内部差距（开工依据）

四路各来自本轮审计（`NFAudit_Checklist_v2` 执行轮）的实证缺口，不是外部比附：

1. **自述数字漂移**：README 长期写「48 模块 · 10 管线 · 7 社区包 · 60 资产档/326 键 · 概念图 2」，
   盘上实况是 **13 官方核心模块 / 3 官方管线 / 111 登记包 / 363 资产档 / 101 概念图**——公开面数字与
   实物相差一个时代，且多处文档重复手写同一组数字（改一处漏三处）。
2. **互操作只有自证**：`results/interop-schema-validation.md` 是「上游 meta-schema 判据校验」，
   但「兼容 X」缺 X 侧消费证据（D13.5 判 FAIL）；且没有任何第三方可自跑的成套入口。
3. **标准目录只有机读真源、没有可引用面**：370 条标准 + 1200 绑定在 `protocol/*.json` 里，
   生成式引擎无从引用（缺稳定锚、按问题聚合的卡片、紧凑机读面）。
4. **中游位置无成文契约**：NF 的装载/装配/门禁/证据/互操作/标准绑定六件事真实存在，
   但没有一份写给 FDE 的栈位说明，也没有一次「brief → 装配 → 门禁 → 证据包」的可跑样例。

## 二、落地件（四路）

| 路 | 落地件 | 关键判据 |
|---|---|---|
| 自述数字实算 | `core/repo_stats.py` · `nf stats --write/--check` · `protocol/repo_stats.json` | 数字全部来自产物；README/README.en/llms.txt 的 marker 生成区与实算逐字节一致 |
| 他证通道 | `scripts/interop_thirdparty_kit.py`（`--emit/--check/--dry-run`）· `docs/interop-thirdparty.md` · `results/interop-thirdparty-status.md` | 14 面各一张卡；回填六字段齐备才算他证；未回填即「通道就绪」；not-applicable 必须写理由 |
| GEO 出口 | `scripts/geo_export.py` · `docs/standards/index.md` + 五分层 + `answer-cards.md` · `protocol/geo_export.json` | 生成物与目录真源逐字节一致；锚点集合 == 目录 id 集合；不可达 38 条逐条披露 |
| FDE 打样 | `docs/fde-stack.md` · `docs/fde-sample/`（brief/run/evidence）· `scripts/fde_sample_run.py` | 五门 G1–G5 全绿；`--check` 逐字节比对证据与当前仓库状态 |

**门禁与基线**：新增 `check38`（四子扫描），`verify.sh` v2.27 → **v2.28**，
`quality_baseline.EXPECTED_*` 同步为 **check1-38 · PASS=66**；
当前态文档（README / ROADMAP / community README / verification-cards / CONFORMANCE 声明）
中手写的旧基线改为指向生成区与真源；CHANGELOG / 历史迁移记录 / VERSION-MATRIX 历史行不改写。

## 三、实测证据

| 项 | 实测 |
|---|---|
| 自述数字 | 13 模块 · 3 管线 · 111 登记包 · 363 资产档 · 101 概念图 · 100 域包/1200 细分 · 370 标准（可达 332 / 不可达 38 / 机构 194 / 206 边） · 1200 绑定 · 馆藏 3 |
| 他证通道 dry-run | 14 面全部产出状态；`cid` 面**抓出真实漂移**：49 条已知向量中 1 条（llms.txt）摘要过期 → 重签回执后归零 |
| GEO 出口 | 8 件生成物（index 81,749 B / 五分层 / answer-cards 7,282 B / geo_export.json 178,442 B）；370 条锚点全对齐 |
| FDE 样例 | G1 声明面 6 · G2 schema↔data 2 对 · G3 概念图 48 节点（拓扑序 47 · 证据强度 external） · G4 装配链 4 件 · G5 出口双绿 |
| 全量门禁（本波件） | `bash verify.sh` → **check1–check38 全部 PASS**；`check38` 四子扫描全绿（自述数字 / 他证通道 / GEO 出口 / FDE 样例）。**唯一残余 FAIL = check35「一致性报告 verdict」**，成因与处置见 §四·4（并发会话在写同一工作区） |

## 四、连带收口（本轮暴露并修掉的三处）

1. **审计片摘要过期**：本波改动触及 `verify.sh` / `scripts/nf.py` / `llms.txt` / `README.en.md` 等
   被审对象 → 14 件历史审计片共 **20 条摘要**按判据重绑（只换 digest，不改结论、日期与签收）。
2. **一致性报告失配**：重绑前 `audit` 契约判 `non-conformant`（26/27）→ 重绑后重跑
   `nf conformance --write` 回到 **27/27 conformant**。
3. **FDE 证据文件触发文本卫生判据**：样例证据 `manifest.json` 的键曾用 Windows 反斜杠
   （U+005C，越出标识面允许字符集）→ 改为 POSIX 分隔符后 `test_text_hygiene` 归零。
4. **并发会话竞态（如实记，非本波缺陷）**：本仓库同期存在另一会话的改动（`.github/workflows/*`、
   `.github/scripts/*`、`desktop/src/core/{purity_scan,paths,asset_ledger}.py`、
   `scripts/serve_decision_model.py`、`CONTRIBUTING.md` 等）。审计判据「被审对象已变 → 旧审计失效」
   会在**对方每次落笔**时把 `audit` 契约打红（实测连续三轮：`llms.txt` → `external-links.yml` →
   `CONTRIBUTING.md`/`asset_ledger.py`）。本波的处置：把摘要按当前字节重绑（机械、非破坏）并重跑
   `nf conformance --write` → `nf receipts --write`（顺序不可颠倒：一致性报告在回执覆盖面内）。
   **稳定绿的收口动作**（待对方停笔后执行一次即可）：

   ```bash
   python <本波重绑工具>            # 或按判据逐条重绑被审对象 digest
   python scripts/nf.py conformance --write
   python scripts/nf.py receipts --write
   bash verify.sh                   # 期望：PASS=66 · WARN=0 · FAIL=0
   ```

## 五、边界与挂账（如实记）

- **他证已执行（作者指令「执行」）**：用**第三方官方实现**在本机实跑 14 面 → **7 PASS · 6 不适用 · 1 未回填**：
  ① `openapi` openapi-spec-validator：**先 FAIL 后 PASS**（见 §六）；② `asyncapi` @asyncapi/cli：
  **先 443 error 后 0 error**（见 §六）；③ `sbom` spdx-tools：通过；④ `cyclonedx` 官方库内置
  bom-1.5 schema + jsonschema（本地解析 spdx 引用）：通过；⑤ `cid` 已知向量独立复算 49/49 一致；
  ⑥ `prov` pyld 上下文可展开；⑦ `mcp` **官方 MCP Inspector** 对 `nf serve` 消费 `tools/list` ·
  `resources/list` · `prompts/list` 三方法全部成功。**不适用 6 面**：`slsa`（slsa-verifier 需 go/docker，
  本机不可得）、`intoto`（in-toto 3.1 面向 DSSE envelope，无 statement 级校验入口）、`vc`（离线取不到
  `w3.org/ns/credentials/v2` 上下文）、`a2a`/`c2pa`/`decisions`（本仓无对端对象）。**未回填 1 面**：
  `ccv3`——需要 SillyTavern 等对端应用，本机无该环境。**外部联系仍为零**（工具为第三方实现，运行者为本机会话，
  已在状态表 `run_by` 如实标注）。

## 六、他证抓出并修掉的两个真缺陷（本轮新增）

| # | 面 | 官方判据原文 | 根因 | 修法 | 复验 |
|---|---|---|---|---|---|
| 1 | openapi | `Path parameter 'id' for 'get' operation in '/library/{id}' was not resolved` | `interop_export.openapi_doc` 只派生 operation 本体，从不派生路径参数 | 由路径模板派生 `parameters`（`in: path`、`required: true`、`schema: string`，带 `x-nf-derived` 注记） | openapi-spec-validator **OK（退出码 0）** |
| 2 | asyncapi | 443 条 `invalid-ref: '#/channels/nf/xxx' does not exist` | 通道键写作 `nf/<事件名>`，而 JSON Pointer 未转义（`/` 必须写 `~1`） | 新增 `_ptr()`（RFC 6901：`~`→`~0`、`/`→`~1`）并用于通道/消息 `$ref` | @asyncapi/cli **0 error**（仅信息级：官方建议 3.1） |

> 这两个缺陷此前未被发现，是因为仓库既有层只做**上游 meta-schema 校验**（校验文档“形状”的元 schema），
> 不校验**实例内部一致性**（路径参数、引用可达）。这正是「他证 ≠ 自证」的实证价值。
- **运行时计数不入文档**：运行 PASS 计数的**期望值**是真源声明（`quality_baseline.EXPECTED_*`），
  由生成器写入入口文件；正文不再散落手写数字。
- **ISO/IEEE 正式文本仍未取得**（见审计执行轮 §8.4）：ISO 官方页为 Cloudflare 挑战，IEEE 仅摘要。
- **本波不新增真源**：四路全部从既有产物派生（`RECEIPTS.json` / `standards_catalog.json` /
  域包 outputs），无平行真相。
