---
id: AUD-0024
title: NF 终端落地（nf shell）—— 端壳退役后的人机入口 + 端壳残留门禁（check39）
date: 2026-09-25
scope: 作者指令「删除 NF 中的 GUI，且为 NF 构建一个终端（CLI 开发）」。GUI 端壳源码/入口/打包线/CI 已于 2026-09-09 永久退役移出；本轮 = 退役状态复核并机制化（新增 check39 端壳零回潮）+ 终端入口落地（nf shell，纯 stdlib）。公开面只入结果态（代码 + 门禁 + 文档 + 本审计）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/terminal.py:3e5b107dfc1a068325282a63a68112113e53a61c43f21c8cb52f4c4f731695d5
  - scripts/nf.py:25f9dde23bec1b41ca67cebfad6e9e615f96ffc25da00fbc856c5803d2ae5d19
  - desktop/tests/test_terminal.py:46a1b762320c65f0cf3bf984f3bbf66990f649278e5caac9e1e71453c35f7ae1
  - scripts/nf:5e09824dc5c31ccdf7aaa70f7bf15720f3a6ac902adea6b754ed29f85e4fd53c
  - scripts/nf.cmd:d1e7ea3a9e99c0822102884cddafe1cdf3893d9b75d19abebe7a8d2a8abeec5a
  - verify.sh:c2cd98816cc9021703e25899899b256d3f6b98a9a0524b6e62154f14efddf9bf
  - desktop/src/core/quality_baseline.py:7c1f06bc581a2400b1248df63e07a98dfffba2b92ca8070a71082abcc317d1e4
  - desktop/src/core/doc_hygiene.py:5cc5d9d0fe0bea3f609d26759ac497aeb92363b0c6b045c1ca6cd67687bae850
  - docs/terminal.md:b08d721ed527baa92d4cdf56f73aa4972c1314159c3213ed38a95911c2b7f71b
  - docs/L3_FROZEN.md:9dad824e749aac75ee4cf583adb48d0ede9c02a0a717ff43d314cbbfcb3cf3af
  - protocol/CONFORMANCE.md:006b56748b6daaf2419be40a65247d90efd6291e87ccd61c6527ed1526b6b4e4

---
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

> 重审（2026-10-14 · 终端基线并发与 argv 唯一性）：被审对象随本轮改动（`baseline_tmp_dir()` 改为按进程唯一；`baseline_argv_issues()` 补 argv 唯一性；基线表 20→19 行）而变，subjects 依「重审并更新 digest」处置——**机械重绑**，既有结论不变。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物：`protocol/repo_stats.json`、`results/interop/*.json`、`protocol/RECEIPTS.json`、
> `protocol/conformance_report.json`、`docs/verification-cards.md` 均为可复算投影或随基线刷新的
> 当前态文档，按既有口径不入审计绑定（它们由 check31/33/35/38 自证一致）。

## 一、内部差距（开工依据）

1. **端壳退役只到「历史事实」，没有常驻判据**：GUI 端壳已于 2026-09-09 由作者裁决永久退役
   （`5ae202b` 移出 `desktop/src/ui` + 打包线；`f8123b6` + 清理波移出 `desktop/main.py`、
   `desktop/src/__main__.py`、`desktop/packaging/`、`build-desktop.yml`、UI 测试/自检脚本）。
   但「已删除」这件事此前**没有任何门禁断言**——`purity_scan` R1 只扫 01/02 协议件里的端壳关键词，
   树内重新长出 GUI 模块不会被任何 check 拦住。
2. **人机交互面真空**：`docs/L3_FROZEN.md` 明文写「能力入口一律落 CLI」，而 CLI 只有非交互命令面，
   端壳退役后**没有**任何给人用的入口（`nf run` 需要参数、`nf --help` 是命令清单，不是可用界面）。
   这是 S7「产品上手门槛」在无壳前提下唯一可做的近端解。
3. **终端与命令面可能静默脱钩**：任何菜单/引导若手写命令示例，都会随 CLI 演进腐烂
   （仓库既有教训：`interop` 可选值两次漏同步、`_cov_tmp.json` 类漂移）。需要「菜单不许指向死命令」的机检。

## 二、交付

| 面 | 落点 |
|---|---|
| 终端核心 | `desktop/src/core/terminal.py`（纯 stdlib · 确定性 · 可注入 `runner` 的会话状态机；**不反向依赖** `scripts/nf.py`） |
| CLI 入口 | `scripts/nf.py` 新增 `shell`（别名 `terminal`）：`--exec` 非交互 / `--json` 机器面 / `--no-banner` / `--yes` |
| 启动器 | `scripts/nf`（POSIX）+ `scripts/nf.cmd`（Windows）：无参数即进终端 |
| 能力菜单 | 端壳时代 GUI 七区（导入/校验/管线/生成/资产/预设/社区）→ **既有**命令面映射；菜单真源 = `terminal.ZONES` |
| 安全闸门 | 写入类命令（`--write`/`--apply`/`--register`/`--tag`/`--rm`… + `register`/`import`/`rename`/`release`/`asset add…`）默认拒跑；交互输入 `yes` 或显式 `--yes` 才放行；`serve`/`shell` 在会话内只给指引 |
| 门禁 | verify **check39**：端壳残留零在场（7 个已知落点 + 全树源件扫描）+ 终端三件在场 + 菜单示例全部可解析到真实命令 + `--exec` 两遍逐字节一致 |
| 单测 | `desktop/tests/test_terminal.py` 31 例（解析/闸门/会话/CLI 集成/零依赖面；含「菜单指向死命令即红」与「SystemExit 不打断会话」） |
| 文档 | `docs/terminal.md`（入 doc_hygiene 四型与指令档清单）+ README/README.en 五分钟上手 + llms.txt 工具面 + ROADMAP/L3_FROZEN 状态 |
| 基线 | verify v2.28 → **v2.29**；`quality_baseline.EXPECTED_*` = **check1-39 · PASS=68** |

## 三、验收证据（本机实测）

- `bash verify.sh` → **PASS=68 · WARN=0 · FAIL=0（exit 0）**。
- `nf shell --exec "/menu"` 两次输出逐字节一致；`--json` 输出 `nf-shell` 逐条记录。
- `nf conformance` → **conformant 27/27**（含审计面）；`nf audit` 扫描零 issue；`nf approve --verify` 有效；
  `nf receipts` 根与实时重算一致；`nf interop --check` 入仓面逐字节一致；`nf stats --check` 自述数字一致。
- 端壳残留实测：树内无 `desktop/main.py`、`desktop/src/ui/*.py`、`desktop/packaging/`、
  `build-desktop.yml`、`build-android.yml`、GUI 测试与自检脚本（`rg` 全树为空）。

## 四、设计偏差与边界（如实记录）

1. **终端是逐行 REPL，不是全屏 TUI**：Windows 无 `curses`、core「零第三方依赖」是成文红线、
   且逐行读写可重定向/可 diff/可进 CI。全屏 TUI 会引入终端能力耦合，故不做（边界写入 `docs/terminal.md`）。
2. **门禁选新增 check39 而非并入 check33**：与 check38 的既有节奏一致（每面一条独立 check，可追溯）；
   代价是基线数与派生文档必须同步刷新（本轮已同步：CONFORMANCE 声明 / conformance 报告 / 内容绑定批准 /
   协议层回执 / interop 入仓面 / 验证卡册 / 审计 digest）。
3. **旧审计 digest 重绑**：基线变更触及 15 份审计件的被审对象（29 条），按仓库既有实践
   （见 commit `ba1cb08`「审计摘要重绑」）重绑 digest，使审计面回到自洽；**未**逐件重写旧审计结论——
   本波改动面由本件（AUD-0024）承担记录责任。此项属执行者自决的机械修复，作者可复核。
4. **未做（遗留）**：① **已收口（2026-09-29，作者确认后执行）**：17 件孤儿字节码（GUI/APK 时代模块的
   `.pyc`）已删除——判据是「现役三棵代码树 `desktop/src/core`／`desktop/tests`／`scripts` **之外**的全部
   `.pyc`」（含 GUI 时代 `ui/` 归档、`.rivet/scratch`、`.github/scripts/__pycache__`）；全为 `.gitignore`
   产物，删后 `git status` 无变化（本项不产生入库面）；
   ② `scripts/e2e_desktop_headless.py` 与 `.github/workflows/e2e-desktop.yml` 的「desktop」命名属端壳时代遗留
   （功能是 headless core E2E，与 GUI 无关），改名牵连 purity_scan 放行键与单测，未擅动；
   ③ L2 真身仍挂在端壳时代目录名 `desktop/` 下，是否改名 `core/` 属独立一波，需作者立项。

## 五、五维自评（改了什么维 / 水位 / 差在哪）

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑ | 新增 check39（端壳零回潮 + 终端可达 + 菜单无死命令 + 输出确定），基线 PASS 66 → 68，全绿 |
| 动态可执行 | ↑ | 终端把「协议被真实执行」的人机入口补回：命令直通 + 写入面闸门 + 确定性回归面 |
| 架构纯度 | →／↑ | 终端纯 stdlib、core 不反向依赖 CLI、菜单与命令面单一判据；端壳残留从「无判据」变「零容忍」 |
| 资产密度 | → | 本波不新增内容资产（终端为能力面，非内容面） |
| 文档可执行性 | ↑ | `docs/terminal.md` 读到即能跑；README 双语面同步并由 check34 断言一致 |
| 差在哪 | — | 全屏 TUI / 真·交互式表单（GUI 时代 zone 表单）未做：前者违背零依赖红线，后者需作者裁决新形态 |
