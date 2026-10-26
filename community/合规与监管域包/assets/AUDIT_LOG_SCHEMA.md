<!-- nf-asset: key="AUDIT_LOG_SCHEMA" version="1.0" status="active" -->
# 审计日志 schema · 合规与监管

> 用途：AI 内容合规证据包的**留痕章节模板**——规定审计日志的最小字段集、链路标识与保留要求，使「哪次生成、谁复核、谁发布」可回放。
> 资产键：`AUDIT_LOG_SCHEMA`｜消费方：`gate_profiles/regulatory-strict.json`（clause `AUDIT-SECTION` / `AUDIT-FIELD-TABLE` / `AUDIT-TRACE-ID`）、M02 收口与派生、人工评审。
> 定位：本资产是**最小字段契约**；落地实现可扩展字段，但不得删减必填字段。

## 1. 最小字段集（≥5 个必填字段）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trace_id` | string(UUID/ULID) | 是 | 链路标识：一次内容产出全链路同值，关联披露与复核记录 |
| `event_time` | string(ISO 8601, 含时区) | 是 | 事件时间戳，不得用本地时间无时区值 |
| `event_type` | enum | 是 | 事件类型：generate / review / publish / retract / delete |
| `actor_id` | string(匿名化 ID) | 是 | 操作者标识（去标识化后的稳定 ID，不存姓名与证件号） |
| `content_ref` | string | 是 | 内容编号或内容摘要（sha256 前缀），与分发侧编号一致 |
| `decision` | enum | 是 | 处置结果：pass / block / escalate |
| `oversight_role` | string | 是 | 执行复核的角色（对齐资产 `HUMAN_OVERSIGHT` 角色表） |

## 2. 机读 schema（JSON Schema 2020-12 片段）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "nf-audit-log-entry/1",
  "type": "object",
  "required": ["trace_id", "event_time", "event_type", "actor_id", "content_ref", "decision"],
  "properties": {
    "trace_id": {"type": "string", "minLength": 8},
    "event_time": {"type": "string", "format": "date-time"},
    "event_type": {"enum": ["generate", "review", "publish", "retract", "delete"]},
    "actor_id": {"type": "string", "minLength": 2},
    "content_ref": {"type": "string", "minLength": 2},
    "decision": {"enum": ["pass", "block", "escalate"]},
    "oversight_role": {"type": "string"}
  },
  "additionalProperties": true
}
```

## 3. 留痕纪律

1. **链路标识必填**：`trace_id` / `request_id` 至少其一，且贯穿披露、复核、发布三阶段。
2. **时间带时区**：`event_time` 必须含偏移量（如 `2026-10-26T17:42:25+08:00`），禁用裸本地时间。
3. **不存敏感明文**：`actor_id` 用去标识化稳定 ID；日志内不得出现凭据、证件号、完整手机号。
4. **只追加**：日志为 append-only；更正以新事件表达（`retract`/`delete`），不原地改历史。
5. **保留期**：日志保留期见资产 `RETENTION_CONTACT`；到期删除须留删除事件。

## 4. 机检映射（profile → 本资产）

| profile clause | 本资产对应段 | 判定 |
|---|---|---|
| `AUDIT-SECTION` | 证据包「审计日志」章节 | 章节存在 |
| `AUDIT-FIELD-TABLE` | §1 四列表（≥5 行） | 表头 字段/类型/必填/说明 |
| `AUDIT-TRACE-ID` | §1/§3 链路标识 | 出现 `trace_id` 或 `request_id` |
| `PRIVACY-NO-PLAINTEXT` | §3 纪律 3 | 日志样例不含敏感明文 |

## 5. 使用边界

- 本 schema 只约束**证据包内声明的日志字段**，不替代组织的日志平台实现与访问控制。
- 日志本身不得用于二次画像；用途限定见资产 `DATA_PROVENANCE_LEDGER`。
- 时间格式的等价性（RFC 3339 的 `Z` 结尾）在实现侧自行归一，本契约只要求含时区。
