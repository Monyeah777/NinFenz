"""author protocol|graph|spec：受控编辑作者对象；每次编辑后跑核心校验，失败不落盘。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import core
from ..canonical import JsonParseError, digest, loads_strict
from ..errors import AppError
from ..io_utils import write_json_atomic
from .common import Outcome, format_human, load_doc


def _target_path(args) -> Path:
    return Path(args.out or args.file)


def _save(args, doc: dict) -> Path:
    target = _target_path(args)
    write_json_atomic(target, doc, canonical=True)
    return target


def _validate_with_core(op: str, request: dict, *, stem: str) -> dict:
    """编辑后校验：核心失败 → AppError（带 report），调用方不落盘。"""
    return core.call_ok(op, request)


def _parse_value(raw: str) -> Any:
    try:
        return loads_strict(raw)
    except JsonParseError:
        return raw


def cmd_author_protocol(args) -> Outcome:
    pack = load_doc(args.file, "nf-protocol-pack")
    changed: list[str] = []
    if args.clause:
        clause = next((c for c in pack["clauses"] if c["id"] == args.clause), None)
        if clause is None:
            raise AppError("NF-E-003", message=f"找不到条款: {args.clause}", fix="先用 status/查看协议包里的 C-###")
        if args.enable:
            clause["enabled"] = True
            changed.append(f"{args.clause}.enabled=True")
        if args.disable:
            clause["enabled"] = False
            changed.append(f"{args.clause}.enabled=False")
    if args.field:
        field = next((f for f in pack["fields"] if f["id"] == args.field), None)
        if field is None:
            raise AppError("NF-E-003", message=f"找不到字段: {args.field}", fix="先用 F-### 字段 id")
        if args.default is not None:
            field["default"] = _parse_value(args.default)
            changed.append(f"{args.field}.default")
        if args.required is not None:
            field["required"] = bool(args.required)
            changed.append(f"{args.field}.required={bool(args.required)}")
    report = _validate_with_core("protocol-validate", {"pack": pack}, stem="nf-protocol-pack")
    path = None
    if changed:
        path = _save(args, pack)
    human = format_human(
        "协议包编辑" + ("（已落盘）" if changed else "（仅校验，无改动）"),
        [
            ("文件", str(path or args.file)),
            ("改动", ", ".join(changed) or "无"),
            ("校验", report.get("verdict")),
            ("digest", digest(pack)),
        ],
    )
    return Outcome(
        {
            "protocol": pack,
            "path": str(path) if path else None,
            "changed": changed,
            "report": report,
            "digest": digest(pack),
        },
        human,
    )


def _parse_add_node(raw: str) -> dict:
    parts = raw.split(":")
    if len(parts) < 3:
        raise AppError("NF-E-003", message=f"--add-node 格式应为 N06:module:标题[:module_ref]", fix="例：--add-node N06:gate:质检")
    node_id, kind, title = parts[0], parts[1], parts[2]
    node: dict = {"id": node_id, "kind": kind, "title": title, "ports": {"in": [], "out": []}}
    if len(parts) >= 4 and parts[3]:
        node["module_ref"] = {"id": parts[3]}
    return node


def _parse_add_edge(raw: str) -> dict:
    parts = raw.split(":")
    if len(parts) < 6:
        raise AppError(
            "NF-E-003",
            message=f"--add-edge 格式应为 E05:from:to:from_port:to_port[:data|control]",
            fix="例：--add-edge E05:N03:N04:draft:draft:data",
        )
    edge_id, src, dst, from_port, to_port = parts[:5]
    edge_type = parts[5] if len(parts) > 5 and parts[5] else "data"
    return {"id": edge_id, "from": src, "to": dst, "from_port": from_port, "to_port": to_port, "type": edge_type}


def cmd_author_graph(args) -> Outcome:
    graph = load_doc(args.file, "nf-pipeline-graph")
    changed: list[str] = []
    if args.mode:
        graph["mode"] = args.mode
        changed.append(f"mode={args.mode}")
    # 先删后加：让"删旧边 E03 + 加新边 E03"这类重排/重命名成为合法的一次编辑
    for edge_id in args.del_edge or []:
        if not any(e["id"] == edge_id for e in graph["edges"]):
            raise AppError("NF-E-003", message=f"找不到边: {edge_id}", fix="检查边 id")
        graph["edges"] = [e for e in graph["edges"] if e["id"] != edge_id]
        changed.append(f"del-edge {edge_id}")
    for raw in args.add_node or []:
        node = _parse_add_node(raw)
        if any(n["id"] == node["id"] for n in graph["nodes"]):
            raise AppError("NF-GRF-002", message=f"节点 id 重复: {node['id']}", fix="改用唯一 N##")
        graph["nodes"].append(node)
        changed.append(f"add-node {node['id']}")
    for node_id in args.del_node or []:
        if not any(n["id"] == node_id for n in graph["nodes"]):
            raise AppError("NF-E-003", message=f"找不到节点: {node_id}", fix="检查节点 id")
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] != node_id]
        graph["edges"] = [e for e in graph["edges"] if e["from"] != node_id and e["to"] != node_id]
        graph["weights"].pop(node_id, None)
        changed.append(f"del-node {node_id}")
    for raw in args.add_edge or []:
        edge = _parse_add_edge(raw)
        if any(e["id"] == edge["id"] for e in graph["edges"]):
            raise AppError("NF-GRF-002", message=f"边 id 重复: {edge['id']}", fix="改用唯一 E##")
        graph["edges"].append(edge)
        changed.append(f"add-edge {edge['id']}")
    for raw in args.weight or []:
        if "=" not in raw:
            raise AppError("NF-E-003", message=f"--weight 格式应为 N##=0..100: {raw}", fix="例：--weight N04=90")
        node_id, value = raw.split("=", 1)
        try:
            number = int(value)
        except ValueError as exc:
            raise AppError("NF-GRF-007", message=f"权重必须是整数: {raw}", fix="0..100 的整数") from exc
        if number < 0 or number > 100:
            raise AppError("NF-GRF-007", message=f"权重越界: {raw}", fix="权重限 0..100 且只挂 stage/module")
        graph["weights"][node_id] = number
        changed.append(f"weight {node_id}={number}")
    for node_id in args.del_weight or []:
        graph["weights"].pop(node_id, None)
        changed.append(f"del-weight {node_id}")
    if args.required_stage:
        stages = list(graph["settings"].get("required_stages", []))
        for stage in args.required_stage:
            if stage not in stages:
                stages.append(stage)
        graph["settings"]["required_stages"] = stages
        changed.append("required_stages=" + ",".join(stages))
    report = _validate_with_core("graph-validate", {"graph": graph}, stem="nf-pipeline-graph")
    path = None
    if changed:
        path = _save(args, graph)
    human = format_human(
        "管线图编辑" + ("（已落盘）" if changed else "（仅校验，无改动）"),
        [
            ("文件", str(path or args.file)),
            ("改动", ", ".join(changed) or "无"),
            ("校验", report.get("verdict")),
            ("digest", digest(graph)),
        ],
    )
    return Outcome(
        {
            "graph": graph,
            "path": str(path) if path else None,
            "changed": changed,
            "report": report,
            "digest": digest(graph),
        },
        human,
    )


def _constraints(slot: dict) -> list[dict]:
    return slot.setdefault("constraints", [])


def _set_constraint(slot: dict, op: str, value: Any) -> None:
    rows = _constraints(slot)
    for row in rows:
        if row.get("op") == op:
            row["value"] = value
            return
    entry: dict = {"op": op}
    if value is not None:
        entry["value"] = value
    rows.append(entry)


def _remove_constraint(slot: dict, op: str) -> None:
    slot["constraints"] = [row for row in _constraints(slot) if row.get("op") != op]


def cmd_author_spec(args) -> Outcome:
    spec = load_doc(args.file, "nf-md-spec")
    changed: list[str] = []
    if args.slot:
        slot = next((s for s in spec["slots"] if s["id"] == args.slot), None)
        if slot is None:
            raise AppError("NF-E-003", message=f"找不到槽位: {args.slot}", fix="用 SLT-## 槽位 id")
        if args.required is not None:
            slot["required"] = bool(args.required)
            changed.append(f"{args.slot}.required={bool(args.required)}")
        if args.min_chars is not None:
            _set_constraint(slot, "min_chars", args.min_chars)
            changed.append(f"{args.slot}.min_chars={args.min_chars}")
        if args.max_chars is not None:
            _set_constraint(slot, "max_chars", args.max_chars)
            slot.setdefault("budget", {})["max_chars"] = args.max_chars
            changed.append(f"{args.slot}.max_chars={args.max_chars}")
        if args.max_tokens is not None:
            _set_constraint(slot, "max_tokens", args.max_tokens)
            slot.setdefault("budget", {})["max_tokens"] = args.max_tokens
            changed.append(f"{args.slot}.max_tokens={args.max_tokens}")
        for raw in args.add_constraint or []:
            if ":" in raw:
                op, value = raw.split(":", 1)
                parsed: Any = int(value) if value.lstrip("-").isdigit() else value
            else:
                op, parsed = raw, None
            _set_constraint(slot, op, parsed)
            changed.append(f"{args.slot}.constraint={op}")
        for op in args.remove_constraint or []:
            _remove_constraint(slot, op)
            changed.append(f"{args.slot}.rm={op}")
    report = _validate_with_core("spec-validate", {"spec": spec}, stem="nf-md-spec")
    path = None
    if changed:
        path = _save(args, spec)
    human = format_human(
        "MD spec 编辑" + ("（已落盘）" if changed else "（仅校验，无改动）"),
        [
            ("文件", str(path or args.file)),
            ("改动", ", ".join(changed) or "无"),
            ("校验", report.get("verdict")),
            ("digest", digest(spec)),
        ],
    )
    return Outcome(
        {
            "spec": spec,
            "path": str(path) if path else None,
            "changed": changed,
            "report": report,
            "digest": digest(spec),
        },
        human,
    )
