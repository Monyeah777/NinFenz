"""决策记录（ADR）正式与否定用例。

三组分工：
1) 正式面：真仓必须全绿、accepted 必须被回执锚定、投影必须与实时重算一致；
2) 规则面：每条判据都有反例（否定用例）；
3) 边界面：畸形 / 恶意输入必须转成**结构化诊断**（fail-closed）——
   不得 traceback，也不得静默放行（空 frontmatter、重复键、路径逃逸、类型混淆）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import decisions as dc  # noqa: E402


def _adr(adr_id="ADR-0001", status="proposed", supersedes="—", superseded_by="—",
         evidence="[art.md, check1]", title="t"):
    return (
        f"---\nid: {adr_id}\ntitle: {title}\nstatus: {status}\ndate: 2026-09-15\n"
        f"supersedes: {supersedes}\nsuperseded_by: {superseded_by}\n"
        f"evidence: {evidence}\n---\n\n"
        "## 背景\nb\n## 决策\nd\n## 后果\nc\n"
    )


GOOD = _adr()


def _mk(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _multi(tmp, adrs, receipts=None):
    """多 ADR 场景：verify.sh / 证据文件 / 回执 / 投影 一次铺好。"""
    _mk(tmp, "verify.sh", "check1(){ :; }\n")
    _mk(tmp, "art.md", "x")
    for rel, text in adrs.items():
        _mk(tmp, rel, text)
    _mk(tmp, dc.RECEIPTS_REL, json.dumps({"entries": receipts or []}, ensure_ascii=False))
    dc.write_projection(tmp)
    return tmp


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
        doc = json.loads((ROOT / "protocol/RECEIPTS.json").read_text(encoding="utf-8"))
        ids = {e["id"] for e in doc["entries"]}
        for e in dc.entries(str(ROOT)):
            if e["fm"].get("status") == "accepted":
                self.assertIn(e["path"], ids, e["path"])

    def test_analysis_is_deterministic(self):
        codes = [i.code for i in dc.analyze(str(ROOT)).issues]
        self.assertEqual(codes, [i.code for i in dc.analyze(str(ROOT)).issues])

    def test_external_runner_boundary_is_decided(self):
        # 2026-10-25：ADR-0008（外部一致性运行器边界）属**真实决策**，已随
        # decisions/ADR-0000 的裁决迁入私有 Plan 仓归档；公开仓只留模板。
        # 该断言只在 ADR 在场时生效——缺席时跳过（决策本身仍有效，只是不公开）。
        hit = next((e for e in dc.entries(str(ROOT))
                    if e["fm"].get("id") == "ADR-0008"), None)
        if hit is None:
            self.skipTest("ADR-0008 已迁私有仓（见 decisions/ADR-0000），公开面不校验内容")
        self.assertEqual("accepted", hit["fm"].get("status"))
        body = hit["body"]
        for phrase in (
            "独立仓库或独立进程",
            "不得只调用 NF 的",
            "范围显式",
            "未执行不等于通过",
        ):
            self.assertIn(phrase, body)


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
        tmp = _multi(tempfile.mkdtemp(), {
            "decisions/ADR-0001-t.md": _adr(superseded_by="ADR-0002"),
            "decisions/ADR-0002-t.md": _adr("ADR-0002", supersedes="ADR-0001",
                                            superseded_by="ADR-0001"),
        })
        self.assertTrue(any("成环" in i for i in dc.scan(tmp)[0]))

    def test_one_way_supersede_is_fail(self):
        tmp = _multi(tempfile.mkdtemp(), {
            "decisions/ADR-0001-t.md": _adr(),
            "decisions/ADR-0002-t.md": _adr("ADR-0002", supersedes="ADR-0001"),
        })
        self.assertTrue(any("互指断裂" in i for i in dc.scan(tmp)[0]))

    def test_mutual_supersede_is_clean(self):
        tmp = _multi(tempfile.mkdtemp(), {
            "decisions/ADR-0001-t.md": _adr(superseded_by="ADR-0002"),
            "decisions/ADR-0002-t.md": _adr("ADR-0002", supersedes="ADR-0001"),
        })
        self.assertEqual([i for i in dc.scan(tmp)[0] if "互指" in i], [])

    def test_projection_drift_is_fail(self):
        tmp = _scene(tempfile.mkdtemp())
        _mk(tmp, dc.INDEX_REL, "# hand written\n")
        self.assertTrue(dc.check_projection(tmp))


class TestChainTopology(unittest.TestCase):
    """取代链拓扑：环判定必须与图论事实一致（旧实现只报"回到起点"的环）。"""

    def test_cycle_not_returning_to_origin_is_fail(self):
        tmp = _multi(tempfile.mkdtemp(), {
            "decisions/ADR-0001-t.md": _adr(superseded_by="ADR-0002"),
            "decisions/ADR-0002-t.md": _adr("ADR-0002", superseded_by="ADR-0003"),
            "decisions/ADR-0003-t.md": _adr("ADR-0003", superseded_by="ADR-0002"),
        })
        issues = dc.scan(tmp)[0]
        self.assertTrue(any("成环" in i for i in issues), issues)
        self.assertTrue(any("ADR-0002" in i and "ADR-0003" in i for i in issues), issues)

    def test_self_supersede_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(),
                     text=_adr(supersedes="ADR-0001"))
        self.assertTrue(any("指向自身" in i for i in dc.scan(tmp)[0]))

    def test_chain_of_n_has_no_cycle_and_one_head(self):
        for n in range(2, 8):
            adrs = {}
            for i in range(1, n + 1):
                sb = f"ADR-{i + 1:04d}" if i < n else "—"
                sp = f"ADR-{i - 1:04d}" if i > 1 else "—"
                adrs[f"decisions/ADR-{i:04d}-t.md"] = _adr(
                    f"ADR-{i:04d}", supersedes=sp, superseded_by=sb)
            tmp = _multi(tempfile.mkdtemp(), adrs)
            issues = dc.scan(tmp)[0]
            self.assertEqual([x for x in issues if "成环" in x], [], f"n={n}")
            self.assertEqual(1, dc.analyze(tmp).stats["chains"], f"n={n}")

    def test_closing_the_chain_always_cycles(self):
        for n in range(2, 8):
            adrs = {}
            for i in range(1, n + 1):
                sb = f"ADR-{i + 1:04d}" if i < n else "ADR-0001"
                sp = f"ADR-{i - 1:04d}" if i > 1 else f"ADR-{n:04d}"
                adrs[f"decisions/ADR-{i:04d}-t.md"] = _adr(
                    f"ADR-{i:04d}", supersedes=sp, superseded_by=sb)
            tmp = _multi(tempfile.mkdtemp(), adrs)
            self.assertTrue(any("成环" in x for x in dc.scan(tmp)[0]), f"n={n}")


class TestEvidenceBoundaries(unittest.TestCase):
    def test_unknown_adr_reference_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(),
                     text=_adr(evidence="[ADR-9999]"))
        self.assertTrue(any("不在册 ADR" in i for i in dc.scan(tmp)[0]))

    def test_traversal_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(),
                     text=_adr(evidence="[../outside.md, check1]"))
        issues = dc.scan(tmp)[0]
        self.assertTrue(any("无法解析" in i and ".." in i for i in issues), issues)

    def test_absolute_path_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(),
                     text=_adr(evidence="[/etc/passwd, check1]"))
        self.assertTrue(any("绝对路径" in i for i in dc.scan(tmp)[0]))

    def test_directory_is_not_evidence(self):
        tmp = _scene(tempfile.mkdtemp(),
                     text=_adr(evidence="[decisions, check1]"))
        self.assertTrue(any("不是文件" in i for i in dc.scan(tmp)[0]))

    def test_scalar_evidence_is_one_item_not_chars(self):
        tmp = _scene(tempfile.mkdtemp(), text=_adr(evidence="art.md"))
        self.assertEqual([], dc.scan(tmp)[0])

    def test_empty_item_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(),
                     text=_adr(evidence="[art.md, , check1]"))
        self.assertTrue(any("有空项" in i for i in dc.scan(tmp)[0]))


class TestMalformedInput(unittest.TestCase):
    """畸形输入：一律结构化诊断，绝不 traceback。"""

    def test_missing_frontmatter(self):
        tmp = _scene(tempfile.mkdtemp(),
                     text="# 无 frontmatter\n\n## 背景\nb\n## 决策\nd\n## 后果\nc\n")
        self.assertTrue(any("缺 frontmatter" in i for i in dc.scan(tmp)[0]))

    def test_duplicate_frontmatter_key(self):
        tmp = _scene(tempfile.mkdtemp(),
                     text=_adr().replace("status: proposed",
                                         "status: proposed\nstatus: accepted"))
        self.assertTrue(any("重复键" in i for i in dc.scan(tmp)[0]))

    def test_non_utf8(self):
        tmp = _scene(tempfile.mkdtemp())
        Path(tmp, "decisions/ADR-0002-t.md").write_bytes(
            b"---\nid: ADR-0002\ntitle: \xff\xfe\n---\n")
        self.assertTrue(any("非 UTF-8" in i for i in dc.scan(tmp)[0]))

    def test_broken_receipts_declaration(self):
        tmp = _scene(tempfile.mkdtemp())
        _mk(tmp, dc.RECEIPTS_REL, "{not json")
        issues = dc.scan(tmp)[0]
        self.assertTrue(any("回执声明不可解析" in i for i in issues), issues)

    def test_no_adr_at_all(self):
        tmp = tempfile.mkdtemp()
        _mk(tmp, "verify.sh", "check1(){ :; }\n")
        self.assertTrue(any("未发现任何 ADR" in i for i in dc.scan(tmp)[0]))


class TestProjectionEscaping(unittest.TestCase):
    """投影注入：竖线 / 控制字符不得破坏表格，也不得静默改写。"""

    def test_pipe_in_title_stays_one_row(self):
        tmp = _scene(tempfile.mkdtemp(), text=_adr(title="A|B"))
        text = dc.render_index(tmp)
        rows = [ln for ln in text.splitlines() if ln.startswith("| ADR-0001")]
        self.assertEqual(1, len(rows))
        self.assertIn("A\\|B", rows[0])

    def test_control_chars_are_stripped(self):
        tmp = _scene(tempfile.mkdtemp(), text=_adr(title="a\x00b"))
        self.assertNotIn("\x00", dc.render_index(tmp))

    def test_projection_round_trips_with_escaping(self):
        tmp = _scene(tempfile.mkdtemp(), text=_adr(title="A|B"))
        self.assertEqual([], dc.check_projection(tmp))


ERRATA_REL = "decisions/ERRATA.json"
ERRATA_SCHEMA = "nf-decisions-errata/1"


def errata_issues(root: str):
    """勘误登记的两条确定性判据（不腐 / 不作假）→ issue 列表。"""
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
