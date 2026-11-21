import json
import tempfile
import unittest
from pathlib import Path

from nf_zero_slice import (
    Block, Document, DraftStore, ImportSession, MdSpec, Section, Source,
    Stage, freeform_spec, infer_mappings, load_spec, parse_markdown,
)

HERE = Path(__file__).parent
FIX = HERE / "fixtures"


def read_fixture(name):
    return (FIX / name).read_text(encoding="utf-8")


class ParseTests(unittest.TestCase):
    def test_headings_become_sections(self):
        doc = parse_markdown(read_fixture("brief.md"))
        self.assertEqual(doc.title, "客户简报：社区书店冬季活动")
        self.assertEqual([s.title for s in doc.sections],
                         ["背景", "目标", "必须包含", "不要写"])
        self.assertTrue(any(b.kind == "list" for b in doc.blocks))

    def test_no_headings_freeform(self):
        doc = parse_markdown("第一行标题\n\n第二段内容\n\n第三段")
        self.assertEqual(len(doc.sections), 1)
        self.assertEqual(doc.title, "第一行标题")
        self.assertIn("第三段", doc.sections[0].text())

    def test_table_and_code(self):
        doc = parse_markdown("|a|b|\n|-|-|\n|1|2|\n\n```\nx\n```\n")
        self.assertTrue(any(b.kind == "table" for b in doc.blocks))
        self.assertTrue(any(b.kind == "code" for b in doc.blocks))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            parse_markdown("   \n")


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.doc = parse_markdown(read_fixture("brief.md"))
        self.spec = load_spec(json.loads(read_fixture("brief-spec.json")))

    def test_exact_spec_maps_all(self):
        report = infer_mappings(self.doc, self.spec)
        self.assertEqual(len(report.mappings), 4)
        self.assertEqual(report.missing_required, [])
        self.assertGreater(report.coverage, 0.85)
        targets = {m.target_slot for m in report.mappings}
        self.assertEqual(targets, {"SLOT-BG", "SLOT-GOAL", "SLOT-MUST", "SLOT-NO"})

    def test_unmatched_source_is_kept(self):
        sample = load_spec(json.loads(read_fixture("sample-spec.json")))
        report = infer_mappings(self.doc, sample)
        # content is not dropped; extras are explicit
        self.assertTrue(report.exceptions)
        self.assertTrue(any(m.target_slot is None for m in report.exceptions))

    def test_low_confidence_goes_to_exceptions(self):
        sample = load_spec(json.loads(read_fixture("sample-spec.json")))
        report = infer_mappings(self.doc, sample)
        self.assertTrue(any(m.confidence < 0.6 for m in report.mappings + report.exceptions))

    def test_freeform_spec(self):
        doc = parse_markdown("随便写一段\n\n再来一段")
        report = infer_mappings(doc, freeform_spec())
        self.assertEqual(len(report.mappings), 1)
        self.assertIn("随便写一段", report.mappings[0].source_text)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DraftStore(self.tmp.name)
        self.session = ImportSession(store=self.store)
        self.text = read_fixture("brief.md")
        self.spec = load_spec(json.loads(read_fixture("brief-spec.json")))

    def tearDown(self):
        self.tmp.cleanup()

    def _start(self, text=None, spec=None):
        self.session.start(Source.from_text("file", "brief.md", text or self.text),
                           spec or self.spec)
        self.session.preview()
        self.session.infer()
        return self.session

    def test_reset_current_clears_and_can_undo(self):
        s = self._start()
        self.assertEqual(s.stage, Stage.MAPPING)
        s.reset("current")
        self.assertEqual(s.stage, Stage.EMPTY)
        self.assertIsNone(s.report)
        self.assertIsNone(s.source)
        # no auto restore
        self.assertEqual(self.store.list(), [])
        s.undo()
        self.assertEqual(s.stage, Stage.MAPPING)
        self.assertIsNotNone(s.report)

    def test_save_draft_overwrites_same_source(self):
        s = self._start()
        s.accept_all()
        d1 = s.save_draft()
        d2 = s.save_draft()
        self.assertEqual(d1, d2)
        self.assertEqual(len(self.store.list()), 1)

    def test_different_source_creates_second_draft(self):
        s = self._start()
        s.save_draft()
        s2 = ImportSession(store=self.store)
        s2.start(Source.from_text("file", "other.md", "另一份内容\n\n第二段"))
        s2.preview(); s2.infer(); s2.save_draft()
        self.assertEqual(len(self.store.list()), 2)

    def test_reset_all_deletes_draft(self):
        s = self._start()
        s.save_draft()
        did = s.draft_id
        self.assertTrue(self.store.exists(did))
        s.reset("all")
        self.assertFalse(self.store.exists(did))
        self.assertEqual(self.store.list(), [])

    def test_toggle_accept_and_project(self):
        s = self._start()
        first = s.report.mappings[0]
        before = first.accepted
        s.toggle(0)
        self.assertNotEqual(first.accepted, before)
        s.accept_all()
        project = s.to_project()
        self.assertEqual(project["schema"], "nf-project/1")
        self.assertTrue(project["slots"])

    def test_empty_source_rejected(self):
        with self.assertRaises(ValueError):
            self.session.start(Source.from_text("file", "x.md", "  "))


if __name__ == "__main__":
    unittest.main()

