"""core.decisions 私有实现分片 2/2（对外只经 core.decisions 门面导入）：_required_issues 等"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

from core import doc_family

from ._part1 import (
    _ABS,
    _ADR,
    _CHECK,
    _CTRL,
    _DATED,
    BEGIN,
    DASH,
    END,
    GLOB,
    INDEX_REL,
    MAX_EVIDENCE_LEN,
    REQUIRED,
    SECTIONS,
    STATUSES,
    Adr,
    Corpus,
    Issue,
    ScanResult,
    _r_identity,
    load,
)


def _required_issues(a: Adr) -> Iterator[Issue]:
    for k in REQUIRED:
        val = a.evidence if k == "evidence" else getattr(a, k)
        if not val:
            yield Issue("ADR020", a.path, f"{a.tag} 缺必填字段：{k}")


def _format_issues(a: Adr) -> Iterator[Issue]:
    if a.status and a.status not in STATUSES:
        yield Issue("ADR021", a.path,
                    f"{a.tag} 的 status 越词表：{a.status}（{'/'.join(STATUSES)}）")
    if a.date and not _DATED.match(a.date):
        yield Issue("ADR022", a.path, f"{a.tag} 的 date 非 YYYY-MM-DD：{a.date}")
    for sec in SECTIONS:
        if sec not in a.body:
            yield Issue("ADR023", a.path, f"{a.tag} 正文缺段落：{sec}")


def _r_fields(c: Corpus) -> Iterator[Issue]:
    for a in c.adrs:
        yield from _required_issues(a)
        yield from _format_issues(a)


def _shape_reason(rel: str) -> str | None:
    """路径形状：NUL / 绝对路径 / .. 逃逸（不碰文件系统）。"""
    if "\x00" in rel:
        return "含 NUL 字节"
    raw = rel.replace("\\", "/")
    if _ABS.match(raw):
        return "绝对路径"
    if any(part == ".." for part in raw.split("/")):
        return "路径含 ..（拒绝逃逸）"
    return None


def _target_reason(root: Path, rel: str) -> str | None:
    """目标判定：解析（跟随符号链接）后必须仍是仓库内的**文件**。"""
    try:
        base = root.resolve()
        target = (root / rel.replace("\\", "/")).resolve()
    except OSError as exc:
        return f"路径无法解析：{exc}"
    if target != base and base not in target.parents:
        return "解析后落在仓库外（可能是符号链接逃逸）"
    if not target.exists():
        return "文件不存在"
    if not target.is_file():
        return "不是文件（目录/设备不可作证据）"
    return None


def _path_reason(root: Path, rel: str) -> str | None:
    return _shape_reason(rel) or _target_reason(root, rel)


def _evidence_issue(a: Adr, s: str, c: Corpus) -> Issue | None:
    if not s:
        return Issue("ADR030", a.path, f"{a.tag} 的 evidence 有空项")
    if len(s) > MAX_EVIDENCE_LEN:
        return Issue("ADR031", a.path,
                     f"{a.tag} 的 evidence 单项超长（>{MAX_EVIDENCE_LEN} 字符）")
    m = _CHECK.match(s)
    if m:
        if m.group(1) not in c.checks:
            return Issue("ADR032", a.path, f"{a.tag} 的 evidence 指向不存在的 check：{s}")
        return None
    if _ADR.match(s):
        if s not in c.ids:
            return Issue("ADR033", a.path, f"{a.tag} 的 evidence 指向不在册 ADR：{s}")
        return None
    reason = _path_reason(c.root, s)
    if reason:
        return Issue("ADR034", a.path,
                     f"{a.tag} 的 evidence 无法解析：{s}（{reason}；修复指引："
                     "改为仓库内真实文件、在册 checkN 或 ADR-N）")
    return None


def _r_evidence(c: Corpus) -> Iterator[Issue]:
    for a in c.adrs:
        for item in a.evidence:
            issue = _evidence_issue(a, item.strip(), c)
            if issue is not None:
                yield issue


def _r_lifecycle(c: Corpus) -> Iterator[Issue]:
    """生命周期面：accepted 必须被回执锚定；superseded 必须给出去向。"""
    for a in c.adrs:
        if a.status == "accepted" and c.has_receipts and a.path not in c.receipts:
            yield Issue("ADR040", a.path,
                        f"{a.tag} 已 accepted 但未被协议回执锚定"
                        "（修复指引：nf receipts --write）——未锚定的 accepted 等于可被偷改")
        if a.status == "superseded" and a.superseded_by in DASH:
            yield Issue("ADR041", a.path, f"{a.tag} 标 superseded 但缺 superseded_by")


def _supersedes_issues(a: Adr, ids: Mapping[str, Adr]) -> Iterator[Issue]:
    if a.id and a.supersedes == a.id:
        yield Issue("ADR042", a.path, f"{a.tag} 的 supersedes 指向自身")
    if not a.supersedes or a.supersedes in DASH:
        return
    other = ids.get(a.supersedes)
    if other is None:
        yield Issue("ADR043", a.path, f"{a.tag} 的 supersedes 指向不在册编号：{a.supersedes}")
    elif other.superseded_by != a.id:
        yield Issue("ADR044", a.path,
                    f"{a.tag} 的 supersedes={a.supersedes}，但 {a.supersedes} 的 "
                    f"superseded_by 是 {other.superseded_by or '—'}（互指断裂）")


def _superseded_by_issues(a: Adr, ids: Mapping[str, Adr]) -> Iterator[Issue]:
    if not a.superseded_by or a.superseded_by in DASH:
        return
    other = ids.get(a.superseded_by)
    if other is None:
        yield Issue("ADR045", a.path,
                    f"{a.tag} 的 superseded_by 指向不在册编号：{a.superseded_by}")
    elif other.supersedes != a.id:
        yield Issue("ADR046", a.path,
                    f"{a.tag} 的 superseded_by={a.superseded_by}，但 {a.superseded_by} 的 "
                    f"supersedes 是 {other.supersedes or '—'}（互指断裂）")


def _r_links(c: Corpus) -> Iterator[Issue]:
    ids = c.ids
    for a in c.adrs:
        yield from _supersedes_issues(a, ids)
        yield from _superseded_by_issues(a, ids)


def _cycle_key(cycle: tuple[str, ...]) -> tuple[str, ...]:
    """把环旋转到最小元素开头，保证同一环只报一次。"""
    if not cycle:
        return cycle
    i = cycle.index(min(cycle))
    return cycle[i:] + cycle[:i]


def _edge_map(c: Corpus) -> dict[str, str]:
    return {a.id: a.superseded_by for a in c.adrs
            if a.id and a.superseded_by and a.superseded_by not in DASH}


def _walk(start: str, edges: Mapping[str, str],
          color: dict[str, int]) -> tuple[str, ...] | None:
    """三色 DFS 的一步：走到无路或撞灰为止，返回规范化后的环（无环 → None）。"""
    path: list[str] = []
    index: dict[str, int] = {}
    cur = start
    while cur and not color.get(cur):
        color[cur] = 1
        index[cur] = len(path)
        path.append(cur)
        cur = edges.get(cur, "")
    cycle = tuple(path[index[cur]:]) if cur and color.get(cur) == 1 else ()
    for node in path:
        color[node] = 2
    return _cycle_key(cycle) if cycle else None


def _r_chains(c: Corpus) -> Iterator[Issue]:
    """任何环都报——旧实现只报「回到起点」的那一种。"""
    edges = _edge_map(c)
    color: dict[str, int] = {}
    reported: set[tuple[str, ...]] = set()
    for start in sorted(edges):
        if color.get(start):
            continue
        cycle = _walk(start, edges, color)
        if cycle and cycle not in reported:
            reported.add(cycle)
            yield Issue("ADR050", "", f"取代链成环：{' → '.join(cycle + (cycle[0],))}")


RULES = (_r_identity, _r_fields, _r_evidence, _r_lifecycle, _r_links, _r_chains)


# ----------------------------------------------------------------- 用例层
def _heads(edges: set[tuple[str, str]]) -> int:
    targets = {t for _, t in edges}
    return sum(1 for s, _ in edges if s not in targets)


def _edges(c: Corpus) -> set[tuple[str, str]]:
    return {(a.id, a.superseded_by) for a in c.adrs
            if a.id and a.superseded_by and a.superseded_by not in DASH}


def _stats(c: Corpus) -> dict[str, object]:
    edges = _edges(c)
    return {"decisions": len(c.ids),
            "accepted": sum(1 for a in c.adrs if a.status == "accepted"),
            "superseded": sum(1 for a in c.adrs if a.status == "superseded"),
            "chains": _heads(edges)}


def analyze(root: str = ".") -> ScanResult:
    """结构化机检（新调用方用这个；scan() 是它的字符串兼容面）。"""
    c = load(root)
    issues: list[Issue] = list(c.issues)
    if not c.adrs:
        issues.append(Issue("ADR005", GLOB, f"未发现任何 ADR（{GLOB}）"))
    for rule in RULES:
        issues.extend(rule(c))
    issues.sort(key=lambda i: i.key())
    return ScanResult(issues=tuple(issues), warnings=(), stats=_stats(c))


def scan(root: str = ".") -> tuple[list[str], list[str], dict[str, object]]:
    """机检 → (issues, warns, stats)。保持旧形状，供 nf decisions 直接打印。"""
    res = analyze(root)
    return ([str(i) for i in res.issues], [str(w) for w in res.warnings], dict(res.stats))


# ----------------------------------------------------------------- 投影层
def _cell(value: object) -> str:
    """表格单元转义：竖线/换行/控制字符不得破坏投影（旧实现裸拼 = 表格注入）。"""
    s = "" if value is None else str(value)
    s = s.replace("\\", "\\\\").replace("|", "\\|")
    s = _CTRL.sub(" ", s).strip()
    return s or "—"


def render_corpus(c: Corpus) -> str:
    out = [BEGIN, "", "## 决策登记表（由各 ADR frontmatter 生成，勿手改）", "",
           "| 编号 | 标题 | 状态 | 日期 | 取代 |", "|---|---|---|---|---|"]
    for a in c.adrs:
        out.append(f"| {_cell(a.id or a.name)} | {_cell(a.title)} | {_cell(a.status)} | "
                   f"{_cell(a.date)} | "
                   f"{'—' if a.superseded_by in DASH else _cell(a.superseded_by)} |")
    out += ["", "> 真源 = `decisions/ADR-*.md` 的 frontmatter；本表为投影（`nf decisions reindex` 重建）。",
            "", END]
    return "\n".join(out)


def render_index(root: str = ".") -> str:
    return render_corpus(load(root))


def write_projection(root: str = ".") -> dict[str, object]:
    return doc_family.write_index(
        root, index_rel=INDEX_REL, header="# NF 决策记录索引（INDEX）\n\n",
        begin=BEGIN, end=END, block=render_index(root))


def check_projection(root: str = ".") -> list[str]:
    return doc_family.check_index(
        root,
        opts=doc_family.IndexOptions(
            index_rel=INDEX_REL,
            begin=BEGIN,
            end=END,
            block=render_index(root),
            missing_hint='nf decisions reindex',
            mismatch='决策登记表与实时重算不一致（跑 nf decisions reindex）',
        ),
    )
