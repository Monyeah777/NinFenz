"""core.role_model 私有实现分片 1/2（对外只经 core.role_model 门面导入）：DECL_REL 等"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import json_doc, repo_face

DECL_REL = "protocol/LAYERS.json"


PROJECTION_REL = "protocol/role_coordinates.json"


SCHEMA = "nf-role-coordinates/1"


ROLES = ("floor", "prod", "verify", "projection", "support", "app", "entry")


KERNEL_ROLES = ("floor", "prod", "verify")


#: 写盘入口的名字面（结构判据用 AST，避免把测试件里**字符串样例**误判成写入口）
_WRITE_NAMES = ("write", "refresh", "freeze", "sync", "record", "rewrite")


_SCAN_DEF = re.compile(r"^def scan\(", re.M)


#: 自述正则：允许文件头是**注释行与空行**的任意组合（实测有件在 coding 行后空一行再起 docstring，
#: 早版要求注释紧贴 docstring，把这类件误判成「无自述」）
def _leading_docstring(text: str) -> str:
    """文件头自述（允许注释行/空行在前；两种三引号都认）。

    为什么不用正则（2026-11-09）：原正则被 CodeQL 判为 py/redos（外层重复套可空字符类，
    长注释行有回溯风险）；改手写扫描：逐行跳过注释/空行，复杂度线性、行为逐条等价。
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("#"):
            break
        i += 1
    rest = "\n".join(lines[i:]).lstrip(" \t")
    for quote in ('"""', "'''"):
        if rest.startswith(quote):
            end = rest.find(quote, len(quote))
            if end != -1:
                return rest[len(quote):end]
    return ""


#: 自述动词 → 角色（仅用于 `auto` 命中的核内件；解析不出即 `support`）
_VERB = (
    ("prod", re.compile(r"生成|装配|渲染|导出|构建|组合|衍生|排版|编排|装载|打包")),
    ("verify", re.compile(r"判|检|核验|审计|门禁|证据|回执|签名|守卫|对齐|校验|体检|评分|巡检")),
    ("projection", re.compile(r"报告|投影|统计|索引|台账|刷新|基线|派生面")),
    ("support", re.compile(r"加载|解析|存储|缓存|路径|日志|适配|入口|终端|语言|基础|工具|注册|通信|打印|分派|守卫")),
)


def load(root: str = ".") -> Dict[str, Any]:
    """读 `protocol/LAYERS.json` 的 `roles` 段。"""
    try:
        doc = json_doc.load(Path(root) / DECL_REL, dict, what=DECL_REL)
    except (OSError, ValueError):
        # 可吞：读不出即「无 roles 段」——调用方（scan/coordinate）按缺段如实报缺口，
        # 不是静默放行；此处返回空只表示本件不可用。
        return {}
    roles = doc.get("roles")
    return roles if isinstance(roles, dict) else {}


def files_of(root: str = ".") -> List[str]:
    """仓库件面（**只枚举一次**）→ 排序的相对路径列表。"""
    r = Path(root).resolve()
    out = []
    # 提交投影必须只由 Git-tracked 面决定；测试/工具留下的未跟踪临时件不能改变
    # `protocol/role_coordinates.json`。合成树没有 Git 时回退到完整扫描面，保留单测语义。
    tracked = repo_face.tracked_paths(str(r))
    paths = tracked if tracked else list(repo_face.walk_repo_paths(str(r)))
    for p in paths:
        try:
            out.append(os.path.relpath(str(p), str(r)).replace(os.sep, "/"))
        except ValueError:            # 跨盘符等异常：跳过而非崩（判据另行报缺口）
            continue
    return sorted(out)


def _glob_re(pattern: str) -> re.Pattern:
    """glob → 正则（`**` 跨目录、`*` 不跨；与 `conformance_scan.iter_files` 同语义）。"""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile("^" + out + "$")


def _rule_hits(roles: Dict[str, Any], files: List[str]) -> List[Dict[str, Any]]:
    """每条规则 → {id, role, globs, hits}（在**已枚举**的文件面上匹配，不重复走盘）。"""
    out = []
    for rule in roles.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        hits = set()
        for pat in rule.get("globs") or []:
            rx = _glob_re(str(pat).replace("\\", "/"))
            hits |= {rel for rel in files if rx.match(rel)}
        out.append({"id": str(rule.get("id") or "?"), "role": str(rule.get("role") or ""),
                    "globs": [str(g) for g in rule.get("globs") or []], "hits": hits})
    return out


def writes_disk(text: str) -> bool:
    """该件是否**真**带写盘入口：顶层 `def write/refresh/…` 体内调用 `atomic_write.*`。

    用 AST 而非正则（实测教训）：测试件里把写入口当**样例字符串**写出来时，正则会把测试件本身
    误判成「verify 件自带写盘入口」。
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # 可吞：解析不了 = 没有可证的写盘入口（本判据只认 AST 能证的部分），
        # 语法坏件另有 check12 全量 py_compile 兜着，不在此重复报。
        return False
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in _WRITE_NAMES:
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            f = sub.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and f.value.id == "atomic_write":
                return True
    return False


#: 一次只读扫描内的文本/自述/信号缓存（出口即清；直接调用不复用，防陈旧）。
_TEXT_MEMO: Optional[Dict[Tuple[str, str], Optional[str]]] = None


_SELF_MEMO: Optional[Dict[Tuple[str, str], str]] = None


_SIGNAL_MEMO: Optional[Dict[Tuple[str, str], str]] = None


@contextmanager
def _text_scope():
    """框定一次只读调用：同一文件只读一次、自述/信号只算一次。"""
    global _TEXT_MEMO, _SELF_MEMO, _SIGNAL_MEMO
    outermost = _TEXT_MEMO is None
    if outermost:
        _TEXT_MEMO, _SELF_MEMO, _SIGNAL_MEMO = {}, {}, {}
    try:
        yield
    finally:
        if outermost:
            _TEXT_MEMO = _SELF_MEMO = _SIGNAL_MEMO = None


def _text_of(root: str, rel: str) -> Optional[str]:
    """读文件（作用域内只读一次）；不可读 → None。"""
    global _TEXT_MEMO
    key = (root, rel)
    if _TEXT_MEMO is not None and key in _TEXT_MEMO:
        return _TEXT_MEMO[key]
    try:
        text = (Path(root) / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = None
    if _TEXT_MEMO is not None:
        _TEXT_MEMO[key] = text
    return text


def self_line(root: str, rel: str) -> str:
    """件的**自述首句**（职能句的唯一来源）：.py 取 docstring / .md 取首标题 / .json 取 note·title·schema。"""
    global _SELF_MEMO
    key = (root, rel)
    if _SELF_MEMO is not None and key in _SELF_MEMO:
        return _SELF_MEMO[key]
    result = _self_line_uncached(root, rel)
    if _SELF_MEMO is not None:
        _SELF_MEMO[key] = result
    return result


def _self_line_uncached(root: str, rel: str) -> str:
    text = _text_of(root, rel)
    if text is None:  # 可吞：读不到=无自述可推，① 覆盖判据另报缺口
        return ""
    if rel.endswith(".py"):
        for line in _leading_docstring(text).splitlines():
            if line.strip():
                return line.strip()
        return ""
    if rel.endswith(".md"):
        for line in text.splitlines():
            if line.startswith("#"):
                return line.lstrip("# ").strip()
        return ""
    if rel.endswith(".json"):
        try:
            doc = json_doc.loads(text, what=rel)
        except ValueError:  # 可吞：坏 JSON=无自述可推；坏件由 schema 面另报
            return ""
        if isinstance(doc, dict):
            for k in ("note", "title", "schema", "id"):
                v = doc.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#") and len(s) > 1:
            return s.lstrip("# ").strip()
    return ""


def _signal_role(root: str, rel: str) -> str:
    """核内件的**逐件收窄**：结构信号优先（可证），自述动词兜底（可驳）。"""
    global _SIGNAL_MEMO
    key = (root, rel)
    if _SIGNAL_MEMO is not None and key in _SIGNAL_MEMO:
        return _SIGNAL_MEMO[key]
    result = _signal_role_uncached(root, rel)
    if _SIGNAL_MEMO is not None:
        _SIGNAL_MEMO[key] = result
    return result


def _signal_role_uncached(root: str, rel: str) -> str:
    text = _text_of(root, rel)
    if text is None:
        return "support"
    if rel.rsplit("/", 1)[-1].startswith("registry"):
        return "floor"
    if _SCAN_DEF.search(text):
        return "verify"          # 判据入口 = 只读面（自带写入口由写例外表逐条登记）
    if writes_disk(text):
        return "projection"
    doc = self_line(root, rel)
    for role, rx in _VERB:
        if rx.search(doc):
            return role
    # 解析不出的核内件按「件（prod）」算——**不许拿 support 当躲避核内要求的后门**：
    # support 不是核内角色，落进去等于同时逃过「逐件职能句」与「核内一致」两条判据。
    return "prod"


def coordinate(root: str, rel: str, rules: List[Dict[str, Any]],
               overrides: Dict[str, Any]) -> Dict[str, Any]:
    """单件坐标 → {role, rule, function}（override > 规则 > 兜底；`auto` 再走信号）。"""
    ov = overrides.get(rel)
    if isinstance(ov, dict) and ov.get("role"):
        return {"role": str(ov["role"]), "rule": "override", "function": self_line(root, rel)}
    role, rule = "", ""
    for r in rules:
        if rel in r["hits"]:
            role, rule = r["role"], r["id"]
            break
    if role == "auto":
        role, rule = _signal_role(root, rel), "auto:" + rule
    return {"role": role, "rule": rule, "function": self_line(root, rel)}


def _projection_impl(root: str = ".") -> Dict[str, Any]:
    roles = load(root)
    # 投影件**不进自己的摘要**（否则写盘/未写盘两态的文件面不同 → 自指漂移，实测踩过）
    files = [x for x in files_of(root) if x != PROJECTION_REL]
    rules = _rule_hits(roles, files)
    overrides = roles.get("overrides") or {}
    entries: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    rule_counts: Dict[str, int] = {}
    for rel in files:
        c = coordinate(root, rel, rules, overrides)
        key = c["role"] or "(未归类)"
        counts[key] = counts.get(key, 0) + 1
        rule_counts[c["rule"]] = rule_counts.get(c["rule"], 0) + 1
        if c["role"] in KERNEL_ROLES:
            # 用**对象列表**而非「路径→值」字典：路径里含 `+` 等越界字符，而本仓 identity 卫生
            # 判据对 JSON **键**有字符集约束（实测 34 条红）——键面不放路径。
            entries.append({"path": rel, "role": c["role"],
                            "function": c["function"], "rule": c["rule"]})
    body = {"schema": SCHEMA, "generated_by": "core.role_model.projection（nf layers --write）",
            "note": "核内（floor/prod/verify）逐件；核外由规则批量覆盖。职能句取自件自述。",
            "counts": counts, "rule_counts": rule_counts, "kernel": entries}
    body["root_digest"] = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return body


def projection(root: str = ".") -> Dict[str, Any]:
    """生成投影（确定性）：**核内逐件** + 规则批量统计 + 摘要。"""
    with _text_scope():
        return _projection_impl(root)
