# 发布结论复跑 v0（release conclusion）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-04
> **Status**: v0 已实装（scripts/release_conclusion.py）· 与 nf release 分工不同

## 是什么

一条命令给出「这台机器现在能不能发布」：**干净树闸门 → checks-only → N 分片并行 → 汇总**。

与 `nf release` 的分工：`nf release` 管**次序**（一致性报告 → 批准 → 回执的冻结链）；
本件管**结论**（冻结之后 check1-42 到底过没过）。两者不替代。

## 为什么有它

三条都是实测教训（2026-11-04）：

1. **full 档单进程太慢**：本机 35–40 分钟（参考机基线 1265 s）。分片跑与全量跑判据等价——
   执行器自带「分片并集 == discover 全集」断言，并行只改墙钟。
2. **脏树上跑分片会产生假红**：文档改到一半去跑分片，报了一堆 conformance / living-docs
   失败，全是中间态。所以脏树默认**拒跑**（rc=2），确需跑加 `--allow-dirty`（并打印警告）。
3. **结论要有固定入口**：此前「发布结论」靠人记三条命令 + 人肉看表，容易漏步（我自己就漏过）。

## 怎么用

```bash
python scripts/release_conclusion.py                 # 缺省 8 分片并行
python scripts/release_conclusion.py --jobs 4        # 并发数
python scripts/release_conclusion.py --dry-run       # 只打印计划（含脏树判定），不跑
python scripts/release_conclusion.py --json          # 机读汇总（含每片 rc 与墙钟）
```

退出码：0 = 可发布 · 1 = 有失败 · 2 = 前置不满足（脏树 / 参数错）。

## 判据（可证）

```bash
# 纯函数判据（脏树闸门 / 分片汇总 / 计划生成）+ dry-run 集成
python -m unittest desktop.tests.test_release_conclusion    # 10 项全绿

# 真跑（干净树上）：8 片并行 + checks-only，总墙钟约 15 分钟量级
python scripts/release_conclusion.py --jobs 8
```

## 边界

- **不等于 `bash verify.sh` 全量档的逐条对照**：它跑的是同一批 check（checks-only 覆盖
  check1-42 的结构面，分片覆盖 check12 的测试面）。真要在 CI 上做「单进程全量」仍用
  `bash verify.sh`。
- **不冻结任何东西**：本件只判读，不写仓库（冻结请用 `nf release --freeze --apply`）。
- 分片并发上限按 `--jobs`，越界自动夹到 `[1, 16]`。
