# 数据地图（DATA MAP）

> ⛔ 操作指令：本件是 `protocol/privacy.json` 的人读投影；改数据类先改真源再同步本件，判据 `desktop/tests/test_privacy_contract.py` 会红。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.1
> 纪律：位置一律写相对仓路径或用户态路径（`~/.NinFenz/`）；不确定的写 `UNKNOWN`，不猜测。

## 分类词表

| 级别 | 含义 |
|---|---|
| public | 可公开：发布物、公开文档 |
| internal | 内部：工程证据/日志/外部材料副本，泄露影响有限 |
| confidential | 机密：会话/认知记录、评测与模型证据 |
| restricted | 受限：密钥/信任材料，绝不入仓/入日志 |

## 数据类地图

| 编号 | 数据类 | 分级 | 位置 | 含什么 | 存储/处理者 | owner |
|---|---|---|---|---|---|---|
| DC-01 | 用户内容资产 | internal | `community/`、`library/`、`05_资产库/` | 用户内容、资产正文 | 仅本机；无外部处理者 | user |
| DC-02 | 会话/认知记录 | confidential | `~/.NinFenz/`（NF_HOME，`NARRATIVE_FORGE_HOME` 可覆盖） | 会话、认知记录 | 仅本机；无外部处理者 | user |
| DC-03 | 证据/回执 | internal | `results/`、`protocol/RECEIPTS.json`、`protocol/generated/receipt_chain.json` | digest、仓相对路径 | 仅本机；无外部处理者 | maintainers |
| DC-04 | 密钥/信任材料 | restricted | `~/.NinFenz/keys/` | 私钥、token | 仅本机；无外部处理者；仓内被 .gitignore 拒绝 | user |
| DC-05 | 门禁/构建日志 | internal | `.nf-logs/`（本地未跟踪） | 日志文本 | 仅本机；无外部处理者 | maintainers |
| DC-06 | 外部材料副本 | internal | `docs/reference/external/` | 外部文档副本 | 仅本机；无外部处理者 | maintainers |
| DC-07 | 评测/模型证据 | confidential | `results/ccos/`、`protocol/eval/` | 评测记录、提示词摘要 | 仅本机；无外部处理者 | maintainers |
| DC-08 | 发布物 | public | `packaging/npm/payload/` | 公开协议/代码/文档 | 仅本机生成；分发即公开 | maintainers |

## 最小化规则

| 编号 | 规则 | 证据 |
|---|---|---|
| MIN-01 | 证据只存 digest 与仓相对路径，不存正文/绝对路径 | `desktop/src/core/evidence.py` |
| MIN-02 | 上下文按任务裁剪并有注入预算上限 | `desktop/src/core/injection_budget.py` |
| MIN-03 | 删除前必须有可复原证据（backup/vcs/quote） | `desktop/src/core/delete_evidence.py` |
| MIN-04 | 凭据检测/脱敏唯一实现 | `desktop/src/core/meta_cockpit/secret_guard.py` |

## PII / 凭据扫描面

- 工具：`desktop/src/core/privacy_scan.py`（邮箱/手机号）+ `desktop/src/core/meta_cockpit/secret_guard.py`（私钥/token）。
- 声明面：`results/`、`protocol/`（文本后缀、单件 ≤1 MiB；不可判定件记 skipped，不当干净）。
- 判据：`test_privacy_contract.py`（扫描面零命中 + fixture 检测/脱敏抽样 + 不可判定显式呈报）。

## 复核命令

```bash
python -m pytest desktop/tests/test_privacy_contract.py -q
python -c "import json;d=json.load(open('protocol/privacy.json',encoding='utf-8'));print(d['schema'],len(d['data_classes']))"
```
