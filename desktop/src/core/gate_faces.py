# -*- coding: utf-8 -*-
"""门禁读面台账（W-03）：静态面 / 动态面 / 声明面 与三源对账。

为什么要它（§6 前置）：门禁失败的直接原因是它的读面变了，不是它 import 了谁。
三源：动态面 observed（read_memo 实读）/ 静态面 static（ast）/ 声明面 declared（manifest）。
对账三规则：声明不在观测=过期；观测不在(静态∪声明)=抽取漏洞；静态不在声明=未声明依赖。

纪律：只读；纯标准库；同输入同输出；不新增 check 序号（入口命名 audit，不占 scan 名额）。
"""
from __future__ import annotations

import ast
import fnmatch
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

MANIFEST_REL = "protocol/gate_experts.json"
CODE_FACES = ("desktop/src/core", "scripts")
#: 声明面口径（§4）：顶层 schema 名与 skip_safety 三档（§5）。
MANIFEST_SCHEMA = "nf-gate-experts/1"
SKIP_SAFETY = ("SAFE", "CONDITIONAL", "UNSAFE")


def _posix(p: str) -> str:
    return str(p).replace("\\", "/")


def _cmp(p: str) -> str:
    """比较用归一：posix + 小写（避开 Windows 上 normcase 改分隔符造成的假分叉）。"""
    return _posix(p).lower()


def norm_key(key: str) -> str:
    """读面 memo 的键 → 绝对路径。键形如 b:<path> / t:<path>。"""
    s = str(key)
    if len(s) > 2 and s[1] == ":" and s[0] in ("b", "t"):
        s = s[2:]
    return os.path.abspath(s)


def rel_face(root: str, keys: Iterable[str]) -> List[str]:
    """把 memo 键归一成仓库相对 posix（只保留落在 root 内的）。"""
    base = os.path.normcase(os.path.abspath(str(root)))
    out = []
    for k in keys:
        n = os.path.normcase(norm_key(k))
        if n == base or n.startswith(base + os.sep):
            tail = n[len(base):].lstrip("\\/").replace("\\", "/")
            out.append(tail)
    return sorted(set(out))


def observed_face(runner: Callable[[], Any], root: str = ".") -> List[str]:
    """跑一次 runner（该专家的只读入口），返回真实读面（仓库相对 posix）。

    conformance_scan 只以模块级 _READ_MEMO 暴露只读记录，且作用域出口即清，
    故必须在 with 内取键——这是当前唯一可得的事实面（§6 观测面）。
    """
    from core import conformance_scan as _cs
    with _cs.read_memo():
        runner()
        memo = getattr(_cs, "_READ_MEMO", None) or {}
        keys = list(memo.keys())
    return rel_face(root, keys)


def static_face(path: str) -> Dict[str, List[str]]:
    """单文件静态面：import 名 + 路径样字符串字面量（含 glob）。"""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    imports, paths = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
                for a in node.names:
                    imports.add(node.module + "." + a.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
            if ("/" in s and " " not in s and len(s) < 120
                    and not s.startswith(("http", "//")) and "\\" not in s):
                paths.add(s)
    return {"imports": sorted(imports), "paths": sorted(paths)}


def static_faces(root: str = ".") -> Dict[str, List[str]]:
    """代码面（core + scripts）的静态读面：模块相对路径 → 路径样字面量表。"""
    out: Dict[str, List[str]] = {}
    for face in CODE_FACES:
        for p in sorted((Path(root) / face).glob("*.py")):
            rel = _posix(p.relative_to(root))
            try:
                out[rel] = static_face(str(p))["paths"]
            except (OSError, SyntaxError):
                out[rel] = []
    return out


def load_manifest_doc(root: str = ".") -> Dict[str, Any]:
    """读声明面原文；缺件/坏件返回空表（由 audit 如实报 warn，不裸崩）。"""
    p = Path(root) / MANIFEST_REL
    if not p.is_file():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def validate_manifest(doc: Any) -> List[str]:
    """声明面形状校验 → 违例清单（空=合规）。fail-closed：缺字段/未知级别即违例。"""
    out: List[str] = []
    if not isinstance(doc, dict) or not doc:
        return ["声明面缺失或非对象"]
    if doc.get("schema") != MANIFEST_SCHEMA:
        out.append("schema 须为 %s，实为 %r" % (MANIFEST_SCHEMA, doc.get("schema")))
    experts = doc.get("experts")
    if not isinstance(experts, list):
        return out + ["experts 须为数组"]
    for i, e in enumerate(experts):
        if not isinstance(e, dict):
            out.append("experts[%d] 须为对象" % i)
            continue
        if not str(e.get("id") or "").strip():
            out.append("experts[%d] 缺 id" % i)
        if not isinstance(e.get("reads"), list):
            out.append("experts[%d] reads 须为数组（读面声明）" % i)
        if e.get("skip_safety") not in SKIP_SAFETY:
            out.append("experts[%d] skip_safety 须在 %s，实为 %r"
                       % (i, list(SKIP_SAFETY), e.get("skip_safety")))
    return out


def load_manifest(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """声明面 → {id: 专家}（只用形状合法的条目；整体校验由 audit 报违例）。"""
    doc = load_manifest_doc(root)
    out: Dict[str, Dict[str, Any]] = {}
    for e in (doc.get("experts") or []):
        if isinstance(e, dict) and e.get("id"):
            out[str(e["id"])] = e
    return out


def covered(path: str, patterns: Iterable[str]) -> bool:
    """path 是否被 patterns 覆盖：非 glob 按目录前缀；glob 按 fnmatch。"""
    p = _cmp(path)
    for pat in patterns:
        g = _cmp(pat)
        if not any(ch in g for ch in "*?["):
            if p == g or p.startswith(g.rstrip("/") + "/"):
                return True
        elif fnmatch.fnmatchcase(p, g):
            return True
    return False


def audit(root: str = ".", observed: Optional[Dict[str, List[str]]] = None,
          static: Optional[Dict[str, List[str]]] = None
          ) -> Tuple[List[str], Dict[str, Any]]:
    """三源对账 → (issues, stats)。observed/static 可注入（测试与后续接线共用）。"""
    doc = load_manifest_doc(root)
    declared = load_manifest(root)
    issues: List[str] = []
    stats: Dict[str, Any] = {"experts": len(declared), "facts": {}, "warns": []}
    if not doc:
        stats["warns"].append("声明面缺件（%s 未落，见 W-03.3）：本次无专家可对账" % MANIFEST_REL)
    else:
        issues += validate_manifest(doc)
    for eid, e in sorted(declared.items()):
        reads = [str(x) for x in (e.get("reads") or [])]
        st = list((static or {}).get(eid) or [])
        ob = list(observed[eid]) if (observed and eid in observed) else None
        stats["facts"][eid] = {"declared": len(reads), "static": len(st),
                               "observed": len(ob) if ob is not None else None}
        for p in st:
            if not covered(p, reads):
                issues.append("静态面未声明：%s 的 %s（补 reads 或删该读取）" % (eid, p))
        if ob is None:
            continue
        for p in ob:
            if not covered(p, reads):
                issues.append("观测面未声明：%s 的 %s（声明⊄观测=过期）" % (eid, p))
        for p in reads:
            if not any(covered(o, [p]) for o in ob):
                issues.append("声明未观测到：%s 的 %s（观测⊄声明=抽取漏洞或读面已变）" % (eid, p))
    return issues, stats
