"""xmind / posm / posf / UOF 标识写入的回归测试（writers_zipformats）。

作者：impl（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_zipformats -v

读取面已由 Lead 接入 metadata.py；本测试直接做「写入 → metadata 提取」往返，
并校验：其它 entry 字节/顺序不变、幂等（二次写逐字节相同）、固定 date_time、
原子写无残留、坏 zip/坏 JSON/缺必要件报 ValueError。
"""

import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

sys_path_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.join(sys_path_root, "desktop", "src") not in __import__("sys").path:
    __import__("sys").path.insert(
        0, os.path.join(sys_path_root, "desktop", "src"))

from xml.etree import ElementTree as ET

from core.labeling import metadata
from core.labeling import writers_zipformats as w

UOF_NS = "http://schemas.uof.org/cn/2009/meta"
AIGC_JSON = json.dumps(
    {"AIGC": {"Label": "1",
              "ContentProducer": "001091350100M000100Y4300000",
              "ProduceID": "pid20250101v123456"}}, ensure_ascii=False)
AIGC_OBJ = json.loads(AIGC_JSON)

#: 四种容器的最小夹具：目标 entry + 一个「其它 entry」。
FIXTURES = {
    "xmind": (("content.json", b'{"sheets":[]}'),
              ("metadata.json", b'{"creator":"xmind-app"}')),
    "posm": (("content.xml", b"<doc/>"),
             ("meta.json", b'{"version":1}')),
    "posf": (("pages/page_1.xml", b"<page/>"),
             ("meta.json", b'{"version":1}')),
    "uof": (("document.xml", b"<doc/>"),
            ("_meta/meta.xml", (
                b'<?xml version="1.0" encoding="UTF-8"?>\n'
                b'<meta:Meta xmlns:meta="' + UOF_NS.encode() + b'" '
                b'xmlns:uof="http://schemas.uof.org/cn/2009/uof">'
                b'<uof:DocInfo>keep</uof:DocInfo></meta:Meta>'))),
}
#: 目标 entry（用于「其它 entry 不变」的判定）。
TARGET = {
    "xmind": "metadata.json",
    "posm": "meta.json",
    "posf": "meta.json",
    "uof": "_meta/meta.xml",
}
REQUIRED_MISSING = {
    "xmind": ("content.json",),
    "posm": ("content.xml",),
    "posf": ("pages/page_1.xml",),
    "uof": ("document.xml",),
}
WRITERS = {
    "xmind": w.inject_xmind,
    "posm": w.inject_posm,
    "posf": w.inject_posf,
    "uof": w.inject_uof,
}


def _make(path, entries):
    with zipfile.ZipFile(path, "w") as zf:
        for name, blob in entries:
            zf.writestr(name, blob)


def _names(path):
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def _data(path, name):
    with zipfile.ZipFile(path) as zf:
        return zf.read(name)


class ZipFormatsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name):
        return str(self.dir / name)

    def _fixture(self, kind):
        path = self.p("a." + kind)
        _make(path, FIXTURES[kind])
        return path

    def _zip_time(self, path):
        with zipfile.ZipFile(path) as zf:
            return {i.date_time for i in zf.infolist()}

    # ------------------------------------------------------- 往返 + 结构
    def test_json_formats_roundtrip(self):
        for kind in ("xmind", "posm", "posf"):
            path = self._fixture(kind)
            WRITERS[kind](path, AIGC_JSON)
            cands = metadata.extract_json_candidates(path)
            hits = [c for c in cands if c["key"] == "AIGC"]
            self.assertEqual(len(hits), 1, (kind, cands))
            self.assertEqual(hits[0]["raw"], AIGC_JSON)
            self.assertEqual(hits[0]["obj"], AIGC_OBJ)
            self.assertEqual(hits[0]["container"], kind + ".AIGC")

    def test_json_formats_preserve_other_keys(self):
        for kind in ("xmind", "posm", "posf"):
            path = self._fixture(kind)
            WRITERS[kind](path, AIGC_JSON)
            obj = json.loads(_data(path, TARGET[kind]))
            self.assertEqual(obj["AIGC"], AIGC_JSON)
            other = "creator" if kind == "xmind" else "version"
            self.assertEqual(obj[other], "xmind-app" if kind == "xmind" else 1)

    def test_uof_roundtrip_and_preserves_elements(self):
        path = self._fixture("uof")
        w.inject_uof(path, AIGC_JSON)
        raw = _data(path, "_meta/meta.xml")
        root = ET.fromstring(raw)
        self.assertEqual(root.tag, "{%s}Meta" % UOF_NS)
        texts = [(e.text or "").strip() for e in root.iter()
                 if e.tag.split("}")[-1] == "AIGC"]
        self.assertEqual(texts, [AIGC_JSON])
        # 其它元素与命名空间前缀都保留
        self.assertIn(b"xmlns:uof", raw)
        self.assertIn(b"uof:DocInfo", raw)
        cands = metadata.extract_json_candidates(path)
        hits = [c for c in cands if c["key"] == "AIGC"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["raw"], AIGC_JSON)
        self.assertEqual(hits[0]["obj"], AIGC_OBJ)

    def test_uof_replaces_existing_aigc(self):
        path = self.p("old.uof")
        meta_xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<meta:Meta xmlns:meta="%s">'
                    '<meta:AIGC>old</meta:AIGC></meta:Meta>'
                    % UOF_NS).encode()
        _make(path, [("document.xml", b"<doc/>"),
                     ("_meta/meta.xml", meta_xml)])
        w.inject_uof(path, AIGC_JSON)
        raw = _data(path, "_meta/meta.xml")
        root = ET.fromstring(raw)
        elems = [e for e in root.iter() if e.tag.split("}")[-1] == "AIGC"]
        self.assertEqual(len(elems), 1)          # 旧 AIGC 已替换，不重复
        self.assertEqual((elems[0].text or "").strip(), AIGC_JSON)

    # ------------------------------------------------------- 其它 entry
    def test_other_entries_bytes_and_order(self):
        for kind, writer in WRITERS.items():
            path = self._fixture(kind)
            before = _names(path)
            before_other = {n: _data(path, n) for n in before
                            if n != TARGET[kind]}
            writer(path, AIGC_JSON)
            after = _names(path)
            self.assertEqual(after, before, kind)      # 顺序与名字都不变
            for name, blob in before_other.items():
                self.assertEqual(_data(path, name), blob, (kind, name))

    def test_target_entry_created_when_missing(self):
        path = self.p("new.xmind")
        _make(path, [("content.json", b'{"sheets":[]}')])
        w.inject_xmind(path, AIGC_JSON)
        self.assertEqual(_names(path),
                         ["content.json", "metadata.json"])
        obj = json.loads(_data(path, "metadata.json"))
        self.assertEqual(obj, {"AIGC": AIGC_JSON})
        uof = self.p("new.uof")
        _make(uof, [("document.xml", b"<doc/>")])
        w.inject_uof(uof, AIGC_JSON)
        raw = _data(uof, "_meta/meta.xml")
        root = ET.fromstring(raw)
        self.assertEqual(root.tag, "{%s}Meta" % UOF_NS)

    # ------------------------------------------------------- 幂等 / 确定性
    def test_idempotent_second_write_bytes_equal(self):
        for kind, writer in WRITERS.items():
            path = self._fixture(kind)
            writer(path, AIGC_JSON)
            once = Path(path).read_bytes()
            writer(path, AIGC_JSON)
            self.assertEqual(once, Path(path).read_bytes(), kind)

    def test_fixed_zip_date_time(self):
        for kind, writer in WRITERS.items():
            path = self._fixture(kind)
            writer(path, AIGC_JSON)
            self.assertEqual(self._zip_time(path),
                             {(2026, 1, 1, 0, 0, 0)}, kind)

    def test_different_json_replaces_single(self):
        other = '{"AIGC":{"Label":2,"ProduceID":"P-2"}}'
        for kind, writer in WRITERS.items():
            path = self._fixture(kind)
            writer(path, AIGC_JSON)
            writer(path, other)
            cands = [c for c in metadata.extract_json_candidates(path)
                     if c["key"] == "AIGC"]
            self.assertEqual(len(cands), 1, kind)
            self.assertEqual(cands[0]["raw"], other, kind)

    # ------------------------------------------------------- 原子写 / 权限
    def test_atomic_write_no_residue(self):
        path = self._fixture("xmind")
        before = sorted(p.name for p in self.dir.iterdir())
        w.inject_xmind(path, AIGC_JSON)
        after = sorted(p.name for p in self.dir.iterdir())
        self.assertEqual(before, after)
        self.assertFalse(any(n.endswith(".tmp") for n in after))
        # 坏 JSON 在写盘前就拒绝，不应留临时件
        with self.assertRaises(ValueError):
            w.inject_xmind(path, "{bad json}")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), after)

    def test_permissions_preserved(self):
        path = self._fixture("posm")
        os.chmod(path, 0o640)
        w.inject_posm(path, AIGC_JSON)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o640)

    # ------------------------------------------------------- 失败面
    def test_bad_zip_raises(self):
        for kind, writer in WRITERS.items():
            bad = self.p("bad." + kind)
            Path(bad).write_bytes(b"not a zip")
            with self.assertRaises(ValueError):
                writer(bad, AIGC_JSON)
            trunc = self.p("trunc." + kind)
            Path(trunc).write_bytes(b"PK\x03\x04broken")
            with self.assertRaises(ValueError):
                writer(trunc, AIGC_JSON)

    def test_bad_json_raises(self):
        for kind, writer in WRITERS.items():
            path = self._fixture(kind)
            for bad in ("{bad json}", "", "  "):
                with self.assertRaises(ValueError):
                    writer(path, bad)

    def test_missing_required_entry_raises(self):
        for kind, writer in WRITERS.items():
            entries = [e for e in FIXTURES[kind]
                       if e[0] not in REQUIRED_MISSING[kind]]
            path = self.p("miss." + kind)
            _make(path, entries)
            with self.assertRaises(ValueError):
                writer(path, AIGC_JSON)

    def test_target_json_not_object_raises(self):
        path = self.p("arr.posm")
        _make(path, [("content.xml", b"<doc/>"),
                     ("meta.json", b"[1,2,3]")])
        with self.assertRaises(ValueError):
            w.inject_posm(path, AIGC_JSON)

    def test_target_json_not_utf8_raises(self):
        path = self.p("bin.posm")
        _make(path, [("content.xml", b"<doc/>"),
                     ("meta.json", b"\xff\xfe\x00bad")])
        with self.assertRaises(ValueError):
            w.inject_posm(path, AIGC_JSON)

    def test_uof_bad_meta_xml_raises(self):
        path = self.p("badmeta.uof")
        _make(path, [("document.xml", b"<doc/>"),
                     ("_meta/meta.xml", b"<not-xml")])
        with self.assertRaises(ValueError):
            w.inject_uof(path, AIGC_JSON)
        wrong_root = self.p("wrongroot.uof")
        _make(wrong_root, [("document.xml", b"<doc/>"),
                           ("_meta/meta.xml", b"<Other/>")])
        with self.assertRaises(ValueError):
            w.inject_uof(wrong_root, AIGC_JSON)

    def test_missing_file_raises(self):
        for kind, writer in WRITERS.items():
            with self.assertRaises(ValueError):
                writer(self.p("nope." + kind), AIGC_JSON)


if __name__ == "__main__":
    unittest.main()
