"""asset_contract 私有子模块 _code：代码面：禁用调用 / 测试件在场 / 第二实现结构契约 / 告警面。

门面 core.asset_contract 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from ._ast import _none_deref
from ._base import _read, resolve



def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return "%s.%s" % (base, node.attr) if base else node.attr
    return ""



def _denied_calls(tree: ast.AST, rel: str, deny: set) -> List[str]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = _dotted(n.func)
            if name and name in deny:
                out.append("代码件 %s 第 %d 行调用了禁用面 %s（修复指引：换用不执行任意代码的等价实"
                    "现；"
                           "确需保留须改声明并写明理由）" % (rel, n.lineno, name))
    return out



def _check_tests(root: str, rel: str, spec: Dict[str, Any]) -> List[str]:
    issues = []
    stem = Path(rel).stem
    if not spec.get("tests"):
        issues.append("代码件 %s 未声明测试件（修复指引：补 tests 列表——没有用例的代码资产不算"
                      "通过测试）" % rel)
    for t in spec.get("tests") or []:
        trel = str(t).replace("\\", "/")
        p = Path(root) / trel
        if not p.is_file():
            issues.append("代码件 %s 声明的测试件不在场：%s（修复指引：先写测试再登记）" % (rel,
 trel))
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        try:
            ast.parse(text)
        except SyntaxError as exc:
            issues.append("测试件 %s 语法坏：%s（修复指引：先修语法）" % (trel, exc))
            continue
        if stem not in text:
            issues.append("测试件 %s 未点名被测模块 %s（修复指引：在测试里 import 或引用该模块）"
                          % (trel, stem))
    return issues



def _forbid_rule_issues(sid: str, rule: dict, texts: list,
                        stats: Dict[str, Any]) -> List[str]:
    """单条 `forbid_regex` 规则：命中行号 + 计数入 stats。"""
    rx = re.compile(str(rule.get("pattern") or ""))
    hits = ["%s:%d" % (rel, text.count(chr(10), 0, m.start()) + 1)
            for rel, text in texts for m in rx.finditer(text)]
    stats["forbid:%s" % rule.get("name")] = len(hits)
    if hits:
        return ["代码契约 %s 命中禁用式 %s（%d 处，例 %s）（修复指引：%s）"
                % (sid, rule.get("name"), len(hits), "、".join(hits[:3]),
                   rule.get("why") or "换成不越界的等价实现")]
    return []


def _limit_rule_issues(sid: str, rule: dict, texts: list,
                       stats: Dict[str, Any]) -> List[str]:
    """单条 `regex_limits` 规则：计数入 stats，超上限判 FAIL（棘轮只减不增）。"""
    rx = re.compile(str(rule.get("pattern") or ""))
    n = sum(len(rx.findall(text)) for _rel, text in texts)
    cap = int(rule.get("max") or 0)
    stats["limit:%s" % rule.get("name")] = n
    if n > cap:
        return ["代码契约 %s 的 %s 计数 %d > 上限 %d（棘轮只减不增）"
                "（修复指引：先降后改声明）" % (sid, rule.get("name"), n, cap)]
    return []


def _code_structural(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """第二实现线的**结构契约**（E2）：不做完整 AST，只判可证的正则面（禁用式 / 计数上限）。

    为什么：`engine/**` 在职能坐标里是 verify（只读判据的第二实现），而代码面此前只有 Python AST。
    完整 Rust/C# 语法树不在本层能力内（ADR-0005 的范围划分），故只声明**范围**与**只减不增**的计数——
    这比「装作 AST 判过」诚实，也比不判多一层门。
    """
    sid = str(spec.get("id") or "?")
    rels = resolve(root, spec)
    if not rels:
        return ["代码契约 %s 未命中任何文件（修复指引：修正 path/glob）" % sid], {"files": 0}
    texts = []
    for rel in rels:
        text, err = _read(root, rel)
        if err:
            return [err], {"files": len(rels)}
        texts.append((rel, text))
    issues: List[str] = []
    stats: Dict[str, Any] = {"files": len(rels)}
    for rule in spec.get("forbid_regex") or []:
        issues += _forbid_rule_issues(sid, rule, texts, stats)
    for rule in spec.get("regex_limits") or []:
        issues += _limit_rule_issues(sid, rule, texts, stats)
    return issues, stats



# ---------------------------------------------------------------- 代码面·告警面（WARN）
def _line_no(text: str, pos: int) -> int:
    """字符偏移 → 1 基行号（与 ruff/编译器同口径）。"""
    return text.count(chr(10), 0, pos) + 1



def _warn_cut(text: str, rule: dict) -> int:
    """`skip_after` 标记之前的区域才判（测试区是脚手架，不是出口契约）。"""
    skip_after = str(rule.get("skip_after") or "")
    cut = text.find(skip_after) if skip_after else -1
    return len(text) if cut < 0 else cut



def _is_code_line(line: str) -> bool:
    """该行是否为**代码**（不是注释/文档）——规则只判代码，避免被注释里的词自命中。"""
    s = line.strip()
    if not s:
        return False
    return not (s.startswith("//") or s.startswith("/*") or s.startswith("*")
                or s.startswith("///") or s.startswith("//!"))



def _warn_unsafe_safety(sid: str, rel: str, text: str, rule: dict) -> list[str]:
    """规则①：每处 `unsafe` 前 within 行内必须有 SAFETY: 注释（说明调用方前置条件）。

    只判**代码行**上的 `unsafe`：注释里提到 unsafe（含 SAFETY: 注释自身）不算出口面。
    """
    rx = re.compile(str(rule.get("pattern") or r"\bunsafe\b"))
    marker = str(rule.get("marker") or "SAFETY:")
    within = int(rule.get("within") or 3)
    cut = _warn_cut(text, rule)
    lines = text.splitlines()
    out: list[str] = []
    for m in rx.finditer(text):
        if m.start() >= cut:
            break
        ln = _line_no(text, m.start())
        if not _is_code_line(lines[ln - 1]):
            continue
        lo = max(0, ln - 1 - within)
        if not any(marker in lines[i] for i in range(lo, ln - 1)):
            out.append(f"代码契约 {sid} 告警：{rel}:{ln} 的 unsafe 前 {within} 行内缺 "
                       f"{marker} 注释（修复指引：在 unsafe 块/签名紧邻上方写"
                       f"「{marker} 调用方前置条件」，让审查面可读）")
    return out



def _warn_null_guard(sid: str, rel: str, text: str, rule: dict) -> list[str]:
    """规则②：每处 `from_raw_parts` 前 within 行内必须有空指针检查（只判代码行）。"""
    rx = re.compile(str(rule.get("pattern") or "from_raw_parts"))
    guard = str(rule.get("guard") or "is_null")
    within = int(rule.get("within") or 20)
    cut = _warn_cut(text, rule)
    lines = text.splitlines()
    out: list[str] = []
    for m in rx.finditer(text):
        if m.start() >= cut:
            break
        ln = _line_no(text, m.start())
        if not _is_code_line(lines[ln - 1]):
            continue
        lo = max(0, ln - 1 - within)
        if not any(guard in lines[i] for i in range(lo, ln - 1)):
            out.append(f"代码契约 {sid} 告警：{rel}:{ln} 的 from_raw_parts 前 {within} 行内"
                       f"无空指针检查（修复指引：先 `if ptr.is_null() {{ return 0; }}` 再构造"
                       f"切片——null 即使 len=0 也是 UB）")
    return out



def _export_span_hits(sid: str, rel: str, lines: list, text: str, span: tuple,
                      forbid: list) -> list[str]:
    """一个导出面区块内的禁用词命中（只看代码行）。"""
    span_start, span_end = span
    ln = _line_no(text, span_start)
    out: list[str] = []
    for offset, line in enumerate(lines[ln - 1:_line_no(text, max(span_end - 1, span_start))]):
        if not _is_code_line(line):
            continue
        for bad in forbid:
            if bad in line:
                out.append(f"代码契约 {sid} 告警：{rel}:{ln + offset} 起的导出面含 "
                           f"{bad!r}（修复指引：C ABI 出口以错误码返回，"
                           f"不 panic/unwrap/expect/assert——越过 ABI 边界 panic 是未定义行为）")
    return out


def _warn_export_no_panic(sid: str, rel: str, text: str, rule: dict) -> list[str]:
    """规则③：导出面（`#[no_mangle]` 起的区块）不得 panic/unwrap/expect/assert。

    区块 = 本次 `#[no_mangle]` 到**下一个** `#[no_mangle]`（或 `skip_after` 标记/文末）；
    只看代码行，注释里写 `panic!` 不算。
    """
    rx = re.compile(str(rule.get("pattern") or r"#\[no_mangle\]"))
    forbid = [str(x) for x in rule.get("forbid") or []]
    cut = _warn_cut(text, rule)
    starts = [m.start() for m in rx.finditer(text) if m.start() < cut]
    lines = text.splitlines()
    out: list[str] = []
    for i, pos in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else cut
        out += _export_span_hits(sid, rel, lines, text, (pos, end), forbid)
    return out



_WARN_RULES = {
    "unsafe_safety_comment": _warn_unsafe_safety,
    "null_guard_before": _warn_null_guard,
    "export_no_panic": _warn_export_no_panic,
}



def _rule_warns(sid: str, rel: str, text: str, rules: dict) -> list[str]:
    """单件文本按声明的 warn_rules 逐条判定（未登记规则名 / 非对象规则跳过）。"""
    out: list[str] = []
    for name, rule in rules.items():
        fn = _WARN_RULES.get(str(name))
        if fn is None or not isinstance(rule, dict):
            continue
        out += fn(sid, rel, text, rule)
    return out


def _code_warns(root: str, spec: dict) -> list[str]:
    """代码面的**告警面**（WARN 级，不 FAIL）：由声明里的 `warn_rules` 驱动。

    为什么单开一路：FFI 出口**必然**要 `unsafe`（C ABI 本质），「禁 unsafe」不能简单套用；
    而「unsafe 须带 SAFETY 注释 / `from_raw_parts` 前须挡空指针 / 导出面不许 panic」这类
    治理规则在**存量未清**时按 FAIL 接入，会立刻逼人重冻或删判据。故先按 WARN 接入：
    看得见、能逐条清；清零后再把规则搬进 `forbid_regex` / 新判据升 FAIL。
    """
    rules = spec.get("warn_rules")
    if not isinstance(rules, dict) or not rules:
        return []
    rels = resolve(root, spec)
    if not rels:
        return []                     # 未命中面的事由 `_check_code` 的 issues 报，不重复告警
    warns: list[str] = []
    sid = str(spec.get("id") or "?")
    for rel in rels:
        text, err = _read(root, rel)
        if err:
            continue                  # 读件失败同样由 issues 面报
        warns += _rule_warns(sid, rel, text or "", rules)
    return warns



def _lang_issue(spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    return (["代码契约 %s 的 lang=%s 不在支持面（仅 python 走 AST；Bash/VBA 走脚本面声明式契约"
        "）"
             % (spec.get("id"), spec.get("lang"))], {})


def _nohit_issue(spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    return (["代码契约 %s 未命中任何文件（修复指引：修正 path/glob）" % spec.get("id")],
            {"files": 0})


def _deny_set(spec: Dict[str, Any]) -> set:
    return {str(x) for x in spec.get("deny_calls") or []}


def _python_contract_issues(root: str, rels: List[str], deny: set) -> List[str]:
    """逐件 AST 判据：禁用调用 + None 解引用（语法坏件如实记一条）。"""
    issues: List[str] = []
    for one in rels:
        text, err = _read(root, one)
        if err:
            issues.append(err)
            continue
        text = text or ""
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            issues.append("代码件 %s 语法坏：%s（修复指引：先修语法，AST 判据需要可解析的树）"
                          % (one, exc))
            continue
        issues += _denied_calls(tree, one, deny)
        issues += _none_deref(tree, one)
    return issues


def _check_code(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    if spec.get("forbid_regex") or spec.get("regex_limits") or spec.get("warn_rules"):
        return _code_structural(root, spec)
    rel = str(spec.get("path") or "")
    if str(spec.get("lang") or "python") != "python":
        return _lang_issue(spec)
    rels = resolve(root, spec)
    if not rels:
        return _nohit_issue(spec)
    issues = _python_contract_issues(root, rels, _deny_set(spec))
    if rel:
        issues += _check_tests(root, rel, spec)
    return issues, {"files": len(rels)}
