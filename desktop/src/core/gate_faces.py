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
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core import effect_rows as er

MANIFEST_REL = "protocol/gate_experts.json"
CODE_FACES = ("desktop/src/core", "scripts")
#: 声明面口径（§4）：顶层 schema 名与 skip_safety 三档（§5）。
MANIFEST_SCHEMA = "nf-gate-experts/1"
SKIP_SAFETY = ("SAFE", "CONDITIONAL", "UNSAFE")

# 效应标记表已迁到 core/effect_rows.py（P-A2：效应行成层，ast 可证 + 规则层同判定）。


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


#: audit hook 的活收集器（进程内只装一次 hook；每次调用注册/注销，防跨次泄漏）。
_COLLECTORS: List[set] = []


def _ensure_hook() -> None:
    """确保进程内已装 open 事件 hook（只装一次；hook 装了不可撤，故用注册表而非重装）。"""
    if _COLLECTORS:
        return

    def _hook(event: str, args: Any) -> None:
        if event != "open":
            return
        try:
            p = args[0]
        except (IndexError, TypeError):
            return
        if isinstance(p, int):          # 文件描述符：无路径可记
            return
        try:
            path = os.fsdecode(p)
        except (TypeError, ValueError):
            return
        for seen in list(_COLLECTORS):
            seen.add(path)

    sys.addaudithook(_hook)


def observed_face(runner: Callable[[], Any], root: str = ".",
                  use_hook: bool = False) -> List[str]:
    """跑一次 runner（该专家的只读入口）→ 真实读面（仓库相对 posix）。

    两条观测路径（M2 §23.17 实测二者不通用）：
      - use_hook=False（默认）：借 conformance_scan._READ_MEMO——**只覆盖走它读助手的扫描器**，
        作用域出口即清，故在 with 内取键；
      - use_hook=True：audit hook(open)——与实现无关，谁读都记。hook 装了不可撤，故
        进程内只装一次、按次注册收集器并在 finally 注销（防跨次泄漏）。
    """
    if use_hook:
        _ensure_hook()
        seen: set = set()
        _COLLECTORS.append(seen)
        try:
            runner()
        finally:
            for i, s in enumerate(_COLLECTORS):
                if s is seen:
                    del _COLLECTORS[i]
                    break
        return rel_face(root, seen)
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


def compress_face(paths: Iterable[str]) -> List[str]:
    """具体路径集 → 尽量少的 glob（按 前两段 + 扩展名 归并；宁可过覆盖，不可漏）。

    M2 实测（§23.17）：静态声明面（手写路径）远小于真读面，会漏判；声明面**必须**由
    观测面生成，本函数即那步的压缩器。
    """
    groups: Dict[Any, int] = {}
    for p in paths:
        parts = _posix(p).split("/")
        ext = os.path.splitext(parts[-1])[1]
        # len>=3 取前两段（如 desktop/src）；len==2 取首段（如 scripts）；根文件取自身
        prefix = "/".join(parts[:2]) if len(parts) >= 3 else parts[0]
        key = (prefix, ext)
        groups[key] = groups.get(key, 0) + 1
    out = []
    for (prefix, ext), _n in sorted(groups.items()):
        out.append("%s/**/*%s" % (prefix, ext) if ext else "%s/**/*" % prefix)
    return sorted(out)


def derive_reads(root: str, observed: Iterable[str]) -> List[str]:
    """观测读面 → 声明 reads（仓库相对 glob）。"""
    rels = [r for r in (_posix(x) for x in observed) if r and r != "."]
    return compress_face(rels)


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


def classify_source(text: str) -> Tuple[str, List[str]]:
    """源码面 → (skip_safety, 依据)。

    P-A2 起：输入换成 **effect_rows 的效应行**（ast 可证，带行号），判定表不变；
    需要规则层同判定时用 effect_rows.level_via_rules（差分自证见 test_effect_rows）。
    """
    rs = er.rows(text)
    return er.level(rs), ["%s:%s(L%s)" % (r["kind"], r["evidence"], r["line"]) for r in rs]


def derive_skip_safety(root: str, expert: Dict[str, Any]
                       ) -> Tuple[Optional[str], List[str]]:
    """从专家源码推导 skip_safety；找不到源码返回 (None, 理由)——**不猜级别**。"""
    mod = str(expert.get("module") or "").strip()
    cands = [Path(root) / mod] if mod else []
    if not cands:
        eid = str(expert.get("id") or "")
        cands = [Path(root) / "desktop" / "src" / "core" / (eid + ".py"),
                 Path(root) / "scripts" / (eid + ".py")]
    for p in cands:
        if p.is_file():
            try:
                return classify_source(p.read_text(encoding="utf-8"))
            except OSError:
                break
    return None, ["无源码可推（按保守处置：不得据此下调级别）"]


def load_manifest(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """声明面 → {id: 专家}（只用形状合法的条目；整体校验由 audit 报违例）。"""
    doc = load_manifest_doc(root)
    out: Dict[str, Dict[str, Any]] = {}
    for e in (doc.get("experts") or []):
        if isinstance(e, dict) and e.get("id"):
            out[str(e["id"])] = e
    return out


def _glob_variants(g: str) -> List[str]:
    """glob 变体：`**/` 允许**零层**目录（fnmatch 的 `*` 本就跨 `/`，故去掉即覆盖）。

    修的是实测缺陷：`scripts/**/*.py` 曾匹配不到 `scripts/a.py`（`**/` 被当成必需一层），
    方向一律**偏过覆盖**（宁可多跑，不可漏跑）。
    """
    out = [g]
    if "**/" in g:
        out.append(g.replace("**/", ""))
        out.append(g.replace("**/", "*/"))
    if "**" in g:
        out.append(g.replace("**", "*"))
    return out


def covered(path: str, patterns: Iterable[str]) -> bool:
    """path 是否被 patterns 覆盖：非 glob 按目录前缀；glob 按 fnmatch（含 globstar 变体）。"""
    p = _cmp(path)
    for pat in patterns:
        g = _cmp(pat)
        if not any(ch in g for ch in "*?["):
            if p == g or p.startswith(g.rstrip("/") + "/"):
                return True
        elif any(fnmatch.fnmatchcase(p, v) for v in _glob_variants(g)):
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
        derived, why = derive_skip_safety(root, e)
        stats["facts"][eid]["derived_skip_safety"] = derived
        if derived and e.get("skip_safety") and e["skip_safety"] != derived:
            issues.append("声明级别与推导不符：%s 声明 %s，推导 %s（%s）"
                          % (eid, e["skip_safety"], derived, "; ".join(why[:3])))
        if ob is None:
            continue
        for p in ob:
            if not covered(p, reads):
                issues.append("观测面未声明：%s 的 %s（声明⊄观测=过期）" % (eid, p))
        for p in reads:
            if not any(covered(o, [p]) for o in ob):
                issues.append("声明未观测到：%s 的 %s（观测⊄声明=抽取漏洞或读面已变）" % (eid, p))
    return issues, stats
