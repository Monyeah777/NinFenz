"""决策记录（ADR）正式与否定用例。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import decisions as dc  # noqa: E402

GOOD = """---
id: ADR-0001
title: t
status: proposed
date: 2026-09-15
supersedes: —
superseded_by: —
evidence: [art.md, check1]
---

## 背景
b
## 决策
d
## 后果
c
"""


def _mk(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _scene(tmp, text=GOOD, name="ADR-0001-t.md", receipts=None, extra=None):
    _mk(tmp, "verify.sh", "check1(){ :; }\n")
    _mk(tmp, "art.md", "x")
    _mk(tmp, "decisions/" + name, text)
    _mk(tmp, dc.RECEIPTS_REL, json.dumps({"entries": receipts or []}, ensure_ascii=False))
    for rel, body in (extra or {}).items():
        _mk(tmp, rel, body)
    dc.write_projection(tmp)
    return tmp


class TestRealRepo(unittest.TestCase):
    def test_scan_clean(self):
        issues, _w, stats = dc.scan(str(ROOT))
        self.assertEqual(issues, [])
        self.assertEqual(dc.check_projection(str(ROOT)), [])
        self.assertGreaterEqual(stats["decisions"], 3)

    def test_accepted_are_receipt_anchored(self):
        import json as _json
        doc = _json.loads((ROOT / "protocol/RECEIPTS.json").read_text(encoding="utf-8"))
        ids = {e["id"] for e in doc["entries"]}
        for e in dc.entries(str(ROOT)):
            if e["fm"].get("status") == "accepted":
                self.assertIn(e["path"], ids, e["path"])


class TestNegatives(unittest.TestCase):
    def test_id_filename_mismatch_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(), name="ADR-0002-t.md")
        self.assertTrue(any("与文件名不一致" in i for i in dc.scan(tmp)[0]))

    def test_missing_section_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(), text=GOOD.replace("## 后果", "## 影响"))
        self.assertTrue(any("正文缺段落" in i for i in dc.scan(tmp)[0]))

    def test_unresolvable_evidence_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(), text=GOOD.replace("art.md", "nowhere.md"))
        self.assertTrue(any("无法解析" in i for i in dc.scan(tmp)[0]))

    def test_unanchored_accepted_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(), text=GOOD.replace("status: proposed",
                                                          "status: accepted"))
        self.assertTrue(any("未被协议回执锚定" in i for i in dc.scan(tmp)[0]))
        _scene(tmp, text=GOOD.replace("status: proposed", "status: accepted"),
               receipts=[{"id": "decisions/ADR-0001-t.md"}])
        self.assertEqual([i for i in dc.scan(tmp)[0] if "回执锚定" in i], [])

    def test_supersede_cycle_is_fail(self):
        tmp = tempfile.mkdtemp()
        a = GOOD.replace("superseded_by: —", "superseded_by: ADR-0002")
        b = (GOOD.replace("id: ADR-0001", "id: ADR-0002")
                 .replace("superseded_by: —", "superseded_by: ADR-0001"))
        _scene(tmp, text=a, name="ADR-0001-t.md", extra={"decisions/ADR-0002-t.md": b})
        dc.write_projection(tmp)
        self.assertTrue(any("成环" in i for i in dc.scan(tmp)[0]))

    def test_projection_drift_is_fail(self):
        tmp = _scene(tempfile.mkdtemp())
        _mk(tmp, dc.INDEX_REL, "# hand written\n")
        self.assertTrue(dc.check_projection(tmp))


ERRATA_REL = "decisions/ERRATA.json"
ERRATA_SCHEMA = "nf-decisions-errata/1"


def errata_issues(root: str):
    """勘误登记的两条确定性判据（**不腐** / **不作假**）→ issue 列表。

    为什么在测试层（2026-10-14）：本判据的天然落点是 `core/decisions.py::scan`，但该件在棘轮
    冻结面上，给它加行须重冻基线；而当时工作区有另一个会话的整波改名在飞（100 项未提交），
    重冻 = 给中间态盖章（本仓明令禁止）。测试层同样随 check12 常驻生效，且**不动冻结面**。
    """
    from core import doc_family
    p = Path(root, ERRATA_REL)
    if not p.is_file():
        return [ERRATA_REL + " 缺失（修复指引：补声明件，或在 README 里撤掉镜像表）"]
    doc = json.loads(p.read_text(encoding="utf-8"))
    out = []
    if doc.get("schema") != ERRATA_SCHEMA:
        out.append("{} 的 schema 不匹配：{}".format(ERRATA_REL, doc.get("schema")))
    live = {str(e["fm"].get("id")): e["fm"] for e in dc.entries(root)}
    checks = doc_family.check_numbers(root)
    vocab = doc.get("fields_vocabulary") or []
    for ent in doc.get("entries") or []:
        adr = str(ent.get("adr") or "")
        if adr not in live:
            out.append(f"勘误指向不在册 ADR：{adr}")
            continue
        field = str(ent.get("field") or "")
        if field not in vocab:
            out.append(f"{adr} 的勘误字段越词表：{field}")
            continue
        vals = [str(v) for v in (live[adr].get(field) or [])]
        if str(ent.get("was")) not in vals:
            out.append(f"{adr} 的勘误已过期：正文该字段里已无 {ent.get('was')}"
                       "（修复指引：重审或撤销该条）")
        out += ["{} 的勘误 now 无法解析：{}（{}）".format(adr, ent.get("now"), i)
                for i in doc_family.refs_issues(root, [str(ent.get("now"))], checks,
                                                label="勘误 now", allow_adr=True)]
    return out


class ErrataTest(unittest.TestCase):
    def test_real_repo_errata_is_clean(self):
        self.assertEqual([], errata_issues(str(ROOT)))

    def test_stale_erratum_is_fail(self):
        tmp = _scene(tempfile.mkdtemp())
        _mk(tmp, ERRATA_REL, json.dumps({"schema": ERRATA_SCHEMA,
            "fields_vocabulary": ["evidence"],
            "entries": [{"adr": "ADR-0001", "field": "evidence",
                         "was": "check99", "now": "art.md"}]}))
        self.assertTrue(any("已过期" in i for i in errata_issues(tmp)))

    def test_unresolvable_now_is_fail(self):
        tmp = _scene(tempfile.mkdtemp())
        _mk(tmp, ERRATA_REL, json.dumps({"schema": ERRATA_SCHEMA,
            "fields_vocabulary": ["evidence"],
            "entries": [{"adr": "ADR-0001", "field": "evidence",
                         "was": "art.md", "now": "nowhere.md"}]}))
        self.assertTrue(any("无法解析" in i for i in errata_issues(tmp)))

    def test_unknown_adr_is_fail(self):
        tmp = _scene(tempfile.mkdtemp())
        _mk(tmp, ERRATA_REL, json.dumps({"schema": ERRATA_SCHEMA,
            "fields_vocabulary": ["evidence"],
            "entries": [{"adr": "ADR-9999", "field": "evidence",
                         "was": "art.md", "now": "art.md"}]}))
        self.assertTrue(any("不在册 ADR" in i for i in errata_issues(tmp)))


if __name__ == "__main__":
    unittest.main()
