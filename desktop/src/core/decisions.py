"""决策记录门禁（ADR：一条决策一编号，采纳后不改不删，只可被取代）。

真源 = decisions/ADR-*.md 的 frontmatter + 正文；decisions/INDEX.md 是投影。

判据（全部可证，零第三方依赖）：
- 编号：id 必须等于文件名前缀 ADR-\\d{4}；全库唯一；
- 状态：status ∈ {proposed, accepted, superseded, deprecated}；date 为 YYYY-MM-DD；
- 三段齐：正文必须含 ## 背景 / ## 决策 / ## 后果；
- 取代链：目标在册、无悬空、无环（DFS 判定：任何环都报，不只回到起点那种）；
  supersedes 与 superseded_by 必须互指（A.supersedes=B ⇔ B.superseded_by=A）；
- 证据：每条须解析到仓库真实**文件**、checkN（verify.sh 在册）或**在册** ADR-N；
  路径必须落在仓库根内（拒绝绝对路径 / .. 逃逸 / 目录 / 指向仓外的符号链接）；
- 不可改：status: accepted 的 ADR 必须已被协议回执锚定（protocol/RECEIPTS.json）——
  正文一改回执即失效，于是「改了」必然被 check35 抓住，决策只能靠新增 + 互指 supersede 演进。

架构（2026-10-19 重构：端口-适配器 + 不可变模型 + 结构化诊断）：
- Adr / Issue 是值对象（frozen dataclass）；规则是纯函数，逐条带稳定 code（ADR0xx）；
- 文件系统 / frontmatter / 回执解析只出现在 load() 这一层；畸形输入一律转 Issue
  （fail-closed），不以 traceback 或静默放行收场；
- scan() 保留旧的 (list[str], list[str], dict) 形状以兼容 nf decisions 既有调用点；
  analyze() 暴露结构化结果（Issue 带 code/severity/path）给新调用方。
"""
from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from core import doc_family, json_doc
from core.library_entries import parse_frontmatter

GLOB = "decisions/ADR-*.md"
INDEX_REL = "decisions/INDEX.md"
RECEIPTS_REL = "protocol/RECEIPTS.json"
BEGIN = "<!-- BEGIN GENERATED: decisions-index -->"
END = "<!-- END GENERATED: decisions-index -->"
STATUSES = ("proposed", "accepted", "superseded", "deprecated")
SECTIONS = ("## 背景", "## 决策", "## 后果")
REQUIRED = ("title", "status", "date", "evidence")
DASH = frozenset({"—", "-", ""})
MAX_EVIDENCE_LEN = 512
FAIL, WARN = "fail", "warn"

_ID = re.compile(r"^ADR-(\d{4})$")
_FILE_ID = re.compile(r"^ADR-(\d{4})-")
_CHECK = re.compile(r"^check(\d+)$")
_ADR = re.compile(r"^ADR-\d{4}$")
_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ABS = re.compile(r"^(?:/|[A-Za-z]:)")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


# ----------------------------------------------------------------- 值对象
@dataclass(frozen=True)
class Issue:
    """一条结构化诊断：稳定 code + 归属路径 + 人读消息 + 严重度。"""

    code: str
    path: str
    message: str
    severity: str = FAIL

    def __str__(self) -> str:
        return self.message

    def key(self) -> tuple[str, str, str]:
        return (self.path, self.code, self.message)


@dataclass(frozen=True)
class Adr:
    """不可变 ADR 视图：字段已规范化，规则只读它、不再碰原始 dict。"""

    path: str
    name: str
    id: str
    title: str
    status: str
    date: str
    evidence: tuple[str, ...]
    supersedes: str
    superseded_by: str
    body: str
    raw: Mapping[str, object] = field(  # type: ignore[assignment]
        default=None, repr=False, compare=False)

    @property
    def tag(self) -> str:
        return self.id or self.name


@dataclass(frozen=True)
class Corpus:
    """一次装载的快照：条目 + 装载期问题 + 真源集合。"""

    root: Path
    adrs: tuple[Adr, ...]
    issues: tuple[Issue, ...]
    checks: frozenset[str]
    receipts: frozenset[str]
    has_receipts: bool

    @property
    def ids(self) -> dict[str, Adr]:
        out: dict[str, Adr] = {}
        for a in self.adrs:
            if a.id and a.id not in out:
                out[a.id] = a
        return out


@dataclass(frozen=True)
class ScanResult:
    issues: tuple[Issue, ...]
    warnings: tuple[Issue, ...]
    stats: Mapping[str, object]

    def failed(self) -> bool:
        return any(i.severity == FAIL for i in self.issues)


# ----------------------------------------------------------------- 边界层
def _txt(fm: Mapping[str, object], key: str) -> str:
    v = fm.get(key)
    return "" if v is None else str(v).strip()


def _as_list(v: object) -> tuple[str, ...]:
    """规范化 evidence：**标量当一项**（旧实现按字符迭代 = 类型混淆）。"""
    if v is None:
        return ()
    if isinstance(v, str):
        return (v.strip(),) if v.strip() else ()
    if isinstance(v, (list, tuple)):
        return tuple(str(x).strip() for x in v)
    return (str(v).strip(),)


def _fm_lines(text: str) -> Iterator[str]:
    """frontmatter 顶层行（到闭合 --- 为止；不含首行与闭合行）。"""
    for ln in text.splitlines()[1:]:
        if ln.strip() == "---":
            return
        yield ln


def _top_keys(text: str) -> list[str]:
    out: list[str] = []
    for ln in _fm_lines(text):
        s = ln.strip()
        if not s or s.startswith("#") or ln.startswith((" ", "\t")):
            continue
        if ":" in ln:
            out.append(ln.split(":", 1)[0].strip())
    return out


def _duplicate_keys(text: str) -> tuple[str, ...]:
    """顶层重复键：解析器静默让后者覆盖前者，必须显式报出来。"""
    keys = _top_keys(text)
    return tuple(sorted({k for k in keys if keys.count(k) > 1}))


def _empty_evidence_slots(text: str) -> int:
    """evidence 空槽数：解析器会静默丢弃空项，必须在装载期报出来。"""
    for ln in _fm_lines(text):
        if not ln.strip().startswith("evidence:"):
            continue
        v = ln.split(":", 1)[1].strip()
        if not (v.startswith("[") and v.endswith("]")):
            return 0
        return sum(1 for part in v[1:-1].split(",") if not part.strip())
    return 0


def _structure_issues(name: str, rel: str, text: str) -> list[Issue]:
    """装载期的结构诊断：重复键 / evidence 空槽（两者都会被解析器静默吞掉）。"""
    out: list[Issue] = []
    dups = _duplicate_keys(text)
    if dups:
        out.append(Issue("ADR003", rel,
                         f"{name} 的 frontmatter 重复键：{'、'.join(dups)}"
                         "（后者会静默覆盖前者）"))
    empties = _empty_evidence_slots(text)
    if empties:
        out.append(Issue("ADR030", rel,
                         f"{name} 的 evidence 有空项 {empties} 个（解析器会静默丢弃，"
                         "修复指引：删掉多余逗号或补齐条目）"))
    return out


def _read_one(p: Path, root: Path) -> tuple[Adr | None, tuple[Issue, ...]]:
    rel = p.relative_to(root).as_posix()
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return None, (Issue("ADR000", rel,
                            f"{p.name} 非 UTF-8：{exc}（修复指引：另存为 UTF-8）"),)
    except OSError as exc:
        return None, (Issue("ADR000", rel, f"{p.name} 读取失败：{exc}"),)
    if not text.startswith("---"):
        return None, (Issue("ADR001", rel, f"{p.name} 缺 frontmatter（首字符不是 ---）"),)
    fm, body = parse_frontmatter(text)
    if not fm:
        return None, (Issue("ADR002", rel, f"{p.name} 的 frontmatter 为空或未闭合"),)
    adr = Adr(path=rel, name=p.name, id=_txt(fm, "id"), title=_txt(fm, "title"),
              status=_txt(fm, "status"), date=_txt(fm, "date"),
              evidence=_as_list(fm.get("evidence")),
              supersedes=_txt(fm, "supersedes"), superseded_by=_txt(fm, "superseded_by"),
              body=body, raw=fm)
    return adr, tuple(_structure_issues(p.name, rel, text))


def _read_receipts(base: Path) -> tuple[frozenset[str], bool, Issue | None]:
    p = base / RECEIPTS_REL
    if not p.is_file():
        return frozenset(), False, None
    try:
        doc = json_doc.load(p, dict, what=RECEIPTS_REL)
        ids = frozenset(str(e.get("id")) for e in (doc.get("entries") or []))
    except Exception as exc:                      # 边界：坏件转 Issue，别把整道门禁炸掉
        return frozenset(), True, Issue(
            "ADR004", RECEIPTS_REL,
            f"回执声明不可解析：{exc}（修复指引：nf receipts --scope protocol --write）")
    return ids, True, None


def load(root: str = ".") -> Corpus:
    """装载语料（唯一接触文件系统的入口）。"""
    base = Path(root)
    adrs: list[Adr] = []
    issues: list[Issue] = []
    for p in sorted(base.glob(GLOB)):
        adr, got = _read_one(p, base)
        issues.extend(got)
        if adr is not None:
            adrs.append(adr)
    adrs.sort(key=lambda a: (a.id, a.name))
    receipts, has_receipts, rec_issue = _read_receipts(base)
    if rec_issue is not None:
        issues.append(rec_issue)
    return Corpus(root=base, adrs=tuple(adrs), issues=tuple(issues),
                  checks=frozenset(doc_family.check_numbers(root)),
                  receipts=receipts, has_receipts=has_receipts)


def entries(root: str = ".") -> list[dict[str, object]]:
    """兼容面：旧调用点要的 {path,file,fm,body}（按编号排序）。"""
    return [{"path": a.path, "file": a.name, "fm": dict(a.raw), "body": a.body}
            for a in load(root).adrs]


# ----------------------------------------------------------------- 规则层
def _r_identity(c: Corpus) -> Iterator[Issue]:
    seen: dict[str, str] = {}
    for a in c.adrs:
        if not a.id:
            yield Issue("ADR010", a.path, f"{a.name} 缺 frontmatter id")
            continue
        if not _ID.match(a.id):
            yield Issue("ADR011", a.path, f"{a.name} 的 id 不合法（须 ADR-四位数字）：{a.id}")
        m = _FILE_ID.match(a.name)
        if not m or f"ADR-{m.group(1)}" != a.id:
            yield Issue("ADR012", a.path, f"{a.name} 的 id 与文件名不一致：{a.id}")
        if a.id in seen:
            yield Issue("ADR013", a.path, f"ADR 编号重复：{a.id}（{seen[a.id]} 与 {a.name}）")
        else:
            seen[a.id] = a.name


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
        root, index_rel=INDEX_REL, begin=BEGIN, end=END, block=render_index(root),
        missing_hint="nf decisions reindex",
        mismatch="决策登记表与实时重算不一致（跑 nf decisions reindex）")
