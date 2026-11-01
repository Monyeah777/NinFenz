"""断言表 runner（数据化断言，机制借鉴 Schematron 的 patterns→rules→assertions）。

真源 `protocol/assertions.json`：每条断言 = id / severity / kind / params / message / fix，
外加 **capability**（该断言服务哪个判定能力）。**kind 是封闭集**（四个），只做确定性形状判定；
不引入第三方依赖、不自造 DSL。能力面另由同表的 `capability_vocabulary` + `capability_index`
声明（能力的单一真源仍在本表——**不新建 capabilities.json**，见设计文档 §5.3）。

边界（写在声明里，这里也钉一遍）：
- 只搬「已在别处被判定过的形状类断言」，不在这里新增语义政策；
- 业务语义断言（需要上下文推理的）留在 check 代码里；
- 每条断言必须有 fix——没有修复指引的断言不许入表。
"""
from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import json_doc
from core import redos_scan

DECL_REL = "protocol/assertions.json"
SCHEMA = "nf-assertions/1"
SEVERITIES = ("fail", "warn")
REQUIRED = ("id", "severity", "kind", "params", "message", "fix")
MAX_ASSERT_FILE_BYTES = 8 * 1024 * 1024
MAX_PATTERN_CHARS = 4096
_NESTED_QUANTIFIER = re.compile(r"\(([^()]*)\)\s*(?:[+*]|\{\d*,?\d*\})")


@functools.lru_cache(maxsize=256)
def _compiled(pattern: str) -> re.Pattern[str]:
    """断言正则只编译一次（模式是纯函数）。"""
    if len(pattern) > MAX_PATTERN_CHARS:
        raise ValueError("正则过长（%d > %d）（修复指引：拆分断言或改用有界字符类）"
                         % (len(pattern), MAX_PATTERN_CHARS))
    if re.search(r"\\[1-9]", pattern):
        raise ValueError("正则含反向引用（回溯风险，封闭集不允许；修复指引：改写为无反向引用的模式）")
    shape = redos_scan.suspicious_nesting(pattern)
    if shape:
        raise ValueError("正则含量词套量词（ReDoS 风险，封闭集不允许；修复指引：增加强制分隔符）：%s"
                         % shape)
    for match in _NESTED_QUANTIFIER.finditer(pattern):
        body = match.group(1)
        if "|" in body or re.search(r"(?:[+*]|\{\d*,?\d*\})", body):
            raise ValueError("正则含嵌套重复/歧义分支（ReDoS 风险，封闭集不允许）：%s"
                             % match.group(0))
    return re.compile(pattern)


def _read_bounded(path: Path) -> Tuple[str | None, str | None]:
    """有上限地读文本 → (text, error)；超过上限/不可读一律 fail-closed。"""
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, "不可读：%s" % exc
    if size > MAX_ASSERT_FILE_BYTES:
        return None, "文件过大（%d > %d 字节）" % (size, MAX_ASSERT_FILE_BYTES)
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as exc:
        return None, "不可读：%s" % exc


def load(root: str = ".") -> Dict[str, Any]:
    p = Path(root) / DECL_REL
    return json_doc.load(p, dict, what=DECL_REL) if p.is_file() else {}


def _glob(root: str, pattern: str) -> List[str]:
    r = Path(root)
    if any(ch in pattern for ch in "*?["):
        return sorted(str(p) for p in r.glob(pattern) if p.is_file())
    p = r / pattern
    return [str(p)] if p.is_file() else []


def _k_regex_absent(root: str, params: Dict[str, Any]) -> Tuple[bool, str]:
    pat = _compiled(str(params.get("pattern") or ""))
    hits = []
    for g in params.get("globs") or []:
        for f in _glob(root, str(g)):
            text, err = _read_bounded(Path(f))
            if err is not None:
                return False, "%s：%s" % (f, err)
            if pat.search(text or ""):
                hits.append(f)
                return False, "命中：%s" % f
    return (not hits, "零命中" if not hits else "命中：%s" % ", ".join(hits[:2]))


def _k_regex_present(root: str, params: Dict[str, Any]) -> Tuple[bool, str]:
    path = Path(root) / str(params.get("path") or "")
    if not path.is_file():
        return False, "目标件不存在：%s" % params.get("path")
    text, err = _read_bounded(path)
    if err is not None:
        return False, "%s：%s" % (params.get("path"), err)
    miss = [p for p in (params.get("patterns") or []) if p not in text]
    return (not miss, "%d 锚点齐" % len(params.get("patterns") or [])
            if not miss else "缺：%s" % ", ".join(miss[:3]))


def _k_count_at_least(root: str, params: Dict[str, Any]) -> Tuple[bool, str]:
    n = len(_glob(root, str(params.get("glob") or "")))
    want = int(params.get("min") or 0)
    return (n >= want, "%d ≥ %d" % (n, want))


def _k_json_value(root: str, params: Dict[str, Any]) -> Tuple[bool, str]:
    path = Path(root) / str(params.get("path") or "")
    if not path.is_file():
        return False, "目标件不存在：%s" % params.get("path")
    text, err = _read_bounded(path)
    if err is not None:
        return False, "%s：%s" % (params.get("path"), err)
    try:
        doc = json_doc.loads(text or "", None, what=str(path))
    except ValueError as exc:
        return False, "JSON 不可解析：%s" % exc
    cur: Any = doc
    for part in str(params.get("key") or "").split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, "缺键：%s" % params.get("key")
        cur = cur[part]
    op = str(params.get("op") or "")
    val = params.get("value")
    if op == "exists":
        return True, "键在场"
    if op == "nonempty":
        ok = bool(cur)
        return (ok, "非空" if ok else "空值")
    if op == "equals":
        return (cur == val, "= %s" % val)
    if op == "in_vocab":
        ok = cur in (val or [])
        return (ok, "%s ∈ 词表" % cur if ok else "%s 越词表" % cur)
    if op == "contains_keys":
        miss = [k for k in (val or []) if k not in (cur or {})]
        return (not miss, "键齐" if not miss else "缺：%s" % ", ".join(miss))
    return False, "未知 op：%s（封闭集：exists/nonempty/equals/in_vocab/contains_keys）" % op


KINDS = {"regex_absent": _k_regex_absent, "regex_present": _k_regex_present,
         "count_at_least": _k_count_at_least, "json_value": _k_json_value}

#: 聚合门能力：32/33/35/36 是「能力的组合器」，不是能力本身（设计文档 §2.3 反模式）。
#: 它必须**显式在册**（否则聚合门的存在成了隐形的），但不计入能力覆盖面。
AGGREGATE_CAPABILITY = "CAP_AGGREGATE_SUMMARY"


def verify_sh_checks(root: str = ".") -> set:
    """verify.sh 里**实际存在**的 check 号集合（能力覆盖面的判定基准，不写死「40」）。"""
    try:
        text = (Path(root) / "verify.sh").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    return {int(m) for m in re.findall(r"(?m)^check(\d+)\s*\(\)", text)}


def capability_report(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """能力面体检：能力词表 × 能力索引 × 断言挂账 × verify.sh 实有 check → (issues, stats)。

    判据（每条都能红；变异例见 tests/test_assertions.py）：

    - 声明了能力词表后，**每条断言**都必须挂一个词表内的能力（未挂 = 覆盖面漏记）；
    - **每个能力**至少压住一条 check（没有 check 的能力 = 图纸，不可判定）；
    - 能力索引引用的 check 号必须在 verify.sh 里**真实存在**（防索引自说自话）；
    - verify.sh 的**每条 check** 至少被一个能力覆盖（空洞检测）；
    - 聚合器 `CAP_AGGREGATE_SUMMARY` 必须显式在册（它是反模式，不能隐身）。

    设计取向：覆盖面按 **check** 算，不按断言条数算——能力定义自 check 集（设计文档 §4.2），
    断言表只是「形状类断言」的搬运面，拿 22 条断言去凑 16 个能力只会让挂账变成注水。
    """
    doc = load(root)
    vocab = [str(c) for c in (doc.get("capability_vocabulary") or [])]
    if not vocab:
        return [], {"declared": False}
    issues: List[str] = []
    index = doc.get("capability_index") or {}
    if not isinstance(index, dict):
        return ["能力索引须是对象（capability → check 号列表）"], {"declared": True}
    if AGGREGATE_CAPABILITY not in vocab:
        issues.append("能力词表缺聚合器 %s（32/33/35/36 是能力的组合器，必须显式在册）"
                      % AGGREGATE_CAPABILITY)
    numbers = set()
    for cap in vocab:
        nums = index.get(cap)
        if not isinstance(nums, list) or not nums:
            issues.append("能力 %s 没有任何 check（空能力不可判定；修复指引：在 capability_index "
                          "补该能力压住的 check 号）" % cap)
            continue
        bad = [n for n in nums if not isinstance(n, int) or isinstance(n, bool)]
        if bad:
            issues.append("能力 %s 的 check 号须是整数：%s" % (cap, bad[:3]))
        numbers.update(n for n in nums if isinstance(n, int) and not isinstance(n, bool))
    declared_checks = verify_sh_checks(root)
    real = [c for c in vocab if c != AGGREGATE_CAPABILITY]
    covered = set()
    for cap in real:
        covered.update(n for n in (index.get(cap) or []) if isinstance(n, int))
    if declared_checks:
        unknown = sorted(numbers - declared_checks)
        if unknown:
            issues.append("能力索引引用了 verify.sh 里不存在的 check：%s（修复指引：核对 check 号"
                          "是否随退役/重排变化）" % ", ".join(str(n) for n in unknown[:6]))
        holes = sorted(declared_checks - numbers)
        if holes:
            issues.append("能力空洞：check %s 未被任何能力覆盖（修复指引：在 capability_index 里"
                          "给该 check 挂能力，或明确它属于聚合器）"
                          % ", ".join(str(n) for n in holes[:8]))
    rows = doc.get("assertions") or []
    missing = [str(a.get("id") or "(无名)") for a in rows if not a.get("capability")]
    if missing:
        issues.append("断言未挂能力：%s%s（修复指引：为每条断言在 capability 里选一个词表内的能力）"
                      % (", ".join(missing[:4]),
                         " 等 %d 条" % len(missing) if len(missing) > 4 else ""))
    off = sorted({str(a.get("capability")) for a in rows
                  if a.get("capability") and str(a.get("capability")) not in vocab})
    if off:
        issues.append("断言的 capability 越词表：%s" % ", ".join(off[:4]))
    stats: Dict[str, Any] = {
        "declared": True,
        "capabilities": len(real),
        "aggregate_present": AGGREGATE_CAPABILITY in vocab,
        "checks": len(declared_checks),
        "covered": len(declared_checks & numbers),
        "assertions": len(rows),
        "mapped_assertions": sum(1 for a in rows if a.get("capability")),
    }
    if declared_checks:
        stats["aggregate_only"] = sorted(declared_checks - covered)
    return issues, stats


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """断言表自身的合法性（防"表里塞了跑不动的断言"）。"""
    issues: List[str] = []
    doc = load(root)
    if not doc:
        return ["缺断言表 %s" % DECL_REL], {}
    if str(doc.get("schema") or "") != SCHEMA:
        issues.append("断言表 schema 不匹配（期望 %s）" % SCHEMA)
    if tuple(doc.get("severity_vocabulary") or ()) != SEVERITIES:
        issues.append("severity 词表与判据不一致（期望 %s）" % "/".join(SEVERITIES))
    if tuple(doc.get("kind_vocabulary") or ()) != tuple(KINDS):
        issues.append("kind 词表必须与 runner 封闭集逐项一致（%s）" % "/".join(KINDS))
    seen = set()
    for a in doc.get("assertions") or []:
        aid = str(a.get("id") or "")
        for k in REQUIRED:
            if not a.get(k) and a.get(k) != {}:
                issues.append("断言 %s 缺必填字段：%s" % (aid or "(无名)", k))
        if aid in seen:
            issues.append("断言 id 重复：%s" % aid)
        seen.add(aid)
        if str(a.get("severity")) not in SEVERITIES:
            issues.append("断言 %s severity 越词表：%s" % (aid, a.get("severity")))
        if str(a.get("kind")) not in KINDS:
            issues.append("断言 %s kind 不在封闭集：%s" % (aid, a.get("kind")))
        elif str(a.get("kind")) == "regex_absent":
            try:
                _compiled(str((a.get("params") or {}).get("pattern") or ""))
            except (ValueError, re.error) as exc:
                issues.append("断言 %s 的正则不可安全执行：%s" % (aid, exc))
        if not str(a.get("fix") or "").strip():
            issues.append("断言 %s 缺 fix（无修复指引不许入表）" % aid)
    cap_issues, cap_stats = capability_report(root)
    issues.extend(cap_issues)
    stats = {"assertions": len(doc.get("assertions") or [])}
    if cap_stats.get("declared"):
        stats["capabilities"] = cap_stats
    return issues, stats


def run(root: str = ".") -> Tuple[List[Dict[str, Any]], List[str]]:
    """跑全部断言 → (results, issues)。results 每项含 ok/severity/kind/detail。"""
    decl_issues, _stats = scan(root)
    issues = list(decl_issues)
    results: List[Dict[str, Any]] = []
    for a in load(root).get("assertions") or []:
        kind = str(a.get("kind"))
        fn = KINDS.get(kind)
        if fn is None:
            issues.append("断言 %s 的 kind 不在封闭集：%s" % (a.get("id"), kind))
            continue
        try:
            ok, detail = fn(root, a.get("params") or {})
        except Exception as exc:                      # 断言自身异常 = 该条不通过
            ok, detail = False, "断言执行异常：%s" % exc
        results.append({"id": a.get("id"), "severity": a.get("severity"), "kind": kind,
                        "ok": bool(ok), "detail": detail, "message": a.get("message"),
                        "fix": a.get("fix"), "evidence": a.get("evidence"),
                        "capability": a.get("capability")})
        if not ok and str(a.get("severity")) == "fail":
            issues.append("%s 不通过：%s（修复指引：%s）"
                          % (a.get("id"), detail, a.get("fix")))
    return results, issues
