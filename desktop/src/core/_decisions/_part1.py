"""core.decisions 私有实现分片 1/2（对外只经 core.decisions 门面导入）：GLOB、INDEX_REL 等"""

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
