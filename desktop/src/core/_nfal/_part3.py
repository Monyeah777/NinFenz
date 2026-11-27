"""core.nfal 私有实现分片 3/3（对外只经 core.nfal 门面导入）：verdict_of、eval_guard 等"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.nf_expr import LexError, ParseError, parse, strip_pos

from ._part1 import _IMPLICIT_TRUE, EXPR_PREFIX, SCHEMA, UNKNOWN, SymbolTable, diag
from ._part2 import _exc_diag, check_condition, evaluate


def verdict_of(value: Any) -> str:
    """三态判决：True→pass / False→fail / 其余→abstain（abstain 永不折算 pass）。"""
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "abstain"


def eval_guard(ast: Any, env: Dict[str, Any]) -> Dict[str, Any]:
    """对单条 guard 求值 → {verdict, value, diagnostics}（确定性：同输入同结果）。"""
    diags: List[Dict[str, Any]] = []
    value = evaluate(ast, env, diags)
    return {"verdict": verdict_of(value), "value": None if value is UNKNOWN else value,
            "diagnostics": diags}


# ------------------------------------------------------------------ NFIR（规范 JSON 中间表示）
def _fence_pipeline(text: str) -> Any:
    """管线围栏 → dict。首选仓库统一 YAML 加载器；无 PyYAML 时回退管线加载器的零依赖子集解析
    （容器分发链路不装第三方依赖，降级如实、不静默改语义）。"""
    try:
        from core import conformance_scan as csc
        return csc._fence_yaml(text, "Pipeline")
    except Exception:  # noqa: BLE001 —— 无 PyYAML 等 ⇒ 走零依赖子集解析
        from core.pipeline_loader import YAML_FENCE_RE, _parse_yaml_block
        m = YAML_FENCE_RE.search(text)
        return _parse_yaml_block(m.group(1)) if m else None


def load_decl(root: str, pipeline_path: str) -> Dict[str, Any]:
    """管线声明（复用 conformance_scan 统一围栏解析；失败给修复指引）。"""
    r = Path(root)
    p = Path(pipeline_path)
    if not p.is_absolute():
        p = p if p.exists() else (r / pipeline_path)
    src = str(r / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    data = _fence_pipeline(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("Pipeline"), dict):
        return data["Pipeline"]
    if isinstance(data, dict):
        return data
    raise ValueError("管线围栏解析失败：%s（修复指引：检查 frontmatter 与代码围栏闭合）" % pipeline_path)


def _module_refs(decl: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    for ly in decl.get("layers") or []:
        if not isinstance(ly, dict):
            continue
        for key in ("default_modules", "allowed_modules"):
            for m in ly.get(key) or []:
                if str(m) not in refs:
                    refs.append(str(m))
    return refs


def _layer_row(ly: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": ly.get("id"), "name": ly.get("name"),
            "optional": bool(ly.get("optional", False)),
            "modules": [str(x) for x in (ly.get("default_modules") or [])]}


def _edge_row(fl: Dict[str, Any], sym: SymbolTable, diags: List[Dict[str, Any]],
              strict: bool) -> Dict[str, Any]:
    edge: Dict[str, Any] = {"from": fl.get("from"), "to": fl.get("to")}
    cond = fl.get("condition")
    if cond is None:
        edge["guard"] = {"source": "implicit", "expr": None, "ast": _IMPLICIT_TRUE}
        edge["guard_types"] = {"guard": "bool"}
        return edge
    raw = str(cond).strip()
    if not raw.startswith(EXPR_PREFIX):
        sev = "fail" if strict else "warn"
        code = "E0202" if strict else "A0201"
        diags.append(diag(code, sev,
                          "condition 为散文（不可机验）；迁移为 '=<nf-expr>' 后即可静态检查+执行：%"
                              "s"
                          % raw[:80], 0))
        edge["guard"] = {"source": "prose", "expr": raw, "ast": None}
        return edge
    expr = raw[len(EXPR_PREFIX):].strip()
    try:
        ast = parse(expr)
    except (ParseError, LexError) as exc:
        diags.append(_exc_diag(exc))
        edge["guard"] = {"source": "expr", "expr": expr, "ast": None}
        return edge
    gtype, gdiags = check_condition(ast, sym)
    diags.extend(gdiags)
    edge["guard"] = {"source": "expr", "expr": expr, "ast": strip_pos(ast)}
    edge["guard_types"] = {"guard": gtype}
    return edge


def _verdict(diags: List[Dict[str, Any]]) -> str:
    if any(d["severity"] == "fail" for d in diags):
        return "fail"
    if diags:
        return "warn"
    return "pass"


def build_ir(root: str = ".", pipeline_path: str = "", sym: Optional[SymbolTable] = None,
             with_tokens: bool = True, strict: bool = False) -> Dict[str, Any]:
    """管线声明 + guard 表达式 → NFIR（规范 JSON；同输入逐字节同输出）。"""
    decl = load_decl(root, pipeline_path)
    if sym is None:
        sym = SymbolTable.from_repo(root, module_refs=_module_refs(decl), with_tokens=with_tokens)
    diags: List[Dict[str, Any]] = []
    layers = [_layer_row(ly) for ly in decl.get("layers") or [] if isinstance(ly, dict)]
    struct = decl.get("structure") or {}
    edges = [_edge_row(fl, sym, diags, strict)
             for fl in struct.get("flow") or [] if isinstance(fl, dict)]
    return {
        "schema": SCHEMA, "kind": "nfal-ir",
        "pipeline": {"id": decl.get("id"), "name": decl.get("name"),
                     "structure_type": struct.get("type"), "source": str(pipeline_path)},
        "layers": layers, "edges": edges, "tokens": sorted(sym.tokens),
        "diagnostics": diags, "verdict": _verdict(diags),
    }


def canonical(ir: Dict[str, Any]) -> str:
    """NFIR → 规范 JSON 文本（键排序 + 2 空格缩进 + 末尾换行；可 diff/golden）。"""
    return json.dumps(ir, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
