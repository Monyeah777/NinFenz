# 保留与删除（RETENTION / DELETION）

> ⛔ 操作指令：本件是 `protocol/privacy.json` 的保留/删除投影；删除前必须有可复原证据（backup/vcs/quote），机密/受限类还须留 blame（谁/何时/为何）。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.1（保留/删除 + 删除证据）
> 纪律：删除不可逆 ⇒ 证据先行；删除失败/不可复原必须显式登记，不得静默吞掉。

## 保留模式词表

| 模式 | 含义 | 删除要求 |
|---|---|---|
| user-managed | 用户自行决定保留期 | 删除前留证据 |
| ephemeral | 临时（本机调试期） | 可整体删除；不要求长期保留 |
| immutable | 不可变：默认保留 | 只删无引用且已归档副本 |
| rotation | 轮换：到期/撤销即换 | 先轮换/吊销再删 |

## 保留/删除表

| 编号 | 数据类 | 分级 | 保留模式 | 删除方式 | 证据类型 | blame |
|---|---|---|---|---|---|---|
| DC-01 | 用户内容资产 | internal | user-managed | git 历史/备份 | vcs | 否 |
| DC-02 | 会话/认知记录 | confidential | user-managed | 用户删除/换 store，删除前备份 | backup | 是 |
| DC-03 | 证据/回执 | internal | immutable | 归档副本后删 | backup | 否 |
| DC-04 | 密钥/信任材料 | restricted | rotation | 先轮换/吊销再删 | backup | 是 |
| DC-05 | 门禁/构建日志 | internal | ephemeral | 直接删除；留档按 backup | backup | 否 |
| DC-06 | 外部材料副本 | internal | user-managed | 删除本地副本 | quote | 否 |
| DC-07 | 评测/模型证据 | confidential | immutable | 随模型版本归档后删 | backup | 是 |
| DC-08 | 发布物 | public | immutable | 发布撤回；git 历史 | vcs | 否 |

## 删除证据规则

1. 每次删除必须给出 `{target, kind, ref}`：`kind ∈ {backup, vcs, quote}`，`ref` 指向可复原位置（备份路径 / commit / 原文引用）；机检入口 `core.delete_evidence.check`。
2. `confidential` / `restricted` 类删除必须带 `blame`（谁在何时为何删）；机检入口 `core.delete_evidence.missing_blame`。
3. 删除失败（证据缺失/ref 不可解析）必须报错并保留现场；不得「先删后补证据」。

## 测试与判据

- 删除证据正/反例：`desktop/tests/test_privacy_contract.py`（缺 ref / 非法 kind / 缺 blame 必须红）。
- 保留超期面：`ephemeral` 数据类（DC-05）的落点必须在 `.gitignore` 内（`git check-ignore` 机检），不得入仓；`immutable` 类删除必须走归档副本 + 证据。
- 复核命令：`python -m pytest desktop/tests/test_privacy_contract.py -q`
