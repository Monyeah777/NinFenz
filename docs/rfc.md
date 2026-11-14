# 协议件 RFC 头与 supersede 链（rfc）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：RFC 头六字段 / 索引真源 / supersede 链判据**复核不变**；补可核现状（`nf rfc` 实读）：
> 在册 **4 件**（NF-0001 01_核心协议 · NF-0002 02_联动注册表 · NF-0003 06_Agent执行协议 · NF-0004 07_官方核心出厂与社区预设导航）·
> 全部 **Active** · 类别 **3 Standards Track + 1 Informational** · 状态词表 **4 值**（Active/Superseded/Deprecated/Experimental）·
> 当前**尚无 supersede 链**（首版，四条 `Supersedes`/`Superseded by` 均为 `—`）。见「§现状对照」。

## 是什么

01/02/06/07 头部现在带机器可读的版本史行（机制借鉴 HMP 的 RFC 系列）：

```
> **RFC**: NF-0001 · **Category**: Standards Track · **Date**: 2026-09-08 ·
  **Status**: Active · **Supersedes**: — · **Superseded by**: —
```

`protocol/rfc_index.json` 是机读索引；文档头部是真源。

## 怎么用

```bash
python scripts/nf.py rfc          # 列 RFC 件与状态
python scripts/nf.py rfc --json
```

## 现状对照（2026-11-13 · 以 `nf rfc` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 在册 RFC | **4 件**：NF-0001 / NF-0002 / NF-0003 / NF-0004 | `nf rfc` |
| 状态 | 全部 **Active** | 同上 |
| 类别 | **3 Standards Track + 1 Informational** | `protocol/rfc_index.json: docs[].category` |
| 状态词表 | **4 值**：Active / Superseded / Deprecated / Experimental | 同上 `status_vocabulary` |
| supersede 链 | **尚无**（首版，四条链字段均为 `—`） | 各件头部 RFC 行 |
| 日期约束 | `Date` == 该件「最后更新」（当前四件均为 2026-11-12） | 判据 |

> 本表只作「当时 → 现行」导航；在册件与状态以 `nf rfc` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py rfc          # 列 RFC 件与状态（含链可解析性）
python scripts/nf.py rfc --json   # 机读索引
```

- 引用本文时：「文档头部是**真源**，`protocol/rfc_index.json` 是索引」= 长期口径；不要只改索引。
- 一旦出现 `Superseded`，必须同时写 `Superseded by` 并指向在册编号，链不得成环。

## 判据（可证）

六字段齐备；编号在册唯一；`Category`/`Status` 在词表内；**`Date` 必须等于该文档的「最后更新」**
（禁止两份日期各说各话）；`Status: Superseded` 必须有 `Superseded by`，且指向在册编号；链不得成环。
