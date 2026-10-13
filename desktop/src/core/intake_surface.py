"""投稿面一致性门（2026-10-13 · 整体架构对齐）。

内部差距实证（本轮逆向外推审查）：投稿面的事实此前散在多处手写且零判据——
模板可见字段 / 长度口径 / 通道口径 / 拒收判据各写 2–4 处；verify check34 只判
「声明 ⇄ INDEX 标签 ⇄ 两个机器人引用」，一行模板都不看。后果已实证四处漂移：
模板缺 `分级` 字段（机器人读它、rating_gate 缺字段即 FAIL）、
「约 6 万字符（平台限制）」与 `MAX_BODY_CHARS=262144` 不符、
声明里的 gate 名全仓只出现在声明件自身、`.gitee/ISSUE_TEMPLATE/` 空置而文档说
「开题后选模板即可」。

本模块把投稿面收敛为声明驱动的一致性命据：真源 = `library/intake.json` 的
`submission` 段；模板与须知只是它的投影，漂移即红。纪律：只读；fail-closed
（声明缺失/不可解析即 FAIL，不静默放行）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

INTAKE_REL = "library/intake.json"
INDEX_REL = "library/INDEX.md"
ROUTES_REL = "docs/agent/ROUTES.md"

#: 反引号内的仓内路径记号（过滤掉 URL / 通配 / 占位符 / 含空白者）
_BACKTICK = re.compile(r"`([^`\n]+)`")
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")


def _decl(root: str = ".") -> dict[str, Any]:
    """读闸门声明件 → dict（缺失 / 非法 JSON → 空 dict，由 scan 报 FAIL）。"""
    p = Path(root) / INTAKE_REL
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:  # 缺件/坏 JSON ⇒ 空 dict（由 intake_surface.scan 报 FAIL，不静默放行）
        return {}
    return data if isinstance(data, dict) else {}


def _read(root: str, rel: str) -> str:
    p = Path(root) / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _has_field_line(text: str, field: str) -> bool:
    """可见字段行 = 行首即「字段：」/「字段:」（括号示例行也算在场，取值为广告位）。"""
    pat = rf"(?m)^\s*{re.escape(field)}\s*[:：]"
    return re.search(pat, text) is not None


def _backtick_paths(text: str, allow: list[str]) -> list[str]:
    out: list[str] = []
    for m in _BACKTICK.finditer(text):
        tok = m.group(1).strip()
        if tok in allow or "/" not in tok or not _PATH_SHAPE.match(tok):
            continue
        if any(ch in tok for ch in "*…<>") or tok.startswith("http"):
            continue
        out.append(tok)
    return out


def _check_templates(root: str, tpl_list: list[str], issues: list[str],
                     stats: dict[str, Any], fields: list[str]) -> None:
    """C0/C1：声明的模板件须在场；模板可见字段须覆盖声明的字段集。"""
    for rel in tpl_list:
        stats["templates"] += 1
        if not (Path(root) / rel).is_file():
            issues.append(f"投稿模板件不在场：{rel}（修复指引：声明与文件须一致）")
            continue
        text = _read(root, rel)
        stats["fields"] += len(fields)
        missing = [f for f in fields if not _has_field_line(text, f)]
        if missing:
            issues.append(
                f"模板缺可见字段：{'/'.join(missing)} ← {rel}"
                "（修复指引：机读契约读这些键，缺则投稿人无法声明）")


def _check_limits(root: str, sub: dict, tpl_list: list[str], issues: list[str]) -> None:
    """C2：长度口径须出现声明标签，且不得出现被禁的错误归因。"""
    label = str(sub.get("body_limit_label") or "")
    banned = [str(x) for x in (sub.get("forbidden_attributions") or [])]
    limit_chars = int(sub.get("body_limit_chars") or 0)
    for rel in [*tpl_list, INDEX_REL]:
        text = _read(root, rel)
        if not text:
            continue
        if label and label not in text:
            issues.append(
                f"{rel} 未写明正文硬上限标签「{label}」"
                f"（修复指引：口径须与 {INTAKE_REL} 的 body_limit_chars={limit_chars} 对齐）")
        for bad in banned:
            if bad in text:
                issues.append(
                    f"{rel} 出现被禁的长度归因「{bad}」"
                    "（修复指引：硬上限以声明件为准，不得伪装成平台限制）")


def _check_gate_refs(root: str, sub: dict, tpl_list: list[str], issues: list[str]) -> None:
    """C3：模板须指向声明/须知，防止把接收口径写死在模板里。"""
    refs = [str(x) for x in (sub.get("gate_ref_surface") or [])]
    for rel in tpl_list:
        text = _read(root, rel)
        if text and refs and not any(r in text for r in refs):
            issues.append(
                f"{rel} 未指向闸门声明/须知（{' 或 '.join(refs)}）——接收口径必须声明驱动")


def _check_paths(root: str, sub: dict, issues: list[str], stats: dict[str, Any]) -> None:
    """C4：反引号内的仓内路径必须可解析（悬空引用）。"""
    allow = [str(x) for x in (sub.get("path_allow") or [])]
    for rel in [str(x) for x in (sub.get("path_surface") or [])]:
        text = _read(root, rel)
        if not text:
            issues.append(f"path_surface 声明的件不在场：{rel}")
            continue
        for tok in _backtick_paths(text, allow):
            stats["paths"] += 1
            if not (Path(root) / tok.rstrip("/")).exists():
                issues.append(f"{rel} 引用的仓内路径不存在：{tok}（悬空引用）")


def _check_gate_impl(root: str, doc: dict, sub: dict, issues: list[str],
                     stats: dict[str, Any]) -> None:
    """C5：声明的闸门名须有落点（editorial = 人工评审面；code:<path> = 实现件须在场）。"""
    impl = sub.get("gate_impl") or {}
    for chan, ch in sorted((doc.get("channels") or {}).items()):
        for gate in (ch or {}).get("gate") or []:
            stats["gates"] += 1
            where = impl.get(str(gate))
            if not where:
                issues.append(
                    f"通道 {chan} 声明了闸门「{gate}」，但 submission.gate_impl 无落点"
                    "（修复指引：登记 editorial 或 code:<path>）")
            elif str(where).startswith("code:") and not (Path(root) / str(where)[5:]).is_file():
                issues.append(
                    f"通道 {chan} 的闸门「{gate}」指向的实现件不在场：{str(where)[5:]}")


def _check_gitee(root: str, sub: dict, templates: dict, issues: list[str]) -> None:
    """C6：Gitee 面声明状态须与磁盘一致，且入口文档须指向模板件。"""
    gs = sub.get("gitee_surface") or {}
    gdir = str(gs.get("dir") or "")
    state = str(gs.get("state") or "")
    if not gdir:
        return
    d = Path(root) / gdir
    if state == "empty-by-design":
        if not d.is_dir():
            issues.append(f"gitee_surface.dir 不存在：{gdir}（empty-by-design 须目录在场且为空）")
        elif any(d.iterdir()):
            issues.append(f"gitee_surface.dir 声明 empty-by-design，但目录非空：{gdir}")
        routes = _read(root, ROUTES_REL)
        for rel in (templates.get("gitee") or []):
            if Path(str(rel)).name not in routes:
                issues.append(
                    f"{ROUTES_REL} 未指向 Gitee 模板件 {rel}"
                    "——Gitee 侧无选择器时，入口只能靠文档")
    elif state == "file-backed":
        if not d.is_dir() or not any(d.iterdir()):
            issues.append(f"gitee_surface.state=file-backed，但目录为空：{gdir}")
    else:
        issues.append(f"gitee_surface.state 非法：{state!r}（取值 empty-by-design / file-backed）")


def _check_code_surfaces(root: str, sub: dict, issues: list[str]) -> None:
    """C7：代码面分类单一真源（本轮漂移的直因：模板里手写一份、仓里演进另一份）。"""
    surfaces = [str(x) for x in (sub.get("code_surfaces") or [])]
    cst = str(sub.get("code_surface_template") or "")
    prefix = str(sub.get("code_surface_prefix") or "")
    if not (surfaces and cst and prefix):
        return
    want = f"{prefix}（{' · '.join(surfaces)}）"
    if want not in _read(root, cst):
        issues.append(f"{cst} 的代码面清单与声明不一致（应逐字为「{want}」）")
    for s in surfaces:
        if not (Path(root) / s.rstrip("/")).exists():
            issues.append(f"code_surfaces 声明的路径不存在：{s}")


def _check_anchors(root: str, sub: dict, issues: list[str]) -> None:
    """C8：口径锚点行须跨文件逐字一致（防「模板改了、声明没改」）。"""
    for a in (sub.get("anchor_lines") or []):
        rel = str((a or {}).get("file") or "")
        want = str((a or {}).get("text") or "")
        if not rel or not want:
            continue
        if want not in _read(root, rel):
            issues.append(f"{rel} 的口径锚点行与声明不一致（声明以「{want[:40]}…」开头）")
        for p in (a or {}).get("check_paths") or []:
            if not (Path(root) / str(p)).exists():
                issues.append(f"锚点行引用的路径不存在：{p} ← {rel}")


def scan(root: str = ".") -> tuple[list[str], dict[str, Any]]:
    """投稿面一致性体检 → (issues, stats)。"""
    doc = _decl(root)
    if not doc:
        return ([f"缺投稿闸门声明 {INTAKE_REL}"
                 "（修复指引：补声明件；投稿面判据以它为唯一真源）"],
                {"templates": 0, "issues": 1})
    sub = doc.get("submission")
    if not isinstance(sub, dict):
        return ([f"{INTAKE_REL} 缺 submission 段"
                 "（修复指引：投稿面契约须成文——字段/长度/拒收/模板/闸门落点）"],
                {"templates": 0, "issues": 1})

    issues: list[str] = []
    stats: dict[str, Any] = {"templates": 0, "paths": 0, "gates": 0, "fields": 0}
    fields = [str(x) for x in (sub.get("fields") or [])]
    templates = sub.get("templates") or {}
    tpl_list = [str(rel) for chan in sorted(templates) for rel in (templates.get(chan) or [])]

    _check_templates(root, tpl_list, issues, stats, fields)
    _check_limits(root, sub, tpl_list, issues)
    _check_gate_refs(root, sub, tpl_list, issues)
    _check_paths(root, sub, issues, stats)
    _check_gate_impl(root, doc, sub, issues, stats)
    _check_gitee(root, sub, templates, issues)
    _check_code_surfaces(root, sub, issues)
    _check_anchors(root, sub, issues)
    return issues, stats
