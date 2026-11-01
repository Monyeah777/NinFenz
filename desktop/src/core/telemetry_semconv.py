"""遥测对齐 OTel GenAI 语义约定（内部差距实证：docs/45_执行遥测规范.md 定义的
`nf assemble --trace` 记录是**自定 JSON**，仓库全域 opentelemetry/otel/span 命中 0
——遥测落盘面存在，但对外界不可消费）。

本模块把既有 trace 记录**映射**为 OTel GenAI semconv 的属性面（不改 trace 格式本身，
不引入 OTel SDK——core 零第三方依赖红线保持）：

- 每个 trace 记录 = 一次工具调用的 span：`gen_ai.operation.name=execute_tool` +
  `gen_ai.tool.name=nf.<命令>`；
- 入参/出参走 semconv 的结构化字段（`gen_ai.tool.call.arguments` / `.result`）；
- NF 侧身份走 `gen_ai.agent.name`；需求原文走 `gen_ai.tool.call.arguments` 内字段；
- 输出 `OTLP 形状` JSON（resourceSpans → scopeSpans → spans），供 collector 侧适配。

纪律：**不宣称 OTLP 传输兼容**（无 protobuf/无导出端点，只有形状与属性命名对齐）；
属性名以 semconv 现行文档为准（docs/gen-ai/gen-ai-spans.md 实测提取）；
schema_url 未填 = semconv 官方站点尚标 TODO，不杜撰。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

#: 本模块输出的 scope 名（采集侧识别用）
SCOPE_NAME = "nf.telemetry"
SCOPE_VERSION = "1.0.0"
MAX_TRACE_BYTES = 16 * 1024 * 1024

#: semconv 属性名（照抄规范，不做同义改写）
A_OPERATION = "gen_ai.operation.name"
A_TOOL_NAME = "gen_ai.tool.name"
A_TOOL_CALL_ID = "gen_ai.tool.call.id"
A_TOOL_ARGS = "gen_ai.tool.call.arguments"
A_TOOL_RESULT = "gen_ai.tool.call.result"
A_AGENT_NAME = "gen_ai.agent.name"
A_CONVERSATION = "gen_ai.conversation.id"

OP_EXECUTE_TOOL = "execute_tool"
_HEX = set("0123456789abcdef")


def _hex_pad(value: Any, length: int) -> str:
    """十六进制补齐：只保留 hex 字符，截断/补零到固定长度。"""
    raw = "".join(ch for ch in str(value or "").lower() if ch in _HEX)
    return raw[:length].ljust(length, "0")

#: trace 字段 → 调用参数面（入参）/ 结果面（出参）
_ARG_FIELDS = ("requirement", "phase", "status")
_RESULT_FIELDS = ("matched", "package", "pipeline", "allowed_modules",
                  "ok", "issues", "stats")


def _json_value(value: Any) -> Any:
    """semconv 的结构化字段：保持 JSON 可表示（字符串原样）。"""
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def tool_name_of(record: Dict[str, Any]) -> str:
    """`nf assemble` / `nf run` → `nf.assemble` / `nf.run`（点分工具名）。"""
    raw = str(record.get("tool") or "nf").strip()
    parts = raw.split()
    return "%s.%s" % (parts[0], parts[1]) if len(parts) > 1 else parts[0]


def call_id_of(record: Dict[str, Any]) -> str:
    """确定性调用标识（trace 无时间戳纪律：id 由内容摘要派生，可复现）。"""
    key = json.dumps({k: record.get(k) for k in
                      ("tool", "phase", "requirement", "package", "pipeline")},
                     sort_keys=True, ensure_ascii=False)
    return "nf-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def attributes_for(record: Dict[str, Any],
                   agent_name: str = "ninfenz") -> Dict[str, Any]:
    """单条 trace 记录 → semconv 属性 dict（未提供的字段不杜撰）。"""
    attrs: Dict[str, Any] = {
        A_OPERATION: OP_EXECUTE_TOOL,
        A_TOOL_NAME: tool_name_of(record),
        A_TOOL_CALL_ID: call_id_of(record),
        A_AGENT_NAME: agent_name,
    }
    args = {k: _json_value(record[k]) for k in _ARG_FIELDS if k in record}
    if args:
        attrs[A_TOOL_ARGS] = args
    result = {k: _json_value(record[k]) for k in _RESULT_FIELDS if k in record}
    if result:
        attrs[A_TOOL_RESULT] = result
    phase = record.get("phase")
    if isinstance(phase, str) and phase:
        attrs[A_CONVERSATION] = "nf-%s" % phase
    return attrs


def to_span(record: Dict[str, Any], span_id: str = "",
            agent_name: str = "ninfenz") -> Dict[str, Any]:
    """trace 记录 → OTLP 形状 span（无 trace 时间戳：timeUnixNano 留空由采集方外套）。"""
    name = "%s %s" % (OP_EXECUTE_TOOL, tool_name_of(record))
    call_id = call_id_of(record)
    trace_id = hashlib.sha256(("trace|" + call_id).encode("utf-8")).hexdigest()[:32]
    generated_span = hashlib.sha256(("span|" + call_id).encode("utf-8")).hexdigest()[:16]
    return {
        "name": name,
        "kind": 1,  # SPAN_KIND_INTERNAL
        "traceId": trace_id,
        "spanId": _hex_pad(span_id or generated_span, 16),
        "attributes": [{"key": k, "value": _otlp_value(v)}
                       for k, v in sorted(attributes_for(record, agent_name).items())],
        "status": {"code": 0 if record.get("ok") is None
                   else (1 if record.get("ok") is True else 2)},
    }


def _otlp_value(value: Any) -> Dict[str, Any]:
    """Python 值 → OTLP AnyValue 形状。"""
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, (dict, list)):
        return {"stringValue": json.dumps(value, ensure_ascii=False,
                                          sort_keys=True)}
    if value is None:
        return {"stringValue": ""}
    return {"stringValue": str(value)}


def to_export(records: List[Dict[str, Any]],
              agent_name: str = "ninfenz") -> Dict[str, Any]:
    """trace 记录集 → OTLP 形状 JSON（resourceSpans → scopeSpans → spans）。"""
    spans = [to_span(r, agent_name=agent_name) for r in records]
    return {"resourceSpans": [{
        "resource": {"attributes": [
            {"key": "service.name", "value": {"stringValue": "ninfenz"}},
        ]},
        "scopeSpans": [{
            "scope": {"name": SCOPE_NAME, "version": SCOPE_VERSION},
            "spans": spans,
        }],
    }]}


def load_trace(path: str) -> List[Dict[str, Any]]:
    """读 trace JSON：单条记录或记录数组均可（兼容 nf assemble --trace 产物）。

    形状纪律（2026-10-10 审计 N10，P2）：顶层非对象/数组、对象数组里混标量、**空对象记录**、
    以及 NaN/Infinity 一律拒绝——此前 {} 会产出一条**伪造 span**、NaN 被当合法记录收下。
    knowledge.harvest_frequency 对同一批形状已经拒了；两处口径由 test_trace_shapes 钉住一致
    （刻意不在两模块间加边：telemetry_semconv 是叶子，加边会动耦合面）。
    """
    def _reject_constant(name: str):
        raise ValueError("含非有限数 %s（JSON 无 NaN/Infinity）" % name)

    try:
        size = Path(path).stat().st_size
    except OSError as exc:
        raise ValueError("trace 不可读：%s（%s）" % (path, exc)) from exc
    if size > MAX_TRACE_BYTES:
        raise ValueError("trace 过大（%d > %d 字节）" % (size, MAX_TRACE_BYTES))
    with open(path, encoding="utf-8-sig") as fh:   # 容忍外来件 BOM（审计 N4）
        text = fh.read()
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise ValueError("trace 不是合法 JSON：%s（修复指引：单条记录 {...} 或 "
                         "{records:[...]}）" % exc)
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        data = data["records"]
    elif isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("trace 顶层须为对象或数组，实为 %s（修复指引：单条记录 {...} 或 "
                         "{records:[...]}）" % type(data).__name__)
    bad = sorted({type(r).__name__ for r in data if not isinstance(r, dict)})
    if bad:
        raise ValueError("trace 记录必须都是 JSON 对象，实见 %s（修复指引：去掉标量元素）"
                         % ", ".join(bad))
    if data and any(not r for r in data):
        raise ValueError("trace 含空对象记录 {}（没有任何可消费字段）"
                         "（修复指引：给记录字段，或删掉该条）")
    return list(data)
