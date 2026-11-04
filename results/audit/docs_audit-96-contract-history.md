---
id: AUD-0048
title: 契约级演进时间线
date: 2026-10-30
scope: 扩展 nf diff --history，在不新增顶层命令的前提下从 Git 历史重建 01/02/06/07、协议声明与 protocol/schema 的结构化演进；补齐 Markdown YAML 字段路径与 JSON schema 结构差异
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/contract_history.py:e452d6d8a0d9849dece08210e7af2acbf554440e8871f8d656f745f533d06646
  - desktop/src/core/contract_text.py:01b784e63dd19425b3609ae3792b6c8d9f40366acb5806f71d10759c96de8fd6
  - desktop/src/core/knowledge_sig.py:06409878244907e1135846a71aae76e5d66303534a7e611b8870a1edd307c35e
  - scripts/nf.py:5802553074a90470c8b360fc69b577ddb0945c5aeed988c62f414869a8110a78
  - desktop/tests/test_knowledge_sig.py:4705091a139b4fc4da9a61bc816e30eeec3221688f3d923e43afc3b11609c17e
  - desktop/tests/test_nf_cli.py:18c407b6780205e50997d99ab9ea967e6ee066b2dca5d087e9eeea632d311804
  - docs/迁移指南-基于nf-sig-diff.md:64b4299bfdec7b663feef412ea16b8b5768c54036754fae066d1c81c3fdbfc5d
  - changes/unreleased/20261030-contract-history.md:4aa6c0df999193ab102115105c450ddae136dfa32c47d07fdebfe271f1059398
---
> 重审（2026-11-04）：分片 1/8 抽检修复：编码闸门/路径旗标名单补全、删零引用常量与函数、耦合基线重冻

> 重审（2026-11-04）：证据线 fail-closed 加固：chain 段必填 / 吊销表坏件判 invalid（攻击矩阵 25→29）

> 重审（2026-11-04）：抽检第二个分片：原子写纪律（包/报告走 atomic_write，临时写例外登记）

> 重审（2026-11-04）：check12 修复波：JSON 面登记 / json_doc 收敛 / Rust 回执去重同步 / 基准 JSON 纯净

> 重审（2026-11-04）：本地 HTTP 面 v0（nf serve --http 三端点）落地 + 端点契约登记 local.*

> 重审（2026-11-04）：cc_resolve（契约面反查）+ 一条链复现脚本落地

> 重审（2026-11-04）：cc_replay 轨迹 + cc_check 单对象策略体检落地（新模块 check_policy）+ 回执去重

> 重审（2026-11-04）：证据复验器扩三种形态 + 攻击矩阵基准（26 项校验路径与基准落地）

> 重审（2026-11-04）：证据包缺省落点改到临时目录（不往仓库落盘）+ CCOS ABI v0 收口

> 重审（2026-11-04）：CCOS ABI v0 + 证据包校验器落地（scripts/nf.py 与 core/terminal.py 摘要变更；并修复本分支既有漂移）

> 重审（2026-10-30）：新增契约级 Git 演进时间线；结构化 Markdown YAML 字段与 JSON schema 差异纳入影响度


# 契约级演进时间线

## 开工依据

仓内已有 `nf sig` 与双文件 `nf diff`，也有版本迁移指南和 CHANGELOG，但没有面向正式契约的
持久演进视图：两次契约修改之间只能手工找 Git 提交、逐个导出文件再比较，无法直接回答
“这份契约何时发生 additive/bump、当时对应哪次提交”。

独立读者侧验证器、轨迹回放与社区包分级均已在仓内存在，故本轮不重复建设这三面。

## 落地面

- `nf diff --history N <契约路径>` 从 Git 历史按旧→新重算签名，输出提交、日期、摘要、
  影响度与结构化变更；`--json` 返回 `nf-contract-history/1`。
- 允许面：`01/02/06/07` 协议文档、`protocol/CONFORMANCE.md`、`protocol/EXTENSION.md` 与
  `protocol/schema/*.json`；路径经过仓库包含性判据。
- Markdown 在既有章节、引用、版本签名上增加 YAML 字段路径；字段删除进入需评审/`bump`。
- JSON 比较规范结构路径：移除、类型/版本变化、`required` 增加判 `bump`；普通字段新增判
  `additive`；正文/描述类值变化判 `editorial`。
- 命令只读，不生成迁移记录；既有迁移四步与 check30 仍是 bump 的处置门禁。

## 验证

| 检查 | 结果 |
|---|---|
| `tests.test_knowledge_sig` | 10/10 PASS（时间线、JSON required、YAML 字段删除、路径拒绝、文本/文件签名等价） |
| 受影响组合 | 233/233 PASS（terminal / changelog / CLI JSON face / nf CLI / knowledge sig） |
| 真实 01 时间线 | 3 次提交可复原；2 次正文更动判 editorial |
| 真实 `contract.schema.json` | 3 次提交可复原；host_consumed 新增判 additive；`$id` 变化判 bump |
| 风格 / 规模 / 耦合 | 定向扫描通过；新增模块均在冻结上限内 |

## 遗留与边界

- 历史读取不跨文件改名推断；路径改名前的提交明确拒绝，不伪造连续签名。
- `--history` 限 1..200 个最近提交，避免无界读取；需要更长历史时分段核查。
- 该时间线是变更事实与影响度工具，不是迁移批准器；bump 仍须作者/维护者按协议留档。
