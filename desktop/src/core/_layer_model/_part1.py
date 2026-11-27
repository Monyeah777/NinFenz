"""core.layer_model 私有实现分片 1/3（对外只经 core.layer_model 门面导入）：DECL_REL 等"""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import json_doc

# 导入闭包指纹：由调用方算（持久层不再反向依赖解析层，见 2026-09-29 拆环）

DECL_REL = "protocol/LAYERS.json"


SCHEMA = "nf-layers/1"


DOC_REL = "docs/layers.md"


VERIFY_REL = "verify.sh"


ASSERTIONS_REL = "protocol/assertions.json"


MARK_BEGIN = "<!-- nf:layers:begin -->"


MARK_END = "<!-- nf:layers:end -->"


#: 引擎阶不得反向 import 的入口面模块名（入口可替换，真源不行）
ENTRY_MODULE_NAMES = ("nf", "scripts")


_CHECK_DEF = re.compile(r"^check(\d+)\(\)\{", re.M)


_JUDGE_CHECK = re.compile(r"^check(\d+)$")


_JUDGE_ASSERTION = "assertion:"


#: L6 的**文本预筛**：只把含入口面 import 的文件交给 AST（避免全量解析，见 _rule_issues）
_ENTRY_IMPORT_RE = re.compile(r"\b(?:import|from)\s+(?:nf|scripts)\b")


#: L6 的**逐件**事实缓存（键 = 该件正文的 sha256；值 = [(行号, 顶层模块名), …]）。
#: 依据（实测 2026-09-29）：L6 每次要把 255 份 `desktop/src/core/*.py`（约 2 MB）读进来再做 AST
#: walk，而「本件是否 import nf/scripts」只是**该件正文**的纯函数 ⇒ 与引擎无关的改动整笔可省。
_ENTRY_IMPORT_CACHE: Dict[str, List[Tuple[int, str]]] = {}


_ENTRY_IMPORT_CACHE_MAX = 4096


def _entry_imports(text: str) -> List[Tuple[int, str]]:
    """`text` 对入口面（`nf` / `scripts`）的 import 清单 `(行号, 顶层模块名)`；键即内容。

    等价性由 `test_layer_model.EntryImportFactTest` 守着：用**未缓存的参考实现**（原先那段
    「预筛 + `ast.parse` + `ast.walk`」原样搬进测试）在真仓库全部 core/*.py 上逐件比对，
    并在合成树上验证**顺序与重复项都不丢**（一件同时 import nf 与 scripts 必须出两条）。
    """
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    hit = _ENTRY_IMPORT_CACHE.get(key)
    if hit is not None:
        return hit
    out: List[Tuple[int, str]] = []
    if _ENTRY_IMPORT_RE.search(text):          # 文本预筛：绝大多数件不含入口 import
        try:
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                else:
                    names = []
                for name in names:
                    if name in ENTRY_MODULE_NAMES:
                        out.append((getattr(node, "lineno", 0), name))
    if len(_ENTRY_IMPORT_CACHE) >= _ENTRY_IMPORT_CACHE_MAX:
        _ENTRY_IMPORT_CACHE.clear()
    _ENTRY_IMPORT_CACHE[key] = out
    return out


def _pattern_to_regex(pattern: str):
    """glob → **逐段**正则（`**` 跨目录、`*` 不跨、`?` 单字符）——只在本相对路径上匹配。

    末尾 `**` 的 pathlib 语义是「本级及其下全部**目录**」——本函数只取文件，故等价于**空集**。
    此前漏了这条：`**` 被译成「任意串」⇒ 快路径把全仓文件都算进面，而参考实现（Path.glob +
    is_file）给空集——实测 66217 vs 0。隐面大缓存树（如 .rivet/scratch）会把这条差异放大成红。
    """
    if pattern == "**" or pattern.endswith("/**"):
        return re.compile(r"(?!)")            # 永不匹配文件（末尾 ** 只指目录）
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                out.append(".*")
                i += 2
                if i < len(pattern) and pattern[i] == "/":
                    i += 1
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def load(root: str = ".") -> Dict[str, Any]:
    """读阶梯真源；缺件或 schema 不符 → 抛带修复指引的错误（不静默降级）。"""
    path = Path(root) / DECL_REL
    if not path.is_file():
        raise ValueError("缺阶梯真源 %s（修复指引：先落该件再跑 nf layers --verify）"
                         % DECL_REL)
    try:
        doc = json_doc.load(path, dict, what=DECL_REL)
    except ValueError as exc:
        raise ValueError("阶梯真源 %s 不是合法 JSON：%s（修复指引：修 JSON 语法后重跑）"
                         % (DECL_REL, exc)) from exc
    if str(doc.get("schema") or "") != SCHEMA:
        raise ValueError("阶梯真源 schema 不匹配（期望 %s；修复指引：核对 schema 字段）"
                         % SCHEMA)
    return doc


def _expand(root: str, globs) -> set:
    """展开 glob → 仓库相对路径集合（只取文件；确定性排序无关，返回集合）。"""
    out = set()
    base = Path(root)
    for pattern in globs or []:
        for p in base.glob(str(pattern)):
            if p.is_file():
                out.add(p.relative_to(base).as_posix())
    return out


def _is_glob(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def _glob_root(pattern: str) -> str:
    """pattern 中**通配符之前**的固定目录前缀（无则 `.`）——用于「同子树只走一次」。"""
    parts = str(pattern).split("/")
    keep: List[str] = []
    for part in parts[:-1] if len(parts) > 1 else []:
        if _is_glob(part):
            break
        keep.append(part)
    return "/".join(keep) if keep else "."


def _walk_files(base: Path, rel_root: str) -> List[str]:
    """收集 rel_root 子树下全部文件的**仓库相对 posix 路径**（走共享子树索引）。

    依据（实测）：本函数原本自己 `os.walk`，而一次 `evaluate` 里 `community` 这棵树被
    layer_model、两个指纹、若干扫描器**各走了一遍**——一次 evaluate 共建了 5403 个
    `os.scandir`，光建扫描器就 687 ms。改走 `conformance_scan.tree_files`（作用域内按目录
    记忆、出口即清）后同一棵树只走一遍，其他调用方直接复用清单。
    """
    from core import conformance_scan as _csc
    return _csc.tree_files(str(base), "" if rel_root in (".", "") else rel_root)


def _expand_one(base: Path, pattern: str, ref_root: str, cache: dict) -> set:
    """单个 glob 的等价快路径：固定件直接探在不在，通配件走子树索引 + 正则。"""
    if not _is_glob(pattern):
        return {pattern} if (base / pattern).is_file() else set()
    if "[" in pattern:                    # 字符类等 Path.glob 专有语义 → 回退参考实现
        return _expand(ref_root, [pattern])
    rel_root = _glob_root(pattern)
    key = ("tree", rel_root)
    if key not in cache:
        cache[key] = _walk_files(base, rel_root)
    rx = _pattern_to_regex(pattern)
    return {rel for rel in cache[key] if rx.match(rel)}


def _expand_many(root: str, globs, cache: dict) -> set:
    """同一次扫描内按 pattern 缓存展开（**每个子树只走一次文件系统**）。

    效率（实测）：`_rule_issues` 的 L1/L2/L3 会重复展开同一批 glob（约 10.5k 次 `stat`
    全花在这里）。两层缓存：① 每个子树的文件清单只 `os.walk` 一次；② 每个 pattern 的
    匹配结果复用。缓存是**每次扫描一份**（不是模块级），所以临时目录/被改动的树不会被
    陈旧结果污染（单测反复扫同一路径也不受影响）。等价性由 `_expand`（参考实现）兜底：
    字符类等 Path.glob 专有语义直接回退，其余由 `test_layer_model` 的等价断言守住。
    """
    base = Path(root)
    out = set()
    for pattern in globs or []:
        key = ("pat", str(pattern))
        if key not in cache:
            cache[key] = _expand_one(base, str(pattern), str(root), cache)
        out |= cache[key]
    return out


def _exists(root: str, rel: str) -> bool:
    return (Path(root) / str(rel)).exists()


def _derived_files(root: str, doc: Dict[str, Any], cache: Optional[dict] = None) -> set:
    if cache is None:
        return _expand(root, doc.get("derived") or [])
    return _expand_many(root, doc.get("derived") or [], cache)


def tier_faces(root: str, doc: Dict[str, Any]) -> Dict[str, set]:
    """每阶真源面（已扣除派生物）→ {tier_id: {rel, …}}。"""
    cache: dict = {}
    derived = _derived_files(root, doc, cache)
    out = {}
    for tier in doc.get("tiers") or []:
        out[str(tier.get("id"))] = \
            _expand_many(root, (tier.get("source") or {}).get("globs"), cache) - derived
    return out


def _obj(v: Any) -> dict:
    """空值回退单点（真源 face 的「or {}」；radon 把每处 or 记为一个分支）。"""
    return v if isinstance(v, dict) else {}


def _arr(v: Any) -> list:
    """空值回退单点（真源 face 的「or []」）。"""
    return v if isinstance(v, list) else []


def _rule_l1_assets(root: str, doc: Dict[str, Any], tier_ids: List[str],
                    cache: dict, issues: List[str]) -> None:
    """L1 资产子级：真源面非空 + tier 在阶名单。"""
    for lv in _arr(doc.get("asset_levels")):
        if not _expand_many(root, lv.get("globs"), cache):
            issues.append("L1 资产子级 %s 的真源面为空：%s（修复指引：核对 globs）"
                          % (lv.get("id"), lv.get("globs")))
        if str(lv.get("tier") or "") not in tier_ids:
            issues.append("L1 资产子级 %s 的 tier 不在阶名单：%s（修复指引：改成真实阶 id）"
                          % (lv.get("id"), lv.get("tier")))


def _rule_l1_files(root: str, doc: Dict[str, Any], issues: List[str]) -> None:
    """L1 入口件与纵切件都必须真实存在。"""
    for sf in _arr(doc.get("surfaces")):
        for rel in _arr(sf.get("entries")):
            if not _exists(root, rel):
                issues.append("L1 入口面 %s 的入口件不存在：%s（修复指引：补件或改成真实路径）"
                              % (sf.get("id"), rel))
    for comp in _arr(_obj(doc.get("crosscut")).get("components")):
        if not _exists(root, comp.get("artifact")):
            issues.append("L1 纵切件 %s 不存在：%s（修复指引：补件或改成真实路径）"
                          % (comp.get("id"), comp.get("artifact")))


def _rule_l1(root: str, doc: Dict[str, Any], tier_ids: List[str], cache: dict,
             issues: List[str]) -> None:
    """L1 真源在位：阶/资产子级/入口件/纵切件都能展开或落盘。"""
    for tier in _arr(doc.get("tiers")):
        globs = _obj(tier.get("source")).get("globs")
        face = _expand_many(root, globs, cache)
        if not globs:
            issues.append("L1 阶 %s 未声明真源面（修复指引：在 source.globs 写明真源落点）"
                          % tier.get("id"))
        elif not face:
            issues.append("L1 阶 %s 的真源面展开为空：%s（修复指引：核对 globs 与实况）"
                          % (tier.get("id"), globs))
    _rule_l1_assets(root, doc, tier_ids, cache, issues)
    _rule_l1_files(root, doc, issues)
