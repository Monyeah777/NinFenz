# 发布结论复跑 v0（release conclusion）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-04
> **Status**: v0 已实装（scripts/release_conclusion.py）· 与 nf release 分工不同

## 是什么

一条命令给出「这台机器现在能不能发布」：**干净树闸门 → checks-only → N 个独立分片 → 汇总**。

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
python scripts/release_conclusion.py --json          # 机读汇总（含每片 rc/墙钟；失败片带输出尾部）
```

退出码：0 = 可发布 · 1 = 有失败 · 2 = 前置不满足（脏树 / 参数错）。

## 判据（可证）

```bash
# 纯函数判据（脏树闸门 / 分片汇总 / 计划生成）+ dry-run 集成
python -m unittest desktop.tests.test_release_conclusion    # 10 项全绿

# 真跑（干净树上）：checks-only + 8 片顺序跑（墙钟随机器变，不在此钉数字）
python scripts/release_conclusion.py
```

## 边界

- **分区 ≠ 并发**：`--shards` 决定切几片（每片独立进程），`--jobs` 决定同时几片。发布结论用缺省。
- **不等于 `bash verify.sh` 全量档的逐条对照**：它跑的是同一批门禁（checks-only 覆盖结构面，
  分片覆盖测试面）。要在 CI 上做「单进程全量」仍用 `bash verify.sh`。
- **不冻结任何东西**：本件只判读，不写仓库（冻结请用 `nf release --freeze --apply`）。
