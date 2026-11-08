# 发布结论复跑 v0（release conclusion）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-06
> **Status**: v0 已实装（scripts/release_conclusion.py）· 与 nf release 分工不同

## 是什么

一条命令给出「这台机器现在能不能发布」：**干净树闸门 → payload 对账 → 供应链核对 →
生成物新鲜度 → 静态棘轮 → checks-only → N 个独立分片 → 汇总**。

与 `nf release` 的分工：`nf release` 管**次序**（一致性报告 → 批准 → 回执的冻结链）；
本件管**结论**（冻结之后全部门禁到底过没过）。两者不替代。

## 为什么有它（三条都是实测教训，2026-11-04）

1. **full 档单进程太慢**：本机 35–40 分钟。分片跑与全量跑判据等价——执行器自带「分片并集 ==
   discover 全集」断言，切分只改进程数、不改判据面。
2. **脏树上跑分片会产生假红**：文档改到一半去跑分片，报了一堆 conformance / living-docs
   失败，全是中间态。所以脏树默认**拒跑**（rc=2），确需跑加 `--allow-dirty`（并打印警告）。
3. **单片跑全量 ≠ 分片跑全量**：单片（`--shards 1`）让所有测试共享一个进程，套件级顺序敏感性
   全部暴露——实测同内容「单片全量」出 8 处红、「8 片独立进程」全绿。故缺省是 **8 片**。

## 怎么用

```bash
python scripts/release_conclusion.py                 # 缺省：8 片、顺序跑（每片独立进程）
python scripts/release_conclusion.py --shards 4      # 分区数（并集必须 == 全量，执行器自带断言）
python scripts/release_conclusion.py --jobs 8        # 并发：只建议给独立 runner（单机有争用）
python scripts/release_conclusion.py --dry-run       # 只打印计划（含脏树判定），不跑
python scripts/release_conclusion.py --only-preflight   # 只跑前置面（脏树/payload/供应链/新鲜度/棘轮，约 45 秒）
python scripts/release_conclusion.py --json          # 机读汇总（含每片 rc/墙钟；失败片带输出尾部）
```

退出码：0 = 可发布 · 1 = 有失败 · 2 = 前置不满足（脏树 / 参数错 / bash 身份不对）。

### Windows 上的两个坑（2026-11-06 各花掉 30+ 分钟）

1. **bash 落到 WSL**：从 PowerShell 启动本件时，PATH 里的 `bash` 可能是
   `C:\Windows\System32\bash.exe`（WSL）。它把 `/d/NinFenz` 当成不存在的路径，
   `bash verify.sh --checks-only` 于是 **rc=1 且零输出**——看起来像「checks-only 未过」。
   现在 checks-only 之前会先跑 `bash -c 'uname -o'` 验身份（git-bash/MSYS/cygwin 才放行），
   不对就 rc=2 并说明怎么改。**跑本件请用 git-bash 的 bash**（或项目自带的 ops_bash）。
2. **日志别写进仓库**：`python scripts/release_conclusion.py > gate.log` 会把日志落在工作树里，
   脏树闸门直接拒绝（`?? gate.log`）。日志写到仓库外（如 `D:/nf-gate-logs/`）。

## 快照模式：`--snapshot`（并发会话在场时取结论）

```bash
python scripts/release_conclusion.py --snapshot            # 在 HEAD 的临时 worktree 里跑全量
python scripts/release_conclusion.py --snapshot --keep-snapshot   # 排障：跑完不删，打印路径
```

**它解决什么**：本仓常有并发会话。普通模式在**主工作区**跑，任何一方中途提交/改文件都会让结论作废
（HEAD 移动即无效；分片途中变更会即刻停）。快照模式先把 HEAD 的树**检出到临时 worktree**
（`.worktrees/gate-snap/<run>/wt`），在快照里跑内层脚本——主树之后再怎么改都不影响这次结论。

**绑定语义**：结论证明的是「**该 SHA 的那棵树**是绿的」，不是「当前工作区现在能发布」。外层仍守脏树闸门
（启动时主树必须干净；运行中的改动无影响）。

**环境隔离**（都是实测踩出来的）：
- payload 在快照里按该 SHA 重新暂存（忽略文件不跟 HEAD 走）；
- 独立 `NARRATIVE_FORGE_HOME`（快照内的守护/缓存自成一户，不会连上活树里的守护）；
- `TEMP/TMP` 指到**盘根独立目录**（`.nf-gate-tmp/<run>/tmp`）：与快照同盘（C 盘满时测试会 ENOSPC），
  且不在任何仓库树的祖先链上（否则 `findRepoRoot` 从 %TEMP% 向上命中活树，npm 包的解包机制不会被触发）；
- 内层日志边跑边落盘（`<run>/inner.log`），外层结束前不再「静默 36 分钟」；
- 陈旧快照（被强杀的 run）会自动清理；`--keep-snapshot` 可显式留存。

**边界**：快照是**干净检出**——gitignored 的构建产物（如 `engine/dotnet/dist/`）按设计不在场，
文档路径判据对「引用 gitignored 路径」放行（fresh clone 同样不在场）；判据面与普通模式**同一批**
（checks-only + 8 片），不存在「快照更松」。

## 五步各判什么

| 步 | 判据 | 不过的含义 |
|---|---|---|
| 1 供应链核对 | `node site/tools/sync-numbers.mjs` 与 `python scripts/sync_llms.py --check` | 发布文案里的数字与真源不一致（站点件数/体积、根投影）→ 先修再跑 |
| 2 生成物新鲜度 | `python scripts/freshness_check.py`（职能坐标 / 门检报告 / 一致性报告 / 审计摘要 == 实时重算） | 我改了东西忘了重跑生成器；**这一条以前要 25 分钟才在分片里出现，现在约 20 秒** |
| 3 静态棘轮 | `style_check` / `code_metrics` / `coupling_metrics` / `sast_check`（合计约 12 s） | 命中超基线：跑测试也变不绿，必须当场修 |
| 4 checks-only | `bash verify.sh --checks-only` | 结构性红（契约/回执/纯度/文档面） |
| 5 分片 | 8 个独立进程跑完全部测试，并集 == 全量 | 测试面红 |

#### 第 1、2 步为什么必须在跑测试之前

它们都是「秒级就能判、但错了会在 25 分钟后的分片里以一条红出现」的东西：

- **供应链数字（G5）**：站点件数/体积与根投影此前是「记得手动跑」的命令，而它们正是发布文案数字的
  来源——忘了跑就把旧数字发出去（实测犯过两次）。
- **静态棘轮**：风格 / 代码度量 / 耦合 / SAST 四条都是「超基线即红」，合计约 12 秒——
  2026-11-05 实测：跨会话留下的风格债正是靠这条在 checks-only 之前被拦住的。
- **生成物新鲜度**：角色坐标 / 门检报告 / 一致性报告 / 审计摘要必须是「提交件 == 实时重算」。
  实测在三轮里各让我白跑一次全量，根因永远是「改了东西忘了重跑生成器」。现在任一不过，gate 停在
  20–30 秒处并打印逐项修复命令。

## 修复回路：`--affected`（本地快回路，**不是**发布结论）

发布结论要全量（上面五步），但「改一处、验一处」不必每次都花 36 分钟。分片执行器提供选片：

```bash
python scripts/verify_tests.py --affected --list    # 先看会跑哪些（含选择理由）
python scripts/verify_tests.py --affected           # 跑受影响模块
```

选片分四类，**宁慢勿漏**：

| 变更面 | 选中 | 实测（2026-11-05） |
|---|---|---|
| 干净树 | 只跑常驻集（纯度/风格/死代码/套件隔离/预算/机器面三判据/隔离/参数登记） | 151 条（~100 s） |
| `desktop/tests/test_*.py` | 该模块的测试 | 89 条 |
| `desktop/src/core/*.py` | 反向 import 闭包（谁依赖它） | 135 条 + 常驻集 |
| 其它路径（CLI/文档…） | 测试源码里**引用了该路径**的模块（文档按 `docs/` 目录前缀） | 594 / 1007 条 |
| `verify.sh` / `protocol/` / `.github/` / 门禁本体 | **全量兜底**（改的是判据本身，选片不可信） | 全量 |

判据：`python -m unittest desktop.tests.test_verify_tests_selection`（11 项，纯函数）。

常驻集里放 `test_cli_error_framing`（~100 s）是有意的：2026-11-05/06 两次红都是「新增 argparse
参数却漏登记编码/路径闸门名单」，只有这组判据会红——不常驻就要等 36 分钟的分片才发现。
用 100 秒换 36 分钟。

**并发**：快照跑之前先拿 `.worktrees/gate-snap/.snapshot.lock`（互斥，含 pid/HEAD/时间）；
拿不到就拒绝（或 `--lock-wait N` 排队等）——实测三份全量并发会把 45 分钟拉成 65+ 分钟，
且两份外层会互相清对方 worktree。锁的自清 `unlink` 已登记 `purity_scan.SINK_ALLOW`。

**纪律**：`--affected` 只用于本地修复回路；「可发布」的结论必须来自上面的全量五步。

## 判据（可证）

```bash
# 纯函数判据（脏树闸门 / 分片汇总 / 计划生成）+ dry-run 集成
python -m unittest desktop.tests.test_release_conclusion    # 63 项全绿

# 真跑（干净树上）：checks-only + 8 片顺序跑（墙钟随机器变，不在此钉数字）
python scripts/release_conclusion.py
```

**与 `scripts/precheck.py` 的分工**：precheck 是「高频横向面」的 4 分钟快车道（覆盖 20/378 个测试模块），
用于提交前自查；它**不能**替代本件的全量结论——发布判定仍只认上面的五步。

## 绿结论台账（发布结论的取证记录）

每次 `--snapshot` 的绿结论绑定一个 SHA 与一次墙钟；下表只记「8 片 rc=0 + `checks_only_rc=0` + `head_moved=false`」的结论，
来自本地 `gate-close*.log`（不入库）。

| 序 | HEAD | 墙钟 |
|---|---|---|
| 1 | `8330a373` | 2870 s |
| 2 | `34f657c5` | 2804 s |
| 3 | `a5c99710` | 2658 s |
| 4 | `228253c2` | 2918 s |
| 5 | `89f499a2` | 2755 s |
| 6 | `7bca052e` | 3051 s |
| 7 | `654ad9bc` | 3894 s |
| 8 | `6fd9e3ce` | 3215 s |
| 9 | `cd0ac722` | 3656 s |
| 10 | `cb4ce9e9` | 3870 s（1 片红：跨日假红，已修） |
| — | `2777fbb8` | 3543 s（2 片红：编码闸漏登记 + 判据只支持包路径导入，均已修） |
| 10 | `888299d8` | 3570 s |
| 11 | `9373ef33` | 3680 s |

红结论同样有记录：`3bffa75f` 两片红（文档计数漂移 + 生成物被误判死链）；`e39ae062` 五处横向门禁失配；`cb4ce9e9` 一片红（报告根含构建日期，跨午夜重算必然不同）——
红不是失败，是判据在干活。

## 边界

- **分区 ≠ 并发**：`--shards` 决定切几片（每片独立进程），`--jobs` 决定同时几片。发布结论用缺省。
- **不等于 `bash verify.sh` 全量档的逐条对照**：它跑的是同一批门禁（checks-only 覆盖结构面，
  分片覆盖测试面）。要在 CI 上做「单进程全量」仍用 `bash verify.sh`。
- **不冻结任何东西**：本件只判读，不写仓库（冻结请用 `nf release --freeze --apply`）。
- **payload 与 HEAD 耦合（前置闸门）**：npm 门槛要求 `packaging/npm/payload/payload-manifest.json`
  的 `source_commit == HEAD`，而 payload 是忽略文件——**「工作树干净」不代表 payload 是最新的**。
  故本件跑之前会先比一次：不一致直接 rc=2 并给出重新暂存的命令，不浪费 30 分钟跑完才发现。
  反过来说：**任何新提交都会让上一次结论失效**，重新取证前先 `node packaging/npm/tools/stage-payload.mjs`
  （只写忽略文件，不产生提交）。
