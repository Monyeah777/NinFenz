"""审计 / 验收门禁（Audit Report + Acceptance/Sign-off + Baseline）。

真源：`protocol/audit.json`（规范件：审计该怎么写）+ `results/audit/*.md`（说明件：审计内容）。

判据（全部可证，零第三方依赖）：
- 声明：schema、required_fields、verdict 词表、rules 非空；
- 带审计头的报告：必填齐；verdict 在词表；date 为 YYYY-MM-DD；
  **`subjects` 每条 `路径:sha256` 必须与当前文件一致**——对象一改，旧审计即失效；
  `accepted_by` 出现则必须有 `accepted_at`（验收签收双要素）；
- 无审计头的存量件：按 **WARN** 挂账（legacy），不判死；
- `rebind()`：对象改动后**机械重绑** subjects 的 digest（`nf audit rebind --note`）——
  只逐行替换 digest（不重排 frontmatter），并把重审理由落成正文首行（同一理由不重复追加）。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import atomic_write
from core import doc_family
from core.library import parse_frontmatter

DECL_REL = "protocol/audit.json"
GLOB = "results/audit/*.md"
SCHEMA = "nf-audit/1"
_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- M_AUDIT 门面
# （`nf design audit` 的实现此前依赖本模块的 init_audit/check_audit/scan_audit，
#   但这三个名字在本模块被审计报告族取代后消失，且调用点曾被同名函数遮蔽
#   （flake8 F811 实证）→ 该子命令实际打到了 nf audit。现按**单源委托**修活：
#   M_AUDIT 的 steelman 模式直接委托 core.steelman（钢人节判据的唯一实现），
#   未实装的 blindspot/full 模式 fail-closed 并给修复指引——不编造语义。）

def init_audit(question: str, context: str = "", decider: str = "",
               mode: str = "steelman", path=None) -> str:
    """M_AUDIT init（mode=steelman）：委托 core.steelman.init_worksheet。"""
    from core import steelman
    if mode != "steelman":
        raise ValueError(
            "M_AUDIT 模式 %r 未实装（修复指引：用 --mode steelman；blindspot/full 的"
            "模板与判据尚未成文，须先落规范再实现——见 docs_f2-decision-steelman.md）" % mode)
    return steelman.init_worksheet(question, context=context, decider=decider, path=path)


def check_audit(target) -> List[str]:
    """M_AUDIT check：委托 core.steelman.check_worksheet（同一套钢人节判据）。"""
    from core import steelman
    from pathlib import Path as _Path
    p = _Path(target)
    if not p.is_file():
        return ["审计件不存在：%s（修复指引：先 nf design audit init 生成工作单）" % p]
    return steelman.check_worksheet(p.read_text(encoding="utf-8"))


def scan_audit(root: str = ".") -> List[str]:
    """M_AUDIT ls：委托 core.steelman.scan_steelman（设计审计记录索引）。"""
    from core import steelman
    return steelman.scan_steelman(root)


def decl(root: str = ".") -> Dict[str, Any]:
    return doc_family.load_decl(root, DECL_REL)


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries(root: str = ".") -> List[Dict[str, Any]]:
    return doc_family.entries(root, GLOB)


def check_doc(root: str, rel: str) -> Tuple[List[str], Dict[str, Any]]:
    """单件机检 → (issues, stats)。无审计头者返回空 issues + legacy 统计。"""
    p = Path(root) / rel
    if not p.is_file():
        return ["审计件不存在：%s" % rel], {}
    d = decl(root)
    fm, _body = parse_frontmatter(p.read_text(encoding="utf-8"))
    fm = fm or {}
    if not fm.get("id"):
        return [], {"legacy": True, "subjects": 0}
    issues: List[str] = doc_family.frontmatter_issues(
        fm, d, required=("id", "date", "scope", "verdict", "auditor", "subjects"),
        vocab_key="verdict_vocabulary", field="verdict",
        default_vocab=("pass", "fail", "warn"))
    subs = fm.get("subjects") or []
    if isinstance(subs, str):
        subs = [subs]
    ok_subs = 0
    for s in subs:
        t = str(s).strip()
        if ":" not in t:
            issues.append("subjects 条目格式须为 路径:sha256：%s" % t[:40])
            continue
        rel_p, want = t.rsplit(":", 1)
        sp = Path(root) / rel_p.replace("\\", "/")
        if not sp.is_file():
            issues.append("被审对象不存在：%s" % rel_p)
            continue
        if _sha(sp) != want.strip():
            issues.append("被审对象已变，旧审计失效：%s（修复指引：重审并更新 digest）" % rel_p)
            continue
        ok_subs += 1
    if fm.get("accepted_by") and not _DATED.match(str(fm.get("accepted_at") or "")):
        issues.append("有 accepted_by 但 accepted_at 缺失或格式非法（签收须双要素）")
    return issues, {"legacy": False, "subjects": ok_subs}


def scan(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """声明 + 全部审计件 → (issues, warns, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    d = decl(root)
    if not d:
        return ["缺审计协议声明 %s" % DECL_REL], warns, {}
    if str(d.get("schema") or "") != SCHEMA:
        issues.append("审计协议 schema 不匹配（期望 %s）" % SCHEMA)
    if tuple(d.get("verdict_vocabulary") or ()) != ("pass", "fail", "warn"):
        issues.append("verdict 词表与判据不一致（期望 pass/fail/warn）")
    if not (d.get("rules") or []):
        issues.append("rules 不得为空（审计纪律必须成文）")
    rows = entries(root)
    legacy, subs = [], 0
    for e in rows:
        i, st = check_doc(root, e["path"])
        if st.get("legacy"):
            legacy.append(e["file"])
            continue
        issues += ["%s：%s" % (e["fm"].get("id") or e["file"], x) for x in i]
        subs += st.get("subjects", 0)
    if legacy:
        warns.append("存量审计件无审计头（legacy，按回合收）：%d 件 —— %s"
                     % (len(legacy), "、".join(legacy[:3])))
    if not rows:
        warns.append("暂无审计件（%s）" % GLOB)
    return issues, warns, {"audits": len(rows), "with_header": len(rows) - len(legacy),
                           "legacy": len(legacy), "subjects_ok": subs}


# ---------------------------------------------------------------- 重审重绑
_SUBJECT_LINE = re.compile(r"^(\s+- )(.+):([0-9a-f]{64})\s*$", re.M)


def _rebind_subjects(root: str, fm: str) -> Tuple[str, List[str]]:
    """frontmatter 文本里逐行替换 `路径:sha256` → (新文本, 被重绑的路径)。"""
    changed: List[str] = []
    out = fm
    for m in list(_SUBJECT_LINE.finditer(fm)):
        rel = m.group(2)
        sp = Path(root) / rel.replace(chr(92), "/")
        if not sp.is_file():
            continue
        now = _sha(sp)
        if now != m.group(3):
            out = out.replace("%s:%s" % (rel, m.group(3)), "%s:%s" % (rel, now))
            changed.append(rel)
    return out, changed


def rebind(root: str = ".", note: str = "", dry_run: bool = False,
           ) -> Tuple[List[str], Dict[str, Any]]:
    """重审并更新 digest → (issues, stats)。

    纪律：**理由必填**（空 → 拒绝）——无理由的重绑就是洗数据；只重绑**已漂移**的条目；
    理由落成正文首行，同一理由不重复追加（此前实测一份审计里叠了 6 条同一说明：重绑必须幂等）。
    """
    issues: List[str] = []
    if not str(note).strip():
        return (["重绑理由为空（修复指引：--note 写明重审理由——无理由的重绑就是洗数据）"],
                {"changed": 0})
    line = "> 重审（%s）：%s" % (date.today().isoformat(), str(note).strip())
    stats: Dict[str, Any] = {"records": 0, "rechained": 0, "subjects": 0, "skipped": 0,
                             "note": line}
    for ent in entries(root):
        rel = str(ent["path"])
        path = Path(root) / rel
        try:
            text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        except OSError as exc:
            issues.append("%s 不可读：%s（修复指引：修好编码/权限）" % (rel, exc))
            continue
        stats["records"] += 1
        parts = text.split("---")
        if len(parts) < 3 or parts[0].strip():
            stats["skipped"] += 1              # legacy：无审计头，不重绑（只挂账）
            continue
        new_fm, changed = _rebind_subjects(root, parts[1])
        if not changed:
            continue
        body = "---".join(parts[2:])
        if line not in body:
            body = chr(10) + line + chr(10) + body
        stats["rechained"] += 1
        stats["subjects"] += len(changed)
        if not dry_run:
            atomic_write.write_text(path, "---" + new_fm + "---" + body)
    return issues, stats
