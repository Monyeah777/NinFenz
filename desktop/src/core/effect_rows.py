# -*- coding: utf-8 -*-
"""效应面（P-A2）：源码 → **效应行**（ast 可证），并给出规则层（P-A1）的同判定 구현。

效应行 = {"kind": net|proc|env|time|fs_probe, "evidence": 点号名, "line": 行号}
级别 = 最严一行（net/proc/env/time → UNSAFE；fs_probe → CONDITIONAL；无行 → SAFE）。
为什么要两套实现：判定表落在条文里，**两实现必须同结果**（差分自证；P-A3 的雏形）。
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List

from core import nfal_rules as nr

#: 导入名 → 效应类
IMPORT_KINDS = {
    "socket": "net", "urllib": "net", "http": "net", "requests": "net",
    "httpx": "net", "aiohttp": "net",
    "subprocess": "proc", "ctypes": "proc", "multiprocessing": "proc",
    "platform": "env", "getpass": "env",
    "time": "time", "datetime": "time",
}
#: 属性全名 → 效应类
ATTR_KINDS = {
    "os.environ": "env", "os.getenv": "env",
    "os.system": "proc", "shutil.which": "proc",
    "time.time": "time", "time.perf_counter": "time", "time.monotonic": "time",
    "datetime.now": "time", "date.today": "time",
    "os.path.exists": "fs_probe", "os.walk": "fs_probe",
}
#: 末段方法名 → 效应类（Path 等实例方法的点号名不定，按末段认）
METHOD_KINDS = {
    "exists": "fs_probe", "is_file": "fs_probe", "is_dir": "fs_probe",
    "glob": "fs_probe", "iterdir": "fs_probe", "walk": "fs_probe",
    "getenv": "env", "which": "proc", "system": "proc",
    "perf_counter": "time", "monotonic": "time", "now": "time", "today": "time",
    "time": "time",
}
_SEV = {"net": 2, "proc": 2, "env": 2, "time": 2, "fs_probe": 1}
_RANK_LEVEL = {2: "UNSAFE", 1: "CONDITIONAL", 0: "SAFE"}


def _dotted(node: ast.AST) -> str:
    """属性节点 → 点号名（os.path.exists）。"""
    parts: List[str] = []
    cur: Any = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def rows(source: str) -> List[Dict[str, Any]]:
    """源码 → 效应行（去重后按 kind/evidence/line 排序）。**解析不出 → 最严一行**（fail-closed）。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [{"kind": "env", "evidence": "unparseable", "line": 0}]
    out: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        line = int(getattr(node, "lineno", 0) or 0)
        if isinstance(node, ast.Import):
            for a in node.names:
                k = IMPORT_KINDS.get(a.name.split(".")[0])
                if k:
                    out.append({"kind": k, "evidence": "import " + a.name, "line": line})
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                k = IMPORT_KINDS.get(node.module.split(".")[0])
                if k:
                    out.append({"kind": k, "evidence": "from " + node.module, "line": line})
        elif isinstance(node, ast.Attribute):
            dotted = _dotted(node).lower()
            k = ATTR_KINDS.get(dotted) or METHOD_KINDS.get(dotted.rsplit(".", 1)[-1])
            if k:
                out.append({"kind": k, "evidence": dotted, "line": line})
    best: Dict[Any, Dict[str, Any]] = {}
    for r in out:
        key = (r["kind"], r["evidence"])
        if key not in best or r["line"] < best[key]["line"]:
            best[key] = r
    return sorted(best.values(), key=lambda r: (r["kind"], r["evidence"], r["line"]))


def level(rows_list: List[Dict[str, Any]]) -> str:
    """直算级别：取最严一行（未知类按最严处置）。"""
    top = 0
    for r in rows_list:
        top = max(top, _SEV.get(r.get("kind"), 2))
    return _RANK_LEVEL[top]


def _rule_doc(rows_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """把判定表写成规则：sev(类, 严度) ⇒ level_max(严度)；module 事实兜底 SAFE。"""
    facts: List[Dict[str, Any]] = [{"pred": "module", "args": ["m"]}]
    for r in rows_list:
        facts.append({"pred": "sev", "args": [r["kind"], _SEV.get(r["kind"], 2)]})
    rules = [{"head": {"pred": "level_max", "args": [0]},
              "body": [{"pred": "module", "args": ["m"]}]}]
    for rank in (1, 2):
        rules.append({"head": {"pred": "level_max", "args": [rank]},
                      "body": [{"pred": "sev", "args": ["?K", rank]}]})
    return {"schema": "nf-nfal-rules/1", "facts": facts, "rules": rules, "fuel": 100000}


def level_via_rules(source: str) -> str:
    """规则层（P-A1）实现的同判定；未达定点即取最严（fail-closed）。"""
    got = nr.evaluate(_rule_doc(rows(source)))
    if got["status"] != "OK":
        return "UNSAFE"
    ranks: List[int] = []
    for f in got["facts"]:
        if f.startswith("level_max("):
            try:
                ranks.append(int(f[len("level_max("):-1]))
            except ValueError:
                pass
    return _RANK_LEVEL[max(ranks)] if ranks else "UNSAFE"
