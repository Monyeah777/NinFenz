"""P-A5：把「门禁影响图」投影成 NFA-L/R 规则，并由 DAG 后端求值。

规则面（与 gate_graph.closure 同语义的两条路径）：
  affects(X, Y) :- imports(X, Y).                       # 直接依赖
  affects(X, Z) :- imports(X, Y), affects(Y, Z).        # 传递（反向可达）
  hit(E)        :- expert(E, X), affects(X, C), changed(C).
  hit(E)        :- expert(E, C), changed(C).            # 变更点本身就是该专家的模块

意义：Part 2 的规则/后端与 Part 1 的影响图第一次**同语义双实现**——差分自证见
tests/test_gate_datalog.py；DAG 后端还额外给出 gate 推导图统计（节点/边/深度）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from core import gate_faces as gf
from core import gate_graph as gg
from core import nfal_rules as nr

FUEL = 5000000


def route_doc(root: str = ".", changed_modules: Sequence[str] = (),
              experts: dict[str, Any] | None = None) -> dict[str, Any]:
    """门禁影响图 → nfal-rules 文档（事实：imports/expert/changed；规则：affects/hit）。"""
    dep_map = gg.module_deps(root)
    decl = experts if experts is not None else gf.load_manifest(root)
    facts: list[dict[str, Any]] = []
    for mod, deps in sorted(dep_map.items()):
        for dep in sorted(deps):
            facts.append({"pred": "imports", "args": [mod, dep]})
    for eid, e in sorted(decl.items()):
        mod = str(e.get("module") or "").strip()
        stem = Path(mod).stem if mod else eid
        facts.append({"pred": "expert", "args": [eid, stem]})
    for cm in sorted(set(changed_modules)):
        facts.append({"pred": "changed", "args": [cm]})
    rules = [
        {"head": {"pred": "affects", "args": ["?X", "?Y"]},
         "body": [{"pred": "imports", "args": ["?X", "?Y"]}]},
        {"head": {"pred": "affects", "args": ["?X", "?Z"]},
         "body": [{"pred": "affects", "args": ["?X", "?Y"]},
                  {"pred": "imports", "args": ["?Y", "?Z"]}]},
        {"head": {"pred": "hit", "args": ["?E"]},
         "body": [{"pred": "expert", "args": ["?E", "?X"]},
                  {"pred": "affects", "args": ["?X", "?C"]},
                  {"pred": "changed", "args": ["?C"]}]},
        {"head": {"pred": "hit", "args": ["?E"]},
         "body": [{"pred": "expert", "args": ["?E", "?C"]},
                  {"pred": "changed", "args": ["?C"]}]},
    ]
    return {"schema": "nf-nfal-rules/1", "facts": facts, "rules": rules, "fuel": FUEL}


def routed(root: str = ".", changed_modules: Sequence[str] = (),
           experts: dict[str, Any] | None = None,
           backend: str = "dag") -> tuple[list[str], dict[str, Any]]:
    """→ (命中的专家 id 排序表, 求值结果)。backend ∈ {dag, naive, seminaive}。"""
    doc = route_doc(root, changed_modules, experts=experts)
    fn = {"dag": nr.evaluate_dag, "naive": nr.evaluate,
          "seminaive": nr.evaluate_seminaive}[backend]
    got = fn(doc)
    hits = sorted({f[len("hit("):-1] for f in got["facts"] if f.startswith("hit(")})
    return hits, got
