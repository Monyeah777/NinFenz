# 隐私与数据生命周期（PRIVACY）

> ⛔ 操作指令：本文件是隐私政策的**入口与摘要**；可机检真源在 `protocol/privacy.json`（`nf-privacy/1`），人读细节在 `docs/privacy/`。改数据类必须同步真源与三份人读件，判据会红。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.1 / §3A D05（BL-01 P0 盲区）
> 纪律：不声称「合规 / 认证」；本文是工程事实声明（做了什么、不能保证什么），不是法律意见。

## 范围

- 本仓是**本地优先**的内容生产/装配工具：数据默认只在本机处理，不向外部服务传输；需要联网的只有显式动作（如外部锚抓取、依赖安装），且不携带用户内容。
- 本政策覆盖：用户内容资产、会话/认知记录、证据/回执、密钥材料、门禁日志、外部材料副本、评测/模型证据、发布物。

## 分级（四级）

| 级别 | 含义 | 例子 |
|---|---|---|
| public | 可公开 | 发布物、公开文档 |
| internal | 内部 | 证据/回执（仅摘要）、门禁日志、外部材料副本 |
| confidential | 机密 | 会话/认知记录、评测与模型证据（可能含提示词与用户上下文） |
| restricted | 受限 | 密钥/信任材料（绝不入仓/入日志，泄露即可伪造身份） |

## 最小化

- 证据只存 digest 与仓相对路径，不存正文/绝对路径；上下文按任务裁剪并有注入预算上限；删除前必须有可复原证据（backup/vcs/quote）。
- 凭据检测/脱敏只有唯一实现 `desktop/src/core/meta_cockpit/secret_guard.py`；PII（邮箱/手机号）由 `desktop/src/core/privacy_scan.py` 检测/脱敏。

## 保留与删除

- 保留模式四值：`user-managed` / `ephemeral` / `immutable` / `rotation`（词表与逐类规则见 `protocol/privacy.json` 与 `docs/privacy/RETENTION.md`）。
- 删除必须有可复原证据；`confidential` / `restricted` 删除还须留 blame（谁/何时/为何）。

## 不能保证什么

- 不保证「合规/认证」；不承诺对抗拥有本机管理员权限的攻击者；不保证用户主动把敏感内容写进公开仓后的可撤销性。
- 已知残余风险见 `docs/privacy/DPIA.md` 的「结论与残余风险」；未关闭项显式登记，不静默关闭。

## 索引

- 数据地图：`docs/privacy/DATA_MAP.md`
- 影响评估（LINDDUN）：`docs/privacy/DPIA.md`
- 保留/删除表：`docs/privacy/RETENTION.md`
- 隐私 QA：`docs/qa/PRIVACY_QA.md`
- 机读真源：`protocol/privacy.json`
