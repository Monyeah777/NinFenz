# 发布结论复跑 v0（release conclusion）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-04
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

退出码：0 = 可发布 · 1 = 有失败 · 2 = 前置不满足（脏树 / 参数错）。

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

**纪律**：`--affected` 只用于本地修复回路；「可发布」的结论必须来自上面的全量五步。

## 判据（可证）

```bash
# 纯函数判据（脏树闸门 / 分片汇总 / 计划生成）+ dry-run 集成
python -m unittest desktop.tests.test_release_conclusion    # 44 项全绿

# 真跑（干净树上）：checks-only + 8 片顺序跑（墙钟随机器变，不在此钉数字）
python scripts/release_conclusion.py
```

## 边界

- **分区 ≠ 并发**：`--shards` 决定切几片（每片独立进程），`--jobs` 决定同时几片。发布结论用缺省。
- **不等于 `bash verify.sh` 全量档的逐条对照**：它跑的是同一批门禁（checks-only 覆盖结构面，
  分片覆盖测试面）。要在 CI 上做「单进程全量」仍用 `bash verify.sh`。
- **不冻结任何东西**：本件只判读，不写仓库（冻结请用 `nf release --freeze --apply`）。
- **payload 与 HEAD 耦合（前置闸门）**：npm 门槛要求 `packaging/npm/payload/payload-manifest.json`
  的 `source_commit == HEAD`，而 payload 是忽略文件——**「工作树干净」不代表 payload 是最新的**。
  故本件跑之前会先比一次：不一致直接 rc=2 并给出重新暂存的命令，不浪费 30 分钟跑完才发现。
  反过来说：**任何新提交都会让上一次结论失效**，重新取证前先 `node tools/stage-payload.mjs`
  （只写忽略文件，不产生提交）。
