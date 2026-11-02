"""writers_ofd.inject_ofd 的单元测试（unittest）。

作者：gate（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_ofd -v

覆盖：`CustomDatas/AIGC.xml` 往返（Content = XML 转义 JSON）、无
`<CustomDatas>` 节时 OFD.xml 字节不变、有节时登记引用、幂等、换 JSON
原位替换、自闭合节展开、命名空间前缀、已有登记不重复、坏 zip / 缺 OFD.xml
/ 坏 JSON 的 ValueError、XML 转义、原子写与权限位。
"""

import json
import os
import stat
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import sys

sys_path_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.join(sys_path_root, "desktop", "src") not in sys.path:
    sys.path.insert(0, os.path.join(sys_path_root, "desktop", "src"))

from core.labeling import writers_ofd as wo

NS = "http://www.ofdspec.org/2016"
PAYLOAD = {"AIGC": {"Label": 1, "Producer": "测试 & <示例>", "n": 7}}
JSON = json.dumps(PAYLOAD, ensure_ascii=False)

FIXED_TIME = (2026, 1, 2, 3, 4, 6)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _write_zip(path: str, entries) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)


def _ofd_xml(with_section: bool = False, self_closing: bool = False,
             prefix: str = "", pre_registered: bool = False) -> str:
    p = prefix
    ns_decl = (' xmlns:%s="%s"' % (p[:-1], NS)) if p else (' xmlns="%s"' % NS)
    if self_closing:
        section = "<%sCustomDatas/>" % p
    elif with_section:
        inner = ""
        if pre_registered:
            inner = ('<%sCustomData Name="AIGC" '
                     'Location="CustomDatas/AIGC.xml"/>' % p)
        section = "<%sCustomDatas>%s</%sCustomDatas>" % (p, inner, p)
    else:
        section = ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<{p}OFD{x} Version=\"1.0\" DocType=\"OFD\">"
        "<{p}DocBody><{p}DocInfo><{p}DocID>t1</{p}DocID></{p}DocInfo>"
        "<{p}DocRoot>Doc_0/Document.xml</{p}DocRoot></{p}DocBody>"
        "{s}</{p}OFD>"
    ).format(p=p, x=ns_decl, s=section)


def _make_ofd(path: str, **kwargs) -> None:
    """最小 OFD：OFD.xml + Doc_0/Document.xml + Page_0/Content.xml。"""
    entries = [
        ("OFD.xml", _ofd_xml(**kwargs).encode("utf-8")),
        ("Doc_0/Document.xml",
         ('<Document xmlns="%s"><Pages><Page ID="1"/></Pages>'
          "</Document>" % NS).encode("utf-8")),
        ("Doc_0/Pages/Page_0/Content.xml",
         ('<Page xmlns="%s"><Content/>' "</Page>" % NS).encode("utf-8")),
    ]
    _write_zip(path, entries)


def _names(path: str):
    with zipfile.ZipFile(path) as zf:
        return [i.filename for i in zf.infolist()]


def _read(path: str, name: str) -> bytes:
    with zipfile.ZipFile(path) as zf:
        return zf.read(name)


def _custom_registrations(ofd_xml: bytes):
    """OFD.xml 里 CustomDatas/CustomData 的 (Name, Location) 列表。"""
    root = ET.fromstring(ofd_xml)
    out = []
    for node in root.iter():
        if _local(node.tag) != "CustomDatas":
            continue
        for child in node:
            if _local(child.tag) == "CustomData":
                out.append((child.get("Name"), child.get("Location")))
    return out


def _content_of(path: str) -> str:
    root = ET.fromstring(_read(path, wo.CUSTOM_ENTRY))
    assert _local(root.tag) == "CustomData"
    assert root.get("Name") == "AIGC"
    for child in root:
        if _local(child.tag) == "Content":
            return child.text or ""
    raise AssertionError("缺 <Content>")


class OfdWriterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name: str) -> str:
        return str(self.dir / name)

    # ------------------------------------------------------------ 往返
    def test_roundtrip_custom_data(self):
        path = self.p("a.ofd")
        _make_ofd(path)
        wo.inject_ofd(path, JSON)
        self.assertIn(wo.CUSTOM_ENTRY, _names(path))
        content = _content_of(path)
        self.assertEqual(JSON, content)
        self.assertEqual(PAYLOAD, json.loads(content))

    def test_ofd_xml_untouched_without_section(self):
        path = self.p("b.ofd")
        _make_ofd(path)
        before_ofd = _read(path, "OFD.xml")
        before_doc = _read(path, "Doc_0/Document.xml")
        before_content = _read(path, "Doc_0/Pages/Page_0/Content.xml")
        wo.inject_ofd(path, JSON)
        self.assertEqual(before_ofd, _read(path, "OFD.xml"))
        self.assertEqual(before_doc, _read(path, "Doc_0/Document.xml"))
        self.assertEqual(before_content,
                         _read(path, "Doc_0/Pages/Page_0/Content.xml"))

    def test_other_entries_and_order_preserved(self):
        path = self.p("c.ofd")
        _make_ofd(path)
        before = _names(path)
        wo.inject_ofd(path, JSON)
        after = _names(path)
        self.assertEqual(before + [wo.CUSTOM_ENTRY], after)
        self.assertEqual("Doc_0/Document.xml", after[1])
        self.assertEqual("Doc_0/Pages/Page_0/Content.xml", after[2])

    # ------------------------------------------------------------ 登记
    def test_registration_added_when_section_present(self):
        path = self.p("d.ofd")
        _make_ofd(path, with_section=True)
        wo.inject_ofd(path, JSON)
        regs = _custom_registrations(_read(path, "OFD.xml"))
        self.assertEqual([("AIGC", "CustomDatas/AIGC.xml")], regs)

    def test_self_closing_section_expanded(self):
        path = self.p("e.ofd")
        _make_ofd(path, self_closing=True)
        wo.inject_ofd(path, JSON)
        text = _read(path, "OFD.xml").decode("utf-8")
        self.assertNotIn("<CustomDatas/>", text)
        regs = _custom_registrations(_read(path, "OFD.xml"))
        self.assertEqual([("AIGC", "CustomDatas/AIGC.xml")], regs)

    def test_prefixed_namespace_registration(self):
        path = self.p("f.ofd")
        _make_ofd(path, with_section=True, prefix="ofd:")
        wo.inject_ofd(path, JSON)
        text = _read(path, "OFD.xml").decode("utf-8")
        self.assertIn('<ofd:CustomData Name="AIGC"', text)
        self.assertIn("</ofd:CustomDatas>", text)
        regs = _custom_registrations(_read(path, "OFD.xml"))
        self.assertEqual([("AIGC", "CustomDatas/AIGC.xml")], regs)

    def test_existing_registration_not_duplicated(self):
        path = self.p("g.ofd")
        _make_ofd(path, with_section=True, pre_registered=True)
        before = _read(path, "OFD.xml")
        wo.inject_ofd(path, JSON)
        self.assertEqual(before, _read(path, "OFD.xml"))
        regs = _custom_registrations(_read(path, "OFD.xml"))
        self.assertEqual(1, len(regs))

    # ------------------------------------------------------------ 幂等/替换
    def test_idempotent_zip_bytes(self):
        path = self.p("h.ofd")
        _make_ofd(path, with_section=True)
        wo.inject_ofd(path, JSON)
        first = Path(path).read_bytes()
        wo.inject_ofd(path, JSON)
        self.assertEqual(first, Path(path).read_bytes())

    def test_rewrite_updates_content_and_keeps_single_registration(self):
        path = self.p("i.ofd")
        _make_ofd(path, with_section=True)
        wo.inject_ofd(path, JSON)
        second = json.dumps({"AIGC": {"Label": 2}}, ensure_ascii=False)
        wo.inject_ofd(path, second)
        self.assertEqual(second, _content_of(path))
        self.assertEqual(1, len(_custom_registrations(
            _read(path, "OFD.xml"))))

    # ------------------------------------------------------------ 转义
    def test_xml_escaping_roundtrip(self):
        path = self.p("j.ofd")
        _make_ofd(path)
        payload = {"s": "<a> & \"q\" 'b'"}
        text = json.dumps(payload, ensure_ascii=False)
        wo.inject_ofd(path, text)
        raw = _read(path, wo.CUSTOM_ENTRY)
        self.assertIn(b"&lt;a&gt;", raw)
        self.assertIn(b"&amp;", raw)
        self.assertEqual(payload, json.loads(_content_of(path)))

    # ------------------------------------------------------------ 坏输入
    def test_bad_zip_raises_value_error(self):
        cases = {
            "empty": b"",
            "text": b"not a zip at all",
        }
        for name, data in cases.items():
            path = self.p(name + ".ofd")
            Path(path).write_bytes(data)
            with self.assertRaises(ValueError, msg=name):
                wo.inject_ofd(path, JSON)
        path = self.p("truncated.ofd")
        _make_ofd(path)
        data = Path(path).read_bytes()
        Path(path).write_bytes(data[:len(data) // 2])
        with self.assertRaises(ValueError):
            wo.inject_ofd(path, JSON)

    def test_missing_ofd_xml_raises_value_error(self):
        path = self.p("k.ofd")
        _write_zip(path, [("Doc_0/Document.xml", b"<Document/>")])
        with self.assertRaises(ValueError) as ctx:
            wo.inject_ofd(path, JSON)
        self.assertIn("OFD.xml", str(ctx.exception))

    def test_invalid_json_leaves_file_untouched(self):
        path = self.p("l.ofd")
        _make_ofd(path)
        before = Path(path).read_bytes()
        with self.assertRaises(ValueError):
            wo.inject_ofd(path, "{not json")
        self.assertEqual(before, Path(path).read_bytes())

    # ------------------------------------------------------------ 写盘
    def test_atomic_no_temp_file_and_mode_kept(self):
        path = self.p("m.ofd")
        _make_ofd(path)
        os.chmod(path, 0o640)
        wo.inject_ofd(path, JSON)
        leftovers = [n for n in os.listdir(self.dir)
                     if n.startswith(".nf-ofd-")]
        self.assertEqual([], leftovers)
        self.assertEqual(0o640, stat.S_IMODE(os.stat(path).st_mode))


if __name__ == "__main__":
    unittest.main()
