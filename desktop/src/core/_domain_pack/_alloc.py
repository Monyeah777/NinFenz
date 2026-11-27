"""domain_pack · _alloc（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from core import conformance_scan as csc

from ._const import (
    PIPELINE_POOL,
    REGISTRY_REL,
)
from ._io import (
    _read_json,
    module_stems,
    used_pipeline_ids,
)


def allocate(root: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """分配全局唯一 id（幂等：已登记包返回其现值）。"""
    code = spec["code"]
    proto = Path(root) / "community" / spec["pack_name"] / "protocol.yaml"
    if proto.is_file():
        text = csc.read_text_cached(proto)
        pipe = re.search(r"(?m)^\s*pipeline:\s*(P\d{2,3})\s*$", text)
        ids = re.findall(r'(?m)^\s*-\s*"([^"]+:M\d{2})"\s*$', text)
        if pipe and len(ids) == 2:
            return {"pipeline": pipe.group(1), "exist": True, "module_ids": ids,
                    "stems": ["%sa" % code, "%sb" % code]}
    reg = _read_json(Path(root) / REGISTRY_REL) or {}
    for p in reg.get("protocols") or []:
        if p.get("id") == spec["pack_name"] and re.fullmatch(r"P\d{2,3}",
                                                             str(p.get("pipeline") or "")):
            return {"pipeline": p["pipeline"], "exist": True,
                    "module_ids": [str(x) for x in p.get("module_ids") or []]}
    used = set(used_pipeline_ids(root))
    pipe_id = next((x for x in PIPELINE_POOL if x not in used), "")
    if not pipe_id:
        raise ValueError("管线 id 池已用尽（%d 个）" % len(PIPELINE_POOL))
    stems = module_stems(root)
    ids = []
    for letter in ("a", "b"):
        stem = "%s%s" % (code, letter)
        others = [p for p in stems.get(stem, []) if "/%s/" % spec["pack_name"] not in p]
        if others:
            raise ValueError("模块文件名 token 冲突：%s ∈ %s" % (stem, others))
        ids.append("%s:M%02d" % (spec["category"], 1 if letter == "a" else 2))
    return {"pipeline": pipe_id, "exist": False, "module_ids": ids,
            "stems": ["%sa" % code, "%sb" % code]}




# ---------------------------------------------------------------- 生成

def _slug(spec: Dict[str, Any]) -> str:
    return spec["code"].lower()




def _yaml_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return '"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"')




def dump_yaml(obj: Any, indent: int = 0) -> List[str]:
    """极简确定性 YAML 发射器（只覆盖本工厂的数据形状；字符串一律带引号）。

    用途：概念图机读块必须是 `concept_graph:` 起头的 YAML 围栏（JSON 带引号的键过不了
    concept_graph.fenced_block 的首键判据）。
    """
    pad = " " * indent
    out: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append("%s%s:" % (pad, k))
                out += dump_yaml(v, indent + 2)
            else:
                out.append("%s%s: %s" % (pad,
 k,
 "[]" if v == [] else "{}" if v == {} else _yaml_scalar(v)))
        return out
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                first = True
                for k, v in item.items():
                    if first and not isinstance(v, (dict, list)):
                        out.append("%s- %s: %s" % (pad, k, _yaml_scalar(v)))
                        first = False
                    elif first:
                        out.append("%s- %s:" % (pad, k))
                        out += dump_yaml(v, indent + 4)
                        first = False
                    elif isinstance(v, (dict, list)) and v:
                        out.append("%s  %s:" % (pad, k))
                        out += dump_yaml(v, indent + 4)
                    else:
                        out.append("%s  %s: %s"
                                   % (pad, k, "[]" if v == [] else _yaml_scalar(v)))
            else:
                out.append("%s- %s" % (pad, _yaml_scalar(item)))
        return out
    return ["%s%s" % (pad, _yaml_scalar(obj))]
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
