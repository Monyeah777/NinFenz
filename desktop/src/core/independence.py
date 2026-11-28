"""生产/治理双平面边界（`nf-independence/1`）：把「谁不许 import 谁」做成可复算数据。

为什么（方案 §5.5 IN-01/IN-02/IN-04）：依赖方向一旦靠人记，迟早出现「生产为了省事顺手
import 治理」或「治理 import 生产运行时才能验证」——两条都会让「不装治理也能生产」变成
空话。本模块把平面归属登记成数据（`protocol/independence.json`），再对 **全部 core 模块**
做导入闭包：任一条闭包边跨进禁止平面即 FAIL，不只看清单内的一跳。

口径与既有件同源：
- 解析复用 `core.import_graph.parse`（AST、静态、含动态导入检测）；
- 闭包按「全部 `desktop/src/core/*.py` + 包目录」展开，未登记模块也参与遍历
  （否则把违规模块改名成未登记就能绕）；
- 动态导入（`__import__` / `importlib`）使静态闭包不可信 ⇒ 默认 FAIL，只允许
  `dynamic_allow` 显式登记（带理由）的白名单；
- 报告落 `results/independence.json`，`--check` 断言「在盘 == 实时重算」。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import import_graph

SCHEMA = "nf-independence/1"
REPORT_SCHEMA = "nf-independence-report/1"
REL = "protocol/independence.json"
REPORT_REL = "results/independence.json"
PLANES = ("production", "governance", "shared")
#: 禁止的跨平面边（源平面 → 目标平面）：生产/治理互不 import；共享原语不得反向依赖任一平面。
FORBIDDEN = (
    ("production", "governance"),
    ("governance", "production"),
    ("shared", "production"),
    ("shared", "governance"),
)
GUIDE = "修复指引："
_CORE = ("desktop", "src", "core")


def _module_file(root: str, name: str) -> Optional[Path]:
    """`core/<name>.py` 或 `core/<name>/__init__.py`；不在场 → None。"""
    base = Path(root).joinpath(*_CORE)
    single = base / (name + ".py")
    if single.is_file():
        return single
    pkg = base / name / "__init__.py"
    return pkg if pkg.is_file() else None


def _universe(root: str) -> Dict[str, Path]:
    """全部 core 模块（顶层 .py + 带 __init__.py 的包）。列不出 → 空表（调用方按缺件报）。"""
    out: Dict[str, Path] = {}
    base = Path(root).joinpath(*_CORE)
    try:
        entries = list(os.scandir(base))
    except OSError:
        return out
    for ent in entries:
        if ent.is_file() and ent.name.endswith(".py"):
            out[ent.name[:-3]] = Path(ent.path)
        elif ent.is_dir() and (Path(ent.path) / "__init__.py").is_file():
            out[ent.name] = Path(ent.path) / "__init__.py"
    return out


def load(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("缺边界登记 %s（%s 新增生产/治理平面归属）" % (REL, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        raise ValueError(REL + " schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    return doc


def _plane_issues(planes: Dict[str, Any],
                  universe: Dict[str, Path]) -> Tuple[List[str], Dict[str, str]]:
    """平面三组互斥、非空、模块在场 → (issues, 模块→平面)。"""
    issues: List[str] = []
    seen: Dict[str, str] = {}
    for plane in PLANES:
        names = planes.get(plane)
        if not isinstance(names, list) or not names:
            issues.append("平面 %s 缺失或为空（%s 三个平面都必须非空）" % (plane, GUIDE))
            continue
        for name in names:
            name = str(name)
            if name in seen:
                issues.append("模块 %s 同时登记在 %s 与 %s（%s 平面互斥）"
                              % (name, seen[name], plane, GUIDE))
                continue
            seen[name] = plane
            if universe and name not in universe:
                issues.append("平面 %s 登记了不存在的模块：%s（%s 删除或改指向真实件）"
                              % (plane, name, GUIDE))
    return issues, seen


def _dynamic_allow_issues(doc: Dict[str, Any], seen: Dict[str, str]) -> List[str]:
    """dynamic_allow 白名单：必须已归平面且写明理由。"""
    issues: List[str] = []
    for name, reason in (doc.get("dynamic_allow") or {}).items():
        if str(name) not in seen:
            issues.append("dynamic_allow 登记了不在任何平面的模块：%s（%s 先归平面）"
                          % (name, GUIDE))
        if not str(reason or "").strip():
            issues.append("dynamic_allow.%s 缺理由（%s 动态导入白名单须可复核）" % (name, GUIDE))
    return issues


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    """登记表结构校验（平面互斥/模块在场/动态白名单可核）→ 问题列表。"""
    issues: List[str] = []
    planes = doc.get("planes")
    if not isinstance(planes, dict):
        return ["缺 planes 对象（" + GUIDE + "登记 production/governance/shared 三组）"]
    universe = _universe(root)
    if not universe:
        issues.append("读不到 core 模块目录（" + GUIDE + "在仓库根运行）")
    plane_issues, seen = _plane_issues(planes, universe)
    issues.extend(plane_issues)
    issues.extend(_dynamic_allow_issues(doc, seen))
    return issues


def _deps(path: Path) -> Optional[Tuple[frozenset, bool]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return import_graph.parse(text)


def _closure_walk(seeds: List[str], universe: Dict[str, Path],
                  memo: Dict[str, Optional[Tuple[frozenset, bool]]]
                  ) -> Tuple[set, Dict[str, Optional[str]]]:
    """从 seeds 做静态导入闭包遍历 → (已达集合, 父指针)。"""
    seen: set = set()
    stack = list(seeds)
    parent: Dict[str, Optional[str]] = {}
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        if name not in memo:
            memo[name] = _deps(universe[name]) if name in universe else None
        info = memo[name]
        if info is None:
            continue
        for dep in info[0]:
            if dep not in parent:
                parent[dep] = name
            if dep not in seen:
                stack.append(dep)
    return seen, parent


def _shortest_paths(seen: set,
                    parent: Dict[str, Optional[str]]) -> Dict[str, Tuple[str, ...]]:
    """父指针还原每个模块的最短路径（上限 64 跳，防环）。"""
    paths: Dict[str, Tuple[str, ...]] = {}
    for name in seen:
        chain: List[str] = [name]
        cur = name
        while parent.get(cur) is not None and len(chain) < 64:
            cur = str(parent[cur])
            chain.append(cur)
        paths[name] = tuple(reversed(chain))
    return paths


def _closure_path(root: str, seeds: List[str],
                  universe: Dict[str, Path]) -> Tuple[Dict[str, List[str]], Dict[str, Tuple[str, ...]]]:
    """从 seeds 出发的静态导入闭包 → ({模块: 依赖}, {被依赖模块: 最短路径})。

    路径形如 `("a","b","c")` 表示 a → b → c；用于把违规边说清，不只报「有交叉」。
    """
    memo: Dict[str, Optional[Tuple[frozenset, bool]]] = {}
    seen, parent = _closure_walk(seeds, universe, memo)
    edges = {n: sorted((memo.get(n) or (frozenset(), False))[0]) for n in seen}
    paths = _shortest_paths(seen, parent)
    return edges, paths


def _scan_indexes(doc: Dict[str, Any]) -> Tuple[Dict[str, List[str]], Dict[str, str], set]:
    """扫描用的三视图：平面→模块、模块→平面、动态白名单集合。"""
    planes = {p: [str(n) for n in doc["planes"][p]] for p in PLANES}
    owner = {name: plane for plane in PLANES for name in planes[plane]}
    allow = {str(k) for k in (doc.get("dynamic_allow") or {})}
    return planes, owner, allow


def _forbidden_targets() -> Dict[str, set]:
    """源平面 → 它不许到达的目标平面集合。"""
    return {plane: {dst for src, dst in FORBIDDEN if src == plane}
            for plane in PLANES}


def _closure_edge_issues(plane: str, planes: Dict[str, List[str]],
                         paths: Dict[str, Tuple[str, ...]], edges: Dict[str, List[str]],
                         forbidden_targets: Dict[str, set]) -> Tuple[List[str], int]:
    """单平面的闭包越界逐边报 → (issues, 违规边数)。"""
    issues: List[str] = []
    count = 0
    reachable = set(edges)
    for dst_plane in sorted(forbidden_targets[plane]):
        for target in sorted(reachable & set(planes[dst_plane])):
            chain = paths.get(target, (target,))
            issues.append(
                "%s 平面闭包越界：%s 到达 %s 平面的 %s（%s 断开这条边；"
                "跨平面只许经共享原语/契约数据）"
                % (plane, " → ".join(chain), dst_plane, target, GUIDE))
            count += 1
    return issues, count


def _dynamic_import_issues(owner: Dict[str, str], universe: Dict[str, Path],
                           allow: set) -> List[str]:
    """动态导入面：解析不出即报；含动态导入且未登记理由也报。"""
    issues: List[str] = []
    for name in sorted(owner):
        path = universe.get(name)
        if path is None:
            continue
        info = _deps(path)
        if info is None:
            issues.append("解析不出模块 %s（%s 修语法或删除登记）" % (name, GUIDE))
            continue
        if info[1] and name not in allow:
            issues.append("模块 %s 含动态导入，静态边界无法证明（%s 改为静态 import，"
                          "或在 dynamic_allow 显式登记理由）" % (name, GUIDE))
    return issues


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """→ (issues, stats)；issues 空 = 双平面边界成立。"""
    issues: List[str] = []
    try:
        doc = load(root)
    except ValueError as exc:
        return [str(exc)], {}
    issues.extend(validate(doc, root))
    universe = _universe(root)
    stats: Dict[str, Any] = {"modules": len(universe),
                             "production": 0, "governance": 0, "shared": 0,
                             "forbidden_edges": 0, "dynamic_allow": 0}
    if issues:
        return issues, stats
    planes, owner, allow = _scan_indexes(doc)
    for p in PLANES:
        stats[p] = len(planes[p])
    stats["dynamic_allow"] = len(allow)

    forbidden_targets = _forbidden_targets()
    for plane in PLANES:
        edges, paths = _closure_path(root, planes[plane], universe)
        edge_issues, count = _closure_edge_issues(plane, planes, paths, edges,
                                                  forbidden_targets)
        issues.extend(edge_issues)
        stats["forbidden_edges"] += count
    issues.extend(_dynamic_import_issues(owner, universe, allow))
    return issues, stats


def build_report(root: str = ".") -> Dict[str, Any]:
    issues, stats = scan(root)
    try:
        doc = load(root)
        planes = {p: len(doc["planes"][p]) for p in PLANES}
    except (ValueError, KeyError):
        planes = {}
    stats["planes"] = planes
    return {"schema": REPORT_SCHEMA, "ok": not issues, "findings": issues,
            "counts": stats}


def render(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    from core import atomic_write
    doc = build_report(root)
    atomic_write.write_text(Path(root) / REPORT_REL, render(doc))
    return doc["findings"], doc


def check_committed(root: str = ".") -> List[str]:
    """在盘报告与实时重算逐字节比对（手改报告/少跑 --write 都红）。"""
    path = Path(root) / REPORT_REL
    if not path.is_file():
        return ["缺边界报告 %s（%s 跑 python scripts/check_independence.py --write）"
                % (REPORT_REL, GUIDE)]
    try:
        have = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ["读不出 %s：%s" % (REPORT_REL, exc)]
    want = render(build_report(root))
    if want != have:
        return ["边界报告与实时重算不一致（%s 跑 python scripts/check_independence.py --write）"
                % GUIDE]
    return []
