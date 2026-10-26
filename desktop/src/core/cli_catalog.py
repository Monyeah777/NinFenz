#!/usr/bin/env python3
# nf-io: inputs=terminal.FAMILIES,scripts/nf.py,argparse outputs=protocol/cli_map.json,docs/cli-map.md
"""CLI 信息架构（IA）机读层（T11.3）：命令 → 族 → 用途 → 机器面，可查询/可校验/可生成文档。

**这是什么**：把「命令面长什么样」从散落在 `terminal.FAMILIES`（策展）与 argparse（存在性
真源）里的两份事实，收敛成**一份 canonical 数据**（`nf-cli-map/1`）：

- `protocol/cli_map.json`：生成件（每命令 group/one_line/usage/flags/has_json/related_docs；
  每族 id/name/summary/commands；根级覆盖率块）；
- `docs/cli-map.md`：由**同一份数据**渲染的人读表（命令/族/用途/机器面）。

**不新造能力、不改命令行为**：本模块只读消费 `terminal.FAMILIES` 与 argparse parser（由 CLI
传入，避免 core 反向依赖 `scripts/nf.py`）；`nf cli map --write` 生成，`--check` 与实时重算
逐字节对账（源改了没重生成即红）。

覆盖率判据（与 check39 的终端自检同口径，但**把数据暴露出来**）
------------------------------------------------------------
1. 每个顶层命令**恰好**归一族（未归族 / 重复归族即 FAIL）；
2. 每族非空（空族 = 图纸，不可执行）；
3. 族内命令必须在 argparse 面真实存在（不许虚指）。

IA 层边界（本波**未做**，见报告）：命令包拆分（不拆 nf.py）、别名体系、弃用/迁移策略
——它们都属「命令行为」变更，按任务约束不在本波范围。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core import atomic_write, terminal

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = "nf-cli-map/1"
MAP_REL = "protocol/cli_map.json"
DOC_REL = "docs/cli-map.md"
DOCS_GLOB = "docs/**/*.md"
_MAX_DOCS = 4
_MAX_ONE_LINE = 120


# ---------------------------------------------------------------- 构建

def _flags(parser: argparse.ArgumentParser) -> List[str]:
    out: List[str] = []
    for act in parser._actions:
        if isinstance(act, argparse._SubParsersAction):
            continue
        out += list(act.option_strings)
    return sorted(set(out))


def _one_line(parser: argparse.ArgumentParser) -> str:
    """命令一句话用途：优先 description 首行，回退到子命令 help。"""
    text = (parser.description or "").strip()
    if not text:
        text = str(getattr(parser, "help", "") or "").strip()
    first = text.splitlines()[0].strip() if text else ""
    return first if len(first) <= _MAX_ONE_LINE else first[:_MAX_ONE_LINE - 1] + "…"


def _usage(parser: argparse.ArgumentParser) -> str:
    text = parser.format_usage().strip().replace("\n", " ")
    return re.sub(r"\s+", " ", text)


def _subcommands(parser: argparse.ArgumentParser) -> Dict[str, List[str]]:
    nested: Dict[str, List[str]] = {}
    for act in parser._actions:
        if not isinstance(act, argparse._SubParsersAction):
            continue
        for name, sp in act.choices.items():
            nested[str(name)] = _flags(sp)
    return dict(sorted(nested.items()))


def _docs_mentions(root: Path, command: str) -> List[str]:
    """命令在 IA 文档里的相关文档（docs/**/*.md，排除生成件自身；确定性排序）。"""
    pat = re.compile(r"\bnf\s+%s\b" % re.escape(command))
    out: List[str] = []
    base = root / "docs"
    if not base.is_dir():
        return out
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if rel == DOC_REL:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if pat.search(text):
            out.append(rel)
        if len(out) >= _MAX_DOCS:
            break
    return out


def _canonical(doc: Dict[str, Any]) -> bytes:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def build(parser: argparse.ArgumentParser,
          families: Optional[Sequence[Dict[str, Any]]] = None,
          root: Optional[Any] = None) -> Dict[str, Any]:
    """→ `nf-cli-map/1` canonical 数据（纯函数；同输入逐字节同输出）。"""
    r = Path(root).resolve() if root is not None else ROOT
    fams = list(families if families is not None else terminal.FAMILIES)
    root_sub = _root_subparsers(parser)
    commands = sorted(root_sub)

    fam_rows: List[Dict[str, Any]] = []
    owner: Dict[str, str] = {}
    dupes: Dict[str, List[str]] = {}
    stray: List[Tuple[str, str]] = []
    for fam in fams:
        cmds = [str(c) for c in (fam.get("commands") or ())]
        fid = str(fam.get("id") or "")
        fam_rows.append({"id": fid, "name": str(fam.get("name") or ""),
                         "summary": str(fam.get("summary") or ""),
                         "commands": sorted(cmds)})
        for cmd in cmds:
            if cmd in owner:
                dupes.setdefault(cmd, [owner[cmd]]).append(fid)
            else:
                owner[cmd] = fid
            if cmd not in root_sub:
                stray.append((cmd, fid))

    rows: List[Dict[str, Any]] = []
    for cmd in commands:
        sp = root_sub[cmd]
        flags = _flags(sp)
        rows.append({
            "name": cmd,
            "group": owner.get(cmd, ""),
            "one_line": _one_line(sp),
            "usage": _usage(sp),
            "flags": flags,
            "nested": _subcommands(sp),
            "has_json": "--json" in flags,
            "related_docs": _docs_mentions(r, cmd),
        })

    empties = [f["id"] for f in fam_rows if not f["commands"]]
    coverage = {
        "commands": len(commands),
        "families": len(fam_rows),
        "covered": sum(1 for c in commands if c in owner),
        "uncurated": sorted(c for c in commands if c not in owner),
        "duplicates": {k: sorted(v) for k, v in sorted(dupes.items())},
        "empty_families": sorted(empties),
        "stray": [{"command": c, "family": f} for c, f in sorted(stray)],
    }
    doc = {
        "kind": "cli-map",
        "schema": SCHEMA,
        "source": {
            "commands": "argparse:scripts/nf.py::_build_parser",
            "families": "desktop/src/core/terminal.py::FAMILIES",
            "docs": DOCS_GLOB,
        },
        "root_flags": sorted(set(terminal_root_flags(parser))),
        "families": sorted(fam_rows, key=lambda f: f["id"]),
        "commands": rows,
        "coverage": coverage,
    }
    doc["digest"] = "sha256:" + hashlib.sha256(_canonical(doc)).hexdigest()
    return doc


def _root_subparsers(parser: argparse.ArgumentParser) -> Dict[str, argparse.ArgumentParser]:
    out: Dict[str, argparse.ArgumentParser] = {}
    for act in parser._actions:
        if not isinstance(act, argparse._SubParsersAction):
            continue
        for name, sp in act.choices.items():
            out[str(name)] = sp
    return dict(sorted(out.items()))


def terminal_root_flags(parser: argparse.ArgumentParser) -> List[str]:
    """根级旗标（`nf --x`），与 `_collect_cli_tree()['root_flags']` 同口径。"""
    return _flags(parser)


# ---------------------------------------------------------------- 覆盖率判据

def coverage_issues(doc: Dict[str, Any]) -> List[str]:
    """→ 覆盖率问题列表（空 = 通过）。与 check39 的终端自检同口径（数据版）。"""
    cov = doc.get("coverage") or {}
    issues: List[str] = []
    for cmd in cov.get("uncurated") or []:
        issues.append("未归族命令：%s（修复指引：在 terminal.FAMILIES 的某一族登记）" % cmd)
    for cmd, fams in (cov.get("duplicates") or {}).items():
        issues.append("命令重复归族：%s → %s（修复指引：一命令只归一族）"
                      % (cmd, "、".join(fams)))
    for fid in cov.get("empty_families") or []:
        issues.append("空能力族：%s（修复指引：补命令或删除该族）" % fid)
    for row in cov.get("stray") or []:
        issues.append("族内虚指命令：%s（族 %s）（修复指引：改成 argparse 面真实命令）"
                      % (row.get("command"), row.get("family")))
    for fam in doc.get("families") or []:
        if not str(fam.get("id") or "").strip():
            issues.append("能力族缺 id（修复指引：补 id）")
        if not str(fam.get("name") or "").strip():
            issues.append("能力族 %s 缺 name（修复指引：补中文名）" % fam.get("id"))
        if not str(fam.get("summary") or "").strip():
            issues.append("能力族 %s 缺 summary（修复指引：补一句职责）" % fam.get("id"))
    return issues


# ---------------------------------------------------------------- 渲染 / 落盘 / 对账

def render_md(doc: Dict[str, Any]) -> str:
    """同一 canonical 数据 → 人读表（确定性：无时间戳、排序固定）。"""
    cov = doc.get("coverage") or {}
    by_fam = {f["id"]: f for f in doc.get("families") or []}
    lines = [
        "# NF CLI 命令地图（生成件 · 真源 = argparse 面 + terminal.FAMILIES）",
        "",
        "> 本件由 `nf cli map --write` 生成，`nf cli map --check` 与实时重算逐字节对账；",
        "> 手改会被下一次 check 判红。命令缺失/重复归族/空族见文末覆盖率块。",
        "",
        "## 覆盖率",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| 顶层命令 | %d |" % cov.get("commands", 0),
        "| 能力族 | %d |" % cov.get("families", 0),
        "| 已归族 | %d |" % cov.get("covered", 0),
        "| 未归族 | %s |" % (", ".join(cov.get("uncurated") or []) or "无"),
        "| 重复归族 | %s |" % (
            "；".join("%s→%s" % (k, "/".join(v)) for k, v in
                      sorted((cov.get("duplicates") or {}).items())) or "无"),
        "| 空族 | %s |" % (", ".join(cov.get("empty_families") or []) or "无"),
        "",
        "## 命令目录",
        "",
        "| 命令 | 族 | 用途 | 机器面 | 相关文档 |",
        "|---|---|---|---|---|",
    ]
    for row in doc.get("commands") or []:
        fam = by_fam.get(row.get("group") or "", {})
        docs = row.get("related_docs") or []
        lines.append("| `nf %s` | %s（%s） | %s | %s | %s |"
                     % (row["name"], fam.get("name", "?"), row.get("group", "?"),
                        (row.get("one_line") or "").replace("|", "\\|"),
                        "JSON" if row.get("has_json") else "文本",
                        "、".join(docs) if docs else "—"))
    lines += ["", "## 能力族", "", "| 族 | 名称 | 命令 |", "|---|---|---|"]
    for fid in sorted(by_fam):
        fam = by_fam[fid]
        lines.append("| %s | %s | %s |" % (fid, fam.get("name", ""),
                                          ", ".join("`nf %s`" % c
                                                    for c in fam.get("commands") or [])))
    lines += ["", "## 复跑", "", "```", "python scripts/nf.py cli map --check --json",
              "python scripts/nf.py cli map --write", "```", ""]
    return "\n".join(lines)


def write(root: Optional[Any] = None, parser: Optional[argparse.ArgumentParser] = None,
          doc: Optional[Dict[str, Any]] = None) -> Tuple[List[str], Dict[str, Any]]:
    """落 `protocol/cli_map.json` + `docs/cli-map.md`；→ (写的相对路径, doc)。"""
    r = Path(root).resolve() if root is not None else ROOT
    doc = doc if doc is not None else build(parser, root=r)
    (r / MAP_REL).parent.mkdir(parents=True, exist_ok=True)
    (r / DOC_REL).parent.mkdir(parents=True, exist_ok=True)
    atomic_write.write_text(r / MAP_REL,
                            json.dumps(doc, ensure_ascii=False, indent=2,
                                       sort_keys=True) + "\n")
    atomic_write.write_text(r / DOC_REL, render_md(doc))
    return [MAP_REL, DOC_REL], doc


def _read_text(p: Path) -> Optional[str]:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def check(root: Optional[Any] = None,
          parser: Optional[argparse.ArgumentParser] = None) -> Tuple[List[str], Dict[str, Any], Dict[str, Any]]:
    """→ (问题, 差异, 实时 doc)。问题 = 覆盖率不闭合 或 生成件与实时重算不一致。"""
    r = Path(root).resolve() if root is not None else ROOT
    doc = build(parser, root=r)
    issues = coverage_issues(doc)
    diffs: Dict[str, Any] = {}
    want_json = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    got_json = _read_text(r / MAP_REL)
    if got_json is None:
        issues.append("缺生成件：%s（修复指引：跑 nf cli map --write）" % MAP_REL)
        diffs["json"] = "missing"
    elif got_json != want_json:
        issues.append("生成件与实时重算不一致：%s（修复指引：跑 nf cli map --write）"
                      % MAP_REL)
        diffs["json"] = "stale"
    want_md = render_md(doc)
    got_md = _read_text(r / DOC_REL)
    if got_md is None:
        issues.append("缺人读件：%s（修复指引：跑 nf cli map --write）" % DOC_REL)
        diffs["md"] = "missing"
    elif got_md != want_md:
        issues.append("人读件与实时重算不一致：%s（修复指引：跑 nf cli map --write）"
                      % DOC_REL)
        diffs["md"] = "stale"
    return issues, diffs, doc
