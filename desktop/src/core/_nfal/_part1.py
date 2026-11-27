"""core.nfal 私有实现分片 1/3（对外只经 core.nfal 门面导入）：SCHEMA、EXPR_PREFIX 等"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import json_doc

SCHEMA = "nf-nfal/1"


#: 命令层进入记号：condition 以 '=' 开头即按 nf-expr 解析；否则视为既有散文（advisory）。
EXPR_PREFIX = "="


_KIND_MAP = {
    "string": "string", "integer": "int", "number": "number", "boolean": "bool",
    "array": "list", "object": "map", "event": "event", "state": "map", "untyped": "untyped",
}


_LIT_TYPES = {"bool": "bool", "int": "int", "float": "number", "str": "string", "null": "null"}


NUMERIC = ("int", "number")


#: 封闭函数集（借 CEL 的「标准函数 + 无用户函数」纪律）：名 → (参数类型表, 返回类型)
FUNCS: Dict[str, Tuple[Tuple[str, ...], str]] = {
    "size": (("list|map|string",), "int"),
    "contains": (("string|list", "any"), "bool"),
    "has": (("map", "string"), "bool"),
    "startsWith": (("string", "string"), "bool"),
    "int": (("any",), "int"),
    "string": (("any",), "string"),
}


_IMPLICIT_TRUE: Dict[str, Any] = {"k": "lit", "t": "bool", "v": True}


class _Unknown:
    """未知值哨兵（三值逻辑的第三值；与 None 区分）。"""

    def __repr__(self) -> str:
        return "UNKNOWN"


UNKNOWN = _Unknown()


def diag(code: str, severity: str, message: str, pos: int = 0) -> Dict[str, Any]:
    """诊断行（与 NF 既有 fail/warn 口径同形）。"""
    return {"code": code, "severity": severity, "message": message, "pos": pos}


def _read_json(path: Path) -> Any:
    try:
        return json_doc.load(path, None, what=str(path))
    except (OSError, ValueError):  # 读不到/坏件 ⇒ None（调用方如实少给符号，不臆造；失败语义同 docstring）
        return None


def _kind_to_type(kind: Optional[str]) -> str:
    return _KIND_MAP.get(str(kind or "untyped"), "untyped")


def _accepts(expected: str, actual: str) -> bool:
    if expected == "any" or actual in ("unknown", "untyped"):
        return True
    return actual in expected.split("|")


def _load_state_kinds(root: Path) -> Dict[str, str]:
    data = _read_json(root / "protocol" / "world_slots.json")
    slots = data.get("slots") if isinstance(data, dict) else None
    if not isinstance(slots, dict):
        return {}
    # 存 io_types 原始词（映射只在 SymbolTable.resolve 做一次，避免双重映射把 int 变 untyped）
    return {str(k): str((v or {}).get("kind") or "untyped") for k, v in slots.items()}


def _load_events(root: Path) -> set:
    data = _read_json(root / "protocol" / "event_registry.json")
    events = data.get("events") if isinstance(data, dict) else None
    return set(events.keys()) if isinstance(events, dict) else set()


def _io_kinds(text: str) -> Dict[str, str]:
    """模块 machine_contract 的 outputs 类型面（io_types 词表；缺件记 untyped）。"""
    try:
        from core import io_types as iot
        data = iot.parse_io_types(text) or {}
        return {str(k): str(v) for k, v in (data.get("outputs") or {}).items()}
    except Exception:  # noqa: BLE001 —— 词表不可用 ⇒ 类型记 untyped（合法值，不臆造）
        return {}


def _load_tokens(root: Path, module_refs: Optional[List[str]]) -> Dict[str, str]:
    """token 面 = 模块 machine_contract 的 outputs + io_types。

    借统一围栏解析 conformance_scan 与 io_types 词表；**不依赖 pipelinerun**——
    更稳的模块不得依赖更不稳的模块（SDP 不变量，见 coupling_metrics）。
    """
    try:
        from core import conformance_scan as csc
    except Exception:  # noqa: BLE001 —— 围栏解析不可用 ⇒ 无 token 面（如实缺口，不伪造）
        return {}
    wanted = {str(x) for x in (module_refs or [])}
    bare = {x.split(":")[-1] for x in wanted}
    tokens: Dict[str, str] = {}
    for doc in csc._module_docs(str(root)):
        try:
            text = Path(doc).read_text(encoding="utf-8")
        except OSError:  # 该模块文档读不到 ⇒ 跳过它（不臆造其 outputs；缺件如实少给 token）
            continue
        parsed = csc._fence_yaml(text, "machine_contract")
        mc = parsed.get("machine_contract") if isinstance(parsed, dict) else None
        if not isinstance(mc, dict):
            continue
        mid = str(mc.get("id") or "")
        if wanted and mid not in wanted and mid.split(":")[-1] not in bare:
            continue
        kinds = _io_kinds(text)
        for tok in mc.get("outputs") or []:
            tokens.setdefault(str(tok), str(kinds.get(str(tok)) or "untyped"))
    return tokens


class SymbolTable:
    """guard 的名字/类型面（只读快照；未登记即缺，不臆造）。"""

    def __init__(self, state: Optional[Dict[str, str]] = None,
                 events: Optional[set] = None,
                 tokens: Optional[Dict[str, str]] = None,
                 inputs: Optional[Dict[str, str]] = None) -> None:
        self.state = dict(state or {})
        self.events = set(events or set())
        self.tokens = dict(tokens or {})
        self.inputs = dict(inputs or {})

    @classmethod
    def from_repo(cls, root: str = ".", module_refs: Optional[List[str]] = None,
                  with_tokens: bool = False) -> "SymbolTable":
        r = Path(root)
        tokens = _load_tokens(r, module_refs) if with_tokens else {}
        return cls(state=_load_state_kinds(r), events=_load_events(r), tokens=tokens)

    def resolve(self, path: List[str]) -> Optional[str]:
        """登记全名 → 类型；未登记返回 None（不猜、不模糊匹配）。"""
        full = ".".join(path)
        if full in self.state:
            return _kind_to_type(self.state[full])
        if full.startswith("state.") and full[6:] in self.state:   # 可选前缀：真源是登记全名
            return _kind_to_type(self.state[full[6:]])
        if len(path) == 2 and path[0] == "event" and path[1] in self.events:
            return "bool"
        if len(path) == 2 and path[0] == "token" and path[1] in self.tokens:
            return _kind_to_type(self.tokens[path[1]])
        if len(path) == 2 and path[0] == "input" and path[1] in self.inputs:
            return _kind_to_type(self.inputs[path[1]])
        return None


def _pos_of(node: Any) -> int:
    return node.get("pos", 0) if isinstance(node, dict) else 0


def _ref_type(node: Dict[str, Any], sym: SymbolTable, diags: List[Dict[str, Any]]) -> str:
    path = list(node["path"])
    kind = sym.resolve(path)
    if kind is None:
        diags.append(diag("E0301", "fail",
                          "未登记符号 %s（不在 world_slots / event_registry / token / input 面内）"
                          % ".".join(path), _pos_of(node)))
        return "unknown"
    return kind


def _require(expected: str, actual: str, pos: int, diags: List[Dict[str, Any]], what: str) -> None:
    if not _accepts(expected, actual):
        diags.append(diag("E0303", "fail", "%s 期望 %s，实为 %s" % (what, expected, actual), pos))


def _join(a: str, b: str) -> str:
    if "unknown" in (a, b):
        return "unknown"
    if "untyped" in (a, b):
        return "untyped"
    return "bool"


def _rel_result(lt: str, rt: str) -> str:
    """比较/成员运算的结果类型：unknown → unknown；untyped → untyped（不得冒充 bool）。"""
    if "unknown" in (lt, rt):
        return "unknown"
    if "untyped" in (lt, rt):
        return "untyped"
    return "bool"


def _infer_cmp(node: Dict[str, Any], lt: str, rt: str, diags: List[Dict[str, Any]]) -> str:
    for side, t in (("左", lt), ("右", rt)):
        if t not in NUMERIC and t != "string" and t not in ("unknown", "untyped"):
            diags.append(diag("E0303", "fail", "%s 比较不支持 %s" % (side, t), _pos_of(node)))
    return _rel_result(lt, rt)


def _infer_arith(op: str, lt: str, rt: str, pos: int, diags: List[Dict[str, Any]]) -> str:
    if op == "+" and lt == "string" and rt == "string":
        return "string"
    if op == "+" and lt == "list" and rt == "list":
        return "list"
    if "unknown" in (lt, rt):
        return "unknown"
    if "untyped" in (lt, rt):
        return "untyped"
    for side, t in (("左", lt), ("右", rt)):
        if t not in NUMERIC:
            diags.append(diag("E0303", "fail", "%s %s 不支持" % (op, side), pos))
            return "unknown"
    return "number" if "number" in (lt, rt) else "int"
