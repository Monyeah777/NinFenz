"""Pattern 包品类（借 ACP 的 patterns：可发布 / 可消费 / 可移植的最佳实践包）。

NF 的 `community/` 是**内容域包**（世界/角色/事件），没有"实践规范包"这一品类。
本模块定义 `patterns/<name>/PATTERN.md` 格式与机检：

- **真源 = 每个包自己的 frontmatter**；`patterns/INDEX.md` 的登记表是**投影**（同 library 的 I5 纪律）；
- 必填：`id`/`name`/`status`/`scope`/`applies_to`/`rules`；`evidence` 至少一条；
- **可证性**：`applies_to` 里每个路径/通配必须**在仓库里匹配到真实文件**（否则这条 pattern 指向空气，
  门禁判 FAIL）；`evidence` 引用必须能解析为仓库内真实文件或 `checkN`；
- **可消费**：`for_path()` 反向回答「这个文件适用哪些 pattern」。

纪律：不为齐全而造 pattern——入库的每条都须有仓库内实证（真实存在的 applies_to 与 evidence）。
"""
from __future__ import annotations

import glob as _glob
import fnmatch as _fnmatch
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import doc_family
from core.library import parse_frontmatter

GLOB = "patterns/*/PATTERN.md"
INDEX_REL = "patterns/INDEX.md"
BEGIN = "<!-- BEGIN GENERATED: patterns-index -->"
END = "<!-- END GENERATED: patterns-index -->"
REQUIRED = ("id", "name", "status", "scope", "applies_to", "rules")
STATUSES = ("active", "deprecated")
_CHECK = re.compile(r"^check\d+$")


def entries(root: str = ".") -> List[Dict[str, Any]]:
    """全量 pattern 包（按 id 排序；path 为仓库相对路径）。"""
    r = Path(root)
    out = []
    for p in sorted(r.glob(GLOB)):
        fm, _body = parse_frontmatter(p.read_text(encoding="utf-8"))
        out.append({"dir": p.parent.name,
                    "path": p.relative_to(r).as_posix(), "fm": fm})
    out.sort(key=lambda e: str(e["fm"].get("id") or e["dir"]))
    return out


def _as_list(v: Any) -> List[str]:
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)] if v else []


def scan(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """机检 pattern 包 → (issues, warns, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    rows = entries(root)
    if not rows:
        return ["未发现任何 pattern 包（%s）" % GLOB], warns, {"patterns": 0}
    seen: Dict[str, str] = {}
    for e in rows:
        fm, d = e["fm"], e["dir"]
        if not fm:
            issues.append("%s 缺 frontmatter（修复指引：见 patterns/README.md）" % d)
            continue
        for k in REQUIRED:
            if not (fm.get(k) or fm.get(k) == []):
                issues.append("%s 缺必填字段：%s" % (d, k))
        pid = str(fm.get("id") or "")
        if pid and pid != d:
            issues.append("%s 的 id 与目录名不一致：%s vs %s" % (d, pid, d))
        if pid:
            if pid in seen:
                issues.append("pattern id 重复：%s（%s / %s）" % (pid, seen[pid], d))
            seen[pid] = d
        st = str(fm.get("status") or "")
        if st and st not in STATUSES:
            issues.append("%s status 越词表：%s（%s）" % (d, st, "/".join(STATUSES)))
        rules = _as_list(fm.get("rules"))
        if not rules:
            issues.append("%s 的 rules 为空（pattern 必须有可执行规则）" % d)
        for pat in _as_list(fm.get("applies_to")):
            pat_clean = pat.strip()
            if any(ch in pat_clean for ch in "*?["):
                hits = _glob.glob(os.path.join(root, pat_clean), recursive=True)
                if not hits:
                    issues.append("%s 的 applies_to 通配无匹配：%s"
                                  "（修复指引：指向仓库内真实文件）" % (d, pat_clean))
            elif not (Path(root) / pat_clean).exists():
                issues.append("%s 的 applies_to 路径不存在：%s" % (d, pat_clean))
        ev = _as_list(fm.get("evidence"))
        if not ev:
            warns.append("%s 缺 evidence（可证性弱：无法回溯规则来源）" % d)
        for item in ev:
            s = item.strip()
            if not s:
                warns.append("%s 的 evidence 有空项" % d)
                continue
            if _CHECK.match(s):
                continue
            # 任何带 / 的引用都按路径校验（此前只认 docs/ desktop/ protocol/ library/ 四个前缀，
            # 其它前缀（如 handovers/）的悬空引用会被静默放过——实测抓到一个）。
            if "/" in s and not (Path(root) / s).exists():
                warns.append("%s 的 evidence 指向不存在的件：%s" % (d, s))
    stats = {"patterns": len(rows), "ids": sorted(seen)}
    return issues, warns, stats


def render_index(root: str = ".") -> str:
    rows = entries(root)
    out = [BEGIN, "", "## Pattern 登记表（由各包 frontmatter 生成，勿手改）", "",
           "| id | 名称 | 状态 | 适用面 | 规则数 |", "|---|---|---|---|---|"]
    for e in rows:
        fm = e["fm"]
        out.append("| %s | %s | %s | %s | %d |" % (
            fm.get("id", e["dir"]), fm.get("name", ""),
            fm.get("status", ""), "、".join(_as_list(fm.get("scope"))[:2]),
            len(_as_list(fm.get("rules")))))
    out += ["", "> 真源 = 各包 `PATTERN.md` 的 frontmatter；本表为投影（`nf patterns reindex` 重建"
        "）。", ""]
    return "\n".join(out + _status_section(rows) + [END])


def _status_section(rows):
    """现状对照 + 复现口径（生成；计数由本表实时算出，不手写）。"""
    ids = [str(e["fm"].get("id") or e["dir"]) for e in rows]
    rules = sum(len(_as_list(e["fm"].get("rules"))) for e in rows)
    statuses = {}
    for e in rows:
        key = str(e["fm"].get("status") or "?")
        statuses[key] = statuses.get(key, 0) + 1
    per_pkg = sorted({len(_as_list(e["fm"].get("rules"))) for e in rows})
    shape = "、".join(str(n) for n in per_pkg)
    status_line = " · ".join(f"{k} {v}" for k, v in sorted(statuses.items()))
    bt = chr(96) * 3
    id_line = "、".join(chr(96) + i + chr(96) for i in ids)
    return [
        "## 现状对照（生成 · 计数由本表实时算出）",
        "",
        "| 面 | 现值 | 说明 |",
        "|---|---|---|",
        f"| 实践包 | **{len(rows)}** | 生成区表格行数 |",
        f"| 规则总数 | **{rules}** | 各包 rules 长度求和（每包 {shape} 条） |",
        f"| 状态分布 | {status_line} | 各包 frontmatter 的 status |",
        "",
        f"**包 id**（生成）：{id_line}",
        "",
        "## 复现与引用口径（生成）",
        "",
        bt + "bash",
        "python scripts/nf.py patterns ls         # 列全部实践包（真源 = 各 PATTERN.md）",
        "python scripts/nf.py patterns verify     # 格式 + 可证性机检",
        "python scripts/nf.py patterns reindex    # 重建本页（幂等：无变化即输出「无变化」）",
        bt,
        "",
        "- **本页整体是生成物**：手改会被下一次 reindex 覆盖；"
        "要改内容请改 patterns/<id>/PATTERN.md。",
        "",
    ]


def write_projection(root: str = ".") -> Dict[str, Any]:
    return doc_family.write_index(
        root, index_rel=INDEX_REL, header="# NF Patterns 索引\n\n",
        begin=BEGIN, end=END, block=render_index(root))


def check_projection(root: str = ".") -> List[str]:
    return doc_family.check_index(
        root, index_rel=INDEX_REL, begin=BEGIN, end=END, block=render_index(root),
        missing_hint="nf patterns reindex",
        mismatch="patterns 登记表与实时重算不一致（跑 nf patterns reindex）")


def for_path(root: str, target: str) -> List[Dict[str, str]]:
    """反向查询：某文件适用哪些 pattern（可消费面的核心）。"""
    hit = []
    t = target.replace("\\", "/")
    for e in entries(root):
        fm = e["fm"]
        for pat in _as_list(fm.get("applies_to")):
            p = pat.strip().replace("\\", "/")
            if any(ch in p for ch in "*?["):
                if _fnmatch.fnmatch(t, p):
                    hit.append({"id": str(fm.get("id") or e["dir"]),
                                "name": str(fm.get("name") or ""),
                                "matched": p})
                    break
            elif t == p or t.startswith(p.rstrip("/") + "/"):
                hit.append({"id": str(fm.get("id") or e["dir"]),
                            "name": str(fm.get("name") or ""), "matched": p})
                break
    return hit
