#!/usr/bin/env python3
"""职能坐标（ADR-0006）—— 与抽象阶梯轴**正交**的第二轴：核内逐件、核外按规则。

**这是什么**：阶梯轴回答「它在哪一阶」（契约/资产/引擎/出口），本轴回答「它在工坊里干什么」。
实测「阶梯轴对核内零分辨力」：`desktop/src/core` 的 .py **全部**落「引擎」一阶——
所以职能轴不是重复登记，而是**新增信息**。

**七个职能**（封闭集，见 `protocol/LAYERS.json` 的 `roles.vocabulary`）：
`floor`（身份/寻址/注册，两核共用地板）· `prod`（件·装配律·派生）· `verify`（声明·见证·判据）·
`projection`（真源→渲染→落点）· `support`（基础设施）· `app`（实例与内容）· `entry`（入口面）。

**坐标可推导**（ADR-0006 决策 2）：角色由**规则**批量命中（`roles.rules`，先命中先算），
核内件再由**结构信号**逐件收窄；**职能句**一律取自该件**自述**（.py 取模块 docstring 首句）——
即「职能句必须可从证据推导」，不是手填。

**三条可判定性**（ADR-0006 决策 3；并入 check27 的阶梯面，**不新增 check 序号**，遵 ADR-0002）：
1. **全覆盖**：仓库件（`repo_face.walk_repo_paths`）每一件至少命中一个坐标；核内件（floor/prod/verify）
   不得落到兜底规则；核内 `.py` 必须有自述（无自述 = FAIL，因为职能句无处可推）。
2. **规则不漂**：每条规则至少命中 1 件；投影件（`protocol/role_coordinates.json`）与实时重算一致。
3. **核内一致**：`verify` 是**只读判据**——自带写盘入口须在 `roles.write_exceptions` 逐条登记理由
   （未登记的写入口 = FAIL；例外表只许缩小，是待清的投影成本）。

性能纪律：文件面**只枚举一次**（`repo_face.walk_repo_paths` 内含 git 子进程），规则匹配在内存里做。

纪律：纯标准库；只读（唯显式 `write()` 落投影）；同输入同输出。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import atomic_write
from core import repo_face

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
_DOC = re.compile(r'\A(?:[ \t]*(?:#[^\n]*)?\r?\n)*[ \t]*"""([\s\S]*?)"""')
_DOC2 = re.compile(r"\A(?:[ \t]*(?:#[^\n]*)?\r?\n)*[ \t]*'''([\s\S]*?)'''")
#: 自述动词 → 角色（仅用于 `auto` 命中的核内件；解析不出即 `support`）
_VERB = (
    ("prod", re.compile(r"生成|装配|渲染|导出|构建|组合|衍生|排版|编排|装载|打包")),
    ("verify", re.compile(r"判|检|核验|审计|门禁|证据|回执|签名|守卫|对齐|校验|体检|评分|巡检")),
    ("projection", re.compile(r"报告|投影|统计|索引|台账|刷新|基线|派生面")),
    ("support", re.compile(r"加载|解析|存储|缓存|路径|日志|适配|入口|终端|语言|基础|工具|注册|通信|打印|分派|守卫")),
)


def load(root: str = ".") -> Dict[str, Any]:
    """读 `protocol/LAYERS.json` 的 `roles` 段。"""
    p = Path(root) / DECL_REL
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    roles = doc.get("roles")
    return roles if isinstance(roles, dict) else {}


def files_of(root: str = ".") -> List[str]:
    """仓库件面（**只枚举一次**）→ 排序的相对路径列表。"""
    r = Path(root).resolve()
    out = []
    for p in repo_face.walk_repo_paths(root):
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


def self_line(root: str, rel: str) -> str:
    """件的**自述首句**（职能句的唯一来源）：.py 取 docstring / .md 取首标题 / .json 取 note·title·schema。"""
    p = Path(root) / rel
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if rel.endswith(".py"):
        m = _DOC.search(text) or _DOC2.search(text)
        for line in (m.group(1).splitlines() if m else []):
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
            doc = json.loads(text)
        except ValueError:
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
    try:
        text = (Path(root) / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
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


def projection(root: str = ".") -> Dict[str, Any]:
    """生成投影（确定性）：**核内逐件** + 规则批量统计 + 摘要。"""
    roles = load(root)
    # 投影件**不进自己的摘要**（否则写盘/未写盘两态的文件面不同 → 自指漂移，实测踩过）
    files = [x for x in files_of(root) if x != PROJECTION_REL]
    rules = _rule_hits(roles, files)
    overrides = roles.get("overrides") or {}
    entries, counts, rule_counts = {}, {}, {}
    for rel in files:
        c = coordinate(root, rel, rules, overrides)
        key = c["role"] or "(未归类)"
        counts[key] = counts.get(key, 0) + 1
        rule_counts[c["rule"]] = rule_counts.get(c["rule"], 0) + 1
        if c["role"] in KERNEL_ROLES:
            entries[rel] = {"role": c["role"], "function": c["function"], "rule": c["rule"]}
    body = {"schema": SCHEMA, "generated_by": "core.role_model.projection（nf layers --write）",
            "note": "核内（floor/prod/verify）逐件；核外由规则批量覆盖。职能句取自件自述。",
            "counts": counts, "rule_counts": rule_counts, "kernel": entries}
    body["root_digest"] = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return body


def _projection_drift(root: str) -> List[str]:
    """② 投影件 == 实时重算；缺失/过期 → FAIL。"""
    p = Path(root) / PROJECTION_REL
    live = projection(root)
    if not p.is_file():
        return ["② 缺职能坐标投影 %s（修复指引：nf layers --write）" % PROJECTION_REL]
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["② %s 不可读：%s（修复指引：nf layers --write）" % (PROJECTION_REL, exc)]
    if rec.get("root_digest") != live.get("root_digest"):
        return ["② %s 与实时重算不一致（记录 %s / 实测 %s）（修复指引：nf layers --write）"
                % (PROJECTION_REL, str(rec.get("root_digest"))[:12], str(live.get("root_digest"))[:12])]
    return []


def write(root: str = ".") -> str:
    """落盘投影（`nf layers --write` 调用；在仓产物，原子写）。"""
    atomic_write.write_text(Path(root) / PROJECTION_REL,
                            json.dumps(projection(root), ensure_ascii=False,
                                       indent=2, sort_keys=True) + "\n")
    return PROJECTION_REL


def _vocab_issues(roles: Dict[str, Any]) -> List[str]:
    """roles.vocabulary 与实现封闭集一致（声明与实现不许两套词表）。"""
    vocab = [str(v) for v in roles.get("vocabulary") or []]
    if set(vocab) != set(ROLES):
        return ["roles.vocabulary 与实现封闭集不一致（修复指引：与 core/role_model.ROLES 对齐）：%s"
                % sorted(set(ROLES) ^ set(vocab))]
    return []


def _coverage_issues(root: str, files: List[str], rules: List[Dict[str, Any]],
                     overrides: Dict[str, Any]) -> List[str]:
    """① 全覆盖 + 核内逐件：未归类 / 落兜底 / 核内实现面无自述。"""
    issues, uncovered, fallback, no_self = [], [], [], []
    for rel in files:
        c = coordinate(root, rel, rules, overrides)
        if not c["role"]:
            uncovered.append(rel)
            continue
        if c["role"] in KERNEL_ROLES:
            if c["rule"] == "R-catch":
                fallback.append(rel)
            if not c["function"]:
                no_self.append(rel)
    if uncovered:
        issues.append("① 覆盖缺口：%d 件未命中任何坐标（例：%s）（修复指引：补规则或 override）"
                      % (len(uncovered), "、".join(uncovered[:3])))
    if fallback:
        issues.append("① 核内件落兜底规则：%s（修复指引：为核内面补专属规则——兜底不许盖核）"
                      % "、".join(fallback[:3]))
    # 自述要求**按面分档**：核内**实现面**（desktop/src/core）无自述 = FAIL（职能句无处可推）；
    # 测试件与第二实现线（engine/**）无自述 = 计入 stats 的可减缺口（不给测试件灌样板 docstring）。
    core_missing = [x for x in no_self if x.startswith("desktop/src/core/") and x.endswith(".py")]
    if core_missing:
        issues.append("① 核内实现面 .py 无自述（职能句无处可推）：%s（修复指引：补模块 docstring 首句）"
                      % "、".join(core_missing[:3]))
    return issues


def _kernel_issues(root: str, kernel: List[str], rules: List[Dict[str, Any]],
                   overrides: Dict[str, Any], exc: Dict[str, str]
                   ) -> Tuple[List[str], List[str]]:
    """③ 核内一致：verify 是只读判据——自带写盘入口须逐条登记理由（→ issues, writers）。"""
    issues, writers = [], []
    for rel in kernel:
        if not rel.endswith(".py"):
            continue
        if coordinate(root, rel, rules, overrides)["role"] != "verify":
            continue
        try:
            text = (Path(root) / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if writes_disk(text):
            writers.append(rel)
            if rel not in exc:
                issues.append("③ verify 件自带写盘入口未登记：%s（修复指引：在 roles.write_exceptions "
                              "写明理由，或把写入口移出判据面）" % rel)
    stale = sorted(k for k in exc if k not in writers)
    if stale:
        issues.append("③ 写例外已失效：%s（修复指引：从 roles.write_exceptions 删除——例外表只许缩小）"
                      % "、".join(stale[:3]))
    return issues, writers


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """三条可判定性 → (issues, stats)；并入 check27 的阶梯面（R7）。"""
    roles = load(root)
    if not roles:
        return ["protocol/LAYERS.json 缺 roles 段（修复指引：补 vocabulary/rules/overrides）"], {}
    files = files_of(root)
    rules = _rule_hits(roles, files)
    overrides = roles.get("overrides") or {}
    coords = {rel: coordinate(root, rel, rules, overrides) for rel in files}
    kernel = [rel for rel in files if coords[rel]["role"] in KERNEL_ROLES]
    issues = _vocab_issues(roles) + _coverage_issues(root, files, rules, overrides)
    empty = [x["id"] for x in rules if not x["hits"] and x["id"] != "R-catch"]
    if empty:
        issues.append("② 规则空转：%s（修复指引：删规则或改 glob——空规则是腐烂）" % "、".join(empty))
    issues += _projection_drift(root)
    exc = {str(k): str(v) for k, v in (roles.get("write_exceptions") or {}).items()}
    kernel_issues, writers = _kernel_issues(root, kernel, rules, overrides, exc)
    issues += kernel_issues
    stats = {"files": len(files), "kernel": len(kernel), "rules": len(rules),
             "uncovered": sum(1 for c in coords.values() if not c["role"]),
             "kernel_no_self": sum(1 for r in kernel if not coords[r]["function"]),
             "verify_writers": len(writers), "write_exceptions": len(exc)}
    return issues, stats
