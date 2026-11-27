"""core.knowledge 私有实现分片 2/2（对外只经 core.knowledge 门面导入）：harvest_frequency 等"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import atomic_write, json_doc

from ._part1 import (
    LOG_REL,
    LOG_SCHEMA,
    USAGE_REL,
    USAGE_SCHEMA,
    load_log,
    load_usage,
    scan,
    sha256_file,
    sources,
    verify_transform,
)


def _parse_trace(text: str, trace_path: str) -> Tuple[List[Any], bool, str]:
    records: List[Any] = []
    parsed_any = False
    shape_error = ""
    try:
        # NaN/±Infinity 拒绝与资产契约同一实现（json_doc.strict_constants，审计 N11/Z1 收口）。
        data = json_doc.loads(text, None, what=str(trace_path), strict_constants=True)
        parsed_any = True
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            rec = data.get("records")
            records = rec if isinstance(rec, list) else [data]
        else:
            # 审计 N5（P2）：顶层是字符串/数字时此前静默按「0 源」放行——形如 "hello" / 42
            # 的件根本不是 trace，读者会把「件给错了」读成「这次没用到知识源」。
            shape_error = "顶层不是对象/数组（实为 %s）" % type(data).__name__
    except ValueError:
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json_doc.loads(line, None, what="knowledge trace 行",
                                                strict_constants=True))
                    parsed_any = True
                except ValueError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
                    continue
    return records, parsed_any, shape_error


def _count_sources(records: List[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in records:
        sid = str(r.get("knowledge_source") or r.get("source_id") or "")
        if sid:
            counts[sid] = counts.get(sid, 0) + 1
    return counts


def harvest_frequency(trace_path: str) -> Dict[str, int]:
    """从 trace 记录数知识源使用频次（确定性，不联网、不调模型）。

    记录形态支持三种：JSON 数组 / `{"records": [...]}` / JSONL（逐行对象）。
    源标识取记录的 `knowledge_source` 或 `source_id` 字段（与遥测 semconv 对齐的字段名）。
    """
    p = Path(trace_path)
    text = p.read_text(encoding="utf-8-sig")   # 容忍外来件 BOM（审计 N4）
    records, parsed_any, shape_error = _parse_trace(text, trace_path)
    # 全件都解析不出来 ⇒ **如实失败**，不是「0 源有事件」（2026-10-01 取证：截断/坏件的
    # trace 此前 rc=0 且报「0 源」，读者会把「文件坏了」读成「这份运行没用到知识源」——
    # 静默错答）。空件仍按 0 记录放行（空 = 合法）。
    if text.strip() and not parsed_any:
        raise ValueError(
            "trace 不是合法 JSON/JSONL：%s（修复指引：收 nf assemble --check <成品.md> "
            "--trace <trace.json> 落的件，或 {\"records\": [...]} / 逐行 JSON）" % p)
    if shape_error:
        raise ValueError("trace %s：%s（修复指引：单条记录 {...}、{\"records\": [...]} "
                         "或逐行 JSON 对象）" % (shape_error, p))
    if records and not all(isinstance(r, dict) for r in records):
        # 审计 N5：对象数组里混进标量（[1,2,3]）此前静默算成 0 源——同样是把「件坏了」
        # 读成「没用到」的静默错答。
        raise ValueError("trace 记录必须都是 JSON 对象：%s（修复指引：单条记录 {...} 或 "
                         "{\"records\": [...]}；数组元素与逐行内容都须是对象）" % p)
    counts = _count_sources(records)
    return {k: counts[k] for k in sorted(counts)}


def write_usage(root: str = ".", counts: Dict[str, int] | None = None) -> str:
    """写频率台账（唯一写入口；频次由 trace 复算，不许手写）。"""
    clean = {k: int(v) for k, v in sorted((counts or {}).items())}
    doc = {"schema": USAGE_SCHEMA,
           "note": "知识源使用频次台账（复算入口：nf knowledge frequency --trace <file> --write）。"
                   "晋升条目若声明 reuse_count，必须与本台账一致——频次不可手写。",
           "counts": clean, "total": sum(clean.values())}
    p = Path(root) / USAGE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    # 原子写（2026-09-30 收口）：在仓台账，并发读（check37 / `nf knowledge`）此前可能读到半截。
    atomic_write.write_text(p, json.dumps(doc, ensure_ascii=False,
                                          indent=2, sort_keys=True) + "\n")
    return USAGE_REL


def write_log(root: str = ".", entries: List[Dict[str, Any]] | None = None) -> str:
    """写消化记录（复核工作流的落盘口；条目按 from/to 排序，保证可复算）。"""
    doc = dict(load_log(root))
    doc["schema"] = LOG_SCHEMA
    doc.setdefault("note", "消化记录（外部 → 本地，digest 绑定）。")
    doc["entries"] = sorted((entries or []), key=lambda e: (str(e.get("from")),
                                                            str(e.get("to"))))
    p = Path(root) / LOG_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    # 原子写（2026-09-30 收口）：同上，消化记录也是在仓台账。
    atomic_write.write_text(p, json.dumps(doc, ensure_ascii=False,
                                          indent=2, sort_keys=True) + "\n")
    return LOG_REL


def _usage_counts_issues(counts: Dict[str, Any], ids: set) -> List[str]:
    issues: List[str] = []
    for k, v in counts.items():
        if str(k) not in ids:
            issues.append("频率台账含未声明的源：%s（防幽灵频次）" % k)
        if not (isinstance(v, int) and v >= 0):
            issues.append("频率计数非非负整数：%s" % k)
    return issues


def _reuse_count_issues(counts: Dict[str, Any], root: str) -> List[str]:
    issues: List[str] = []
    for e in load_log(root).get("entries") or []:
        if not isinstance(e, dict) or "reuse_count" not in e:
            continue
        got = counts.get(str(e.get("from")))
        if e["reuse_count"] != got:
            issues.append("频次不可复算：%s 的记录 reuse_count=%s，频率台账=%s"
                          "（修复指引：按 trace 重算，不要手写频次）"
                          % (e.get("from"), e["reuse_count"], got))
    return issues


def _usage_events(counts: Dict[str, Any]) -> int:
    return sum(v for v in counts.values() if isinstance(v, int))


def _usage_total_issue(doc: Dict[str, Any], counts: Dict[str, Any]) -> List[str]:
    if not isinstance(doc.get("total"), int):
        return []
    if doc["total"] != _usage_events(counts):
        return ["频率台账 total 与 counts 求和不一致（手改痕迹）"]
    return []


def verify_usage(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """频率台账校验：条目合法 + 与消化记录的 reuse_count 交叉复算。"""
    issues: List[str] = []
    warns: List[str] = []
    doc = load_usage(root)
    if not doc:
        return ["缺频率台账 %s（修复指引：nf knowledge frequency --trace <file> --write）"
                % USAGE_REL], warns, {}
    if str(doc.get("schema") or "") != USAGE_SCHEMA:
        issues.append("频率台账 schema 不匹配（期望 %s）" % USAGE_SCHEMA)
    counts = doc.get("counts")
    if not isinstance(counts, dict):
        issues.append("频率台账 counts 非对象")
        counts = {}
    ids = {str(s.get("id")) for s in sources(root)}
    issues.extend(_usage_counts_issues(counts, ids))
    issues.extend(_usage_total_issue(doc, counts))
    issues.extend(_reuse_count_issues(counts, root))
    stats = {"sources_with_usage": len(counts), "events": _usage_events(counts)}
    return issues, warns, stats


def _library_id_issues(r: Path, lib: List[Path]) -> Tuple[List[str], Dict[str, str]]:
    issues: List[str] = []
    ids: Dict[str, str] = {}
    for p in lib:
        fm, _body = None, None
        # 直连**叶子件**（2026-09-30）：`library` 只是把 `parse_frontmatter` 从
        # `library_entries` 兼容转发出来；从这里绕一手会平白多一条 knowledge → library 的
        # 依赖边，而 library 的不稳定性（i≈0.36）高于 knowledge（i≈0.33）⇒ 撞 SDP 判据
        # 「稳定侧不得依赖更不稳的一侧」。改直连叶子后这条边消失（同一实现，零行为变化）。
        from core.library_entries import parse_frontmatter
        fm, _body = parse_frontmatter(p.read_text(encoding="utf-8"))
        eid = str((fm or {}).get("id") or "")
        if not eid:
            issues.append("%s 缺 frontmatter id（复用面无法寻址）" % p.name)
            continue
        if eid in ids:
            issues.append("条目 id 重复：%s（%s 与 %s）——同一编号两处真源" % (eid,
 ids[eid],
 p.name))
        ids[eid] = p.name
        if eid != p.stem:
            issues.append("%s 的 id 与文件名不一致：%s" % (p.name, eid))
    return issues, ids


def _digest_issues(r: Path) -> Tuple[List[str], Dict[str, List[str]]]:
    issues: List[str] = []
    digests: Dict[str, List[str]] = {}
    for p in sorted(r.glob("library/NF-*.md")) + sorted(r.glob("patterns/*/PATTERN.md")):
        d = sha256_file(str(p))
        digests.setdefault(d, []).append(p.relative_to(r).as_posix())
    for d, files in digests.items():
        if len(files) > 1:
            issues.append("同一内容存在两份（禁止复制正文）：%s" % " 、 ".join(files))
    return issues, digests


def _alias_cells(line: str) -> List[str] | None:
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 2 or cells[0] in ("小写键", "---") or set(cells[0]) <= set("-: "):
        return None
    return cells


def _alias_issues(alias: Path, ids: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
    issues: List[str] = []
    seen: Dict[str, str] = {}
    if not alias.is_file():
        return issues, seen
    for line in alias.read_text(encoding="utf-8").splitlines():
        cells = _alias_cells(line)
        if cells is None:
            continue
        key, real = cells[0], cells[1]
        if key in seen:
            issues.append("ALIAS 小写键重复：%s（转译将歧义）" % key)
        seen[key] = real
        if real and real not in ids:
            issues.append("ALIAS 指向不在册条目：%s → %s" % (key, real))
    return issues, seen


def verify_reuse(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """唯一来源复用（conref / keyref 的可验证版）→ (issues, warns, stats)。

    三条判据（全部确定性）：
    1. **ID 唯一**：library 条目的 frontmatter `id` 必须唯一且等于文件名；
    2. **间接层可解析**：`library/ALIAS.md` 的小写键唯一，且每行的真实编号都在册；
    3. **禁止复制正文**：任意两件（library 条目 + patterns 源件）全文摘要不得相同
       ——同一内容两份 = 两个真源，违反单一真相源。
    """
    issues: List[str] = []
    warns: List[str] = []
    r = Path(root)
    lib = sorted(r.glob("library/NF-*.md"))
    id_issues, ids = _library_id_issues(r, lib)
    issues += id_issues
    digest_issues, digests = _digest_issues(r)
    issues += digest_issues
    alias = r / "library" / "ALIAS.md"
    alias_issues, seen = _alias_issues(alias, ids)
    issues += alias_issues
    stats = {"entries": len(lib), "alias_keys": len(seen) if alias.is_file() else 0,
             "unique_digests": len(digests)}
    return issues, warns, stats


def _dangling_refs(root: str) -> List[str]:
    dangling: List[str] = []
    for rel in ("library/INDEX.md", "library/ALIAS.md", "llms.txt"):
        p = Path(root) / rel
        if not p.is_file():
            continue
        for m in re.finditer(r"library/([A-Za-z0-9\-]+)\.md", p.read_text(encoding="utf-8")):
            target = Path(root) / "library" / ("%s.md" % m.group(1))
            if not target.is_file() and rel not in dangling:
                dangling.append("%s → %s" % (rel, target.name))
    return dangling


def _orphan_entries(entry_ids: List[str], idx: str) -> List[str]:
    return [e for e in entry_ids if idx and e not in idx]


def _missing_stale(root: str) -> List[str]:
    no_stale: List[str] = []
    for p in sorted((Path(root) / "library").glob("NF-*.md")):
        if "stale_after:" not in p.read_text(encoding="utf-8"):
            no_stale.append(p.name)
    return no_stale


def lint(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """知识层巡检（LLM Wiki lint 六项在 NF 的落位）：悬空引用 / 孤儿 / 时效 / 溯源 / 声明。"""
    issues: List[str] = []
    warns: List[str] = []
    d_issues, _d_warns, stats = scan(root)
    issues += d_issues
    issues += verify_transform(root)[0]
    issues += verify_usage(root)[0]
    issues += verify_reuse(root)[0]
    entry_ids = [p.name[:-3] for p in sorted((Path(root) / "library").glob("NF-*.md"))]
    idx_rel = Path(root) / "library" / "INDEX.md"
    idx = idx_rel.read_text(encoding="utf-8") if idx_rel.is_file() else ""
    dangling = _dangling_refs(root)
    for d in sorted(set(dangling)):
        issues.append("悬空引用（提及但无件）：%s" % d)
    orphan = _orphan_entries(entry_ids, idx)
    for o in orphan:
        issues.append("孤儿条目（未出现在 INDEX 生成区）：%s" % o)
    no_stale = _missing_stale(root)
    for n in no_stale:
        warns.append("条目未声明 stale_after（时效无法判定）：%s" % n)
    stats.update({"entries": len(entry_ids), "orphan": len(orphan),
                  "dangling": len(set(dangling)), "no_stale_after": len(no_stale)})
    return issues, warns, stats
