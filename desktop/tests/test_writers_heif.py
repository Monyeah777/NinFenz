"""HEIF 标识写入的回归测试（writers_heif）。

作者：impl（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_heif -v

覆盖：iinf/iloc fullbox v0 与 v1；infe v2 结构；iloc 新 item；meta 变长后
**原主图 item extent 偏移 +delta** 且仍指向同一份图像字节；原 mdat 不变；
幂等（同 json 不新增 item）；替换不同 json；坏文件；原子写。
"""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

sys_path_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.join(sys_path_root, "desktop", "src") not in __import__("sys").path:
    __import__("sys").path.insert(
        0, os.path.join(sys_path_root, "desktop", "src"))


from core.labeling import metadata
from core.labeling import writers_heif as w

J = json.dumps({"AIGC": {"Label": "1",
                         "ContentProducer": "001091350100M000100Y4300000",
                         "ProduceID": "pid20250101v123456"}},
               ensure_ascii=False)
OBJ = json.loads(J)
IMG = b"\x89HEIC_PRIMARY_IMAGE_PAYLOAD_0123456789"


# ---------------------------------------------------------------- 夹具
def _box(btype, payload):
    return (len(payload) + 8).to_bytes(4, "big") + btype + payload


def _fullbox(btype, version, flags, payload):
    return _box(btype, bytes([version]) + flags.to_bytes(3, "big") + payload)


def _infe_v2(item_id, item_type, name=None, content_type=None):
    body = (bytes([2, 0, 0, 0]) + item_id.to_bytes(2, "big")
            + b"\x00\x00" + item_type)
    if name is not None:
        body += name.encode("utf-8") + b"\x00" + content_type + b"\x00"
    return _box(b"infe", body)


def make_heif(path, iinf_ver=0, iloc_ver=0, extra_meta=(), extra_top=(),
              item_ids=(1,)):
    """最小 HEIF：ftyp + meta(hdlr/pitm/iinf/iloc[+extra]) + mdat 主图。

    item_ids：主图 item 的 id 列表（第一个是 pitm 指向的主图）；每个 item
    的 extent 都指向 mdat 里的同一段图像（简化夹具）。
    """
    def build(offset):
        ftyp = _box(b"ftyp", b"heic" + b"\x00\x00\x00\x00" + b"mif1heic")
        hdlr = _box(b"hdlr", bytes([0, 0, 0, 0]) + b"\x00" * 4
                    + b"pict" + b"\x00" * 12 + b"\x00")
        pitm = _fullbox(b"pitm", 0, 0,
                        item_ids[0].to_bytes(2, "big"))
        infes = b"".join(_infe_v2(i, b"hvc1") for i in item_ids)
        iinf = _fullbox(
            b"iinf", iinf_ver, 0,
            len(item_ids).to_bytes(2 if iinf_ver == 0 else 4, "big")
            + infes)
        items = b""
        for item_id in item_ids:
            item = item_id.to_bytes(2, "big")
            if iloc_ver in (1, 2):
                item += (0).to_bytes(2, "big")          # construction_method
            item += (0).to_bytes(2, "big")              # data_reference_index
            item += (1).to_bytes(2, "big")              # extent_count
            item += offset.to_bytes(4, "big")           # extent_offset
            item += len(IMG).to_bytes(4, "big")         # extent_length
            items += item
        iloc = _fullbox(
            b"iloc", iloc_ver, 0,
            bytes([0x44, 0x00])
            + len(item_ids).to_bytes(2 if iloc_ver < 2 else 4, "big")
            + items)
        extra = b"".join(_box(t, p) for t, p in extra_meta)
        children = hdlr + pitm + extra + iinf + iloc
        meta = _fullbox(b"meta", 0, 0, children)
        mdat = _box(b"mdat", IMG)
        return ftyp, meta, mdat

    ftyp, meta, mdat = build(0)
    mdat_off = len(ftyp) + len(meta) + 8
    ftyp, meta, mdat = build(mdat_off)
    data = bytearray(ftyp)
    for name, payload in extra_top:
        data += _box(name, payload)
    data += meta + mdat
    Path(path).write_bytes(bytes(data))
    return {"img": IMG, "mdat_payload_off": mdat_off}


# ---------------------------------------------------------------- 解析辅助
def _parse(data):
    """自建 BMFF 解析：顶层盒、meta 子盒、iinf、iloc、pitm。"""
    def boxes(start, end):
        pos = start
        out = []
        while pos + 8 <= end:
            size = int.from_bytes(data[pos:pos + 4], "big")
            btype = data[pos + 4:pos + 8]
            hdr = 8
            if size == 1:
                size = int.from_bytes(data[pos + 8:pos + 16], "big")
                hdr = 16
            elif size == 0:
                size = end - pos
            out.append((btype, pos, pos + hdr, pos + size))
            pos += size
        return out

    top = boxes(0, len(data))
    meta = next(b for b in top if b[0] == b"meta")
    children = boxes(meta[2] + 4, meta[3])
    iinf_box = next(b for b in children if b[0] == b"iinf")
    iloc_box = next(b for b in children if b[0] == b"iloc")
    pitm_box = next(b for b in children if b[0] == b"pitm")

    infes = []
    p = iinf_box[2]
    iinf_ver = data[p]
    p += 4
    if iinf_ver == 0:
        cnt = int.from_bytes(data[p:p + 2], "big")
        p += 2
    else:
        cnt = int.from_bytes(data[p:p + 4], "big")
        p += 4
    for btype, bs, body, be in boxes(p, iinf_box[3]):
        if btype != b"infe":
            continue
        ver = data[body]
        item_id = int.from_bytes(data[body + 4:body + 6], "big")
        if ver >= 2:
            itype = data[body + 8:body + 12]
            pos = body + 12
            name = ctype = None
            if itype == b"mime":
                stop = data.find(b"\x00", pos, be)
                name = data[pos:stop].decode()
                pos = stop + 1
                stop = data.find(b"\x00", pos, be)
                ctype = data[pos:stop].decode()
            infes.append({"id": item_id, "version": ver, "type": itype,
                          "name": name, "content_type": ctype})
        else:
            stop = data.find(b"\x00", body + 8, be)
            infes.append({"id": item_id, "version": ver, "type": None,
                          "name": data[body + 8:stop].decode()})

    p = iloc_box[2]
    iloc_ver = data[p]
    p += 4
    b1 = data[p]
    off_size, len_size = b1 >> 4, b1 & 0x0F
    b2 = data[p + 1]
    base_size = b2 >> 4
    idx_size = (b2 & 0x0F) if iloc_ver in (1, 2) else 0
    p += 2
    id_size = 2 if iloc_ver < 2 else 4
    cnt = int.from_bytes(data[p:p + (2 if iloc_ver < 2 else 4)], "big")
    p += 2 if iloc_ver < 2 else 4
    items = []
    for _ in range(cnt):
        item_id = int.from_bytes(data[p:p + id_size], "big")
        p += id_size
        cm = 0
        if iloc_ver in (1, 2):
            cm = int.from_bytes(data[p:p + 2], "big") & 0x0F
            p += 2
        data_ref = int.from_bytes(data[p:p + 2], "big")
        p += 2
        base = int.from_bytes(data[p:p + base_size], "big") if base_size else 0
        p += base_size
        ext_cnt = int.from_bytes(data[p:p + 2], "big")
        p += 2
        exts = []
        for _ in range(ext_cnt):
            if idx_size:
                p += idx_size
            off = int.from_bytes(data[p:p + off_size], "big") if off_size else 0
            p += off_size
            ln = int.from_bytes(data[p:p + len_size], "big") if len_size else 0
            p += len_size
            exts.append((base + off, ln))
        items.append({"id": item_id, "cm": cm, "data_ref": data_ref,
                      "base": base, "extents": exts})
    pitm = int.from_bytes(data[pitm_box[2] + 4:pitm_box[2] + 6], "big")
    return {"top": top, "meta": meta, "children": children,
            "iinf_ver": iinf_ver, "infes": infes,
            "iloc_ver": iloc_ver, "items": items, "pitm": pitm}


def _entry_data(data, item):
    """按 iloc item 的 (offset, length) 取字节。"""
    off, ln = item["extents"][0]
    return data[off:off + ln]


class HeifWriterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name):
        return str(self.dir / name)

    # ------------------------------------------------------- 往返
    def test_metadata_roundtrip_v0(self):
        path = self.p("a.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        w.inject_heif(path, J)
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "AIGC"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["container"], "heif.item")
        self.assertEqual(cands[0]["raw"], J)
        self.assertEqual(cands[0]["obj"], OBJ)

    def test_metadata_roundtrip_v1(self):
        path = self.p("b.heic")
        make_heif(path, iinf_ver=1, iloc_ver=1)
        w.inject_heif(path, J)
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "AIGC"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["raw"], J)

    # ------------------------------------------------------- 结构
    def test_iinf_gets_mime_infe(self):
        path = self.p("a.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        before = _parse(Path(path).read_bytes())
        w.inject_heif(path, J)
        after = _parse(Path(path).read_bytes())
        self.assertEqual(len(after["infes"]), len(before["infes"]) + 1)
        new = [ie for ie in after["infes"]
               if (ie["name"] or "").upper() == "AIGC"]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["version"], 2)
        self.assertEqual(new[0]["type"], b"mime")
        self.assertEqual(new[0]["content_type"], "application/json")
        self.assertGreater(new[0]["id"], before["infes"][0]["id"])

    def test_iloc_gets_item_pointing_to_json(self):
        path = self.p("a.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        w.inject_heif(path, J)
        data = Path(path).read_bytes()
        parsed = _parse(data)
        aigc = next(ie for ie in parsed["infes"]
                    if (ie["name"] or "").upper() == "AIGC")
        item = next(it for it in parsed["items"] if it["id"] == aigc["id"])
        self.assertEqual(item["cm"], 0)          # file offset
        self.assertEqual(len(item["extents"]), 1)
        off, ln = item["extents"][0]
        self.assertEqual(ln, len(J.encode("utf-8")))
        self.assertEqual(data[off:off + ln], J.encode("utf-8"))

    def test_meta_size_and_delta(self):
        path = self.p("a.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        before = _parse(Path(path).read_bytes())
        old_meta_size = before["meta"][3] - before["meta"][1]
        w.inject_heif(path, J)
        after = _parse(Path(path).read_bytes())
        new_meta_size = after["meta"][3] - after["meta"][1]
        delta = new_meta_size - old_meta_size
        self.assertGreater(delta, 0)
        # 主图 extent 的绝对偏移正好 +delta
        old_item = before["items"][0]
        new_item = next(it for it in after["items"]
                        if it["id"] == old_item["id"])
        self.assertEqual(new_item["extents"][0][0],
                         old_item["extents"][0][0] + delta)

    def test_primary_image_extent_data_unchanged(self):
        path = self.p("a.heic")
        info = make_heif(path, iinf_ver=0, iloc_ver=0)
        before = _parse(Path(path).read_bytes())
        old_primary = next(it for it in before["items"]
                           if it["id"] == before["pitm"])
        w.inject_heif(path, J)
        data = Path(path).read_bytes()
        after = _parse(data)
        primary = next(it for it in after["items"]
                       if it["id"] == after["pitm"])
        # 偏移变了，但读到的仍是同一份原始图像字节
        self.assertEqual(_entry_data(data, primary), IMG)
        self.assertNotEqual(primary["extents"][0][0],
                            old_primary["extents"][0][0])
        self.assertEqual(info["img"], IMG)

    def test_original_mdat_bytes_unchanged(self):
        path = self.p("a.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        before = Path(path).read_bytes()
        old_mdat = b"\x00\x00\x00\x00mdat" + IMG
        idx = before.find(b"mdat") - 4
        old_mdat = before[idx:idx + 8 + len(IMG)]
        w.inject_heif(path, J)
        after = Path(path).read_bytes()
        self.assertIn(old_mdat, after)          # 原 mdat 原字节仍在
        self.assertGreater(len(after), len(before))

    def test_meta_children_order_and_unknown_preserved(self):
        free = (b"free", b"unknown-meta-child")
        path = self.p("c.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0, extra_meta=[free])
        before_data = Path(path).read_bytes()
        before = _parse(before_data)
        w.inject_heif(path, J)
        after_data = Path(path).read_bytes()
        after = _parse(after_data)
        self.assertEqual([c[0] for c in before["children"]],
                         [c[0] for c in after["children"]])
        # 未知子盒与 hdlr 的原字节保持不变
        for btype in (b"hdlr", b"free", b"pitm"):
            b_before = [b for b in before["children"]
                        if b[0] == btype][0]
            b_after = [b for b in after["children"] if b[0] == btype][0]
            self.assertEqual(before_data[b_before[1]:b_before[3]],
                             after_data[b_after[1]:b_after[3]], btype)

    def test_id_generation_is_max_plus_one(self):
        path = self.p("d.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0, item_ids=(1, 7))
        w.inject_heif(path, J)
        parsed = _parse(Path(path).read_bytes())
        aigc = next(ie for ie in parsed["infes"]
                    if (ie["name"] or "").upper() == "AIGC")
        self.assertEqual(aigc["id"], 8)

    # ------------------------------------------------------- 幂等 / 替换
    def test_idempotent_same_json(self):
        path = self.p("a.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        w.inject_heif(path, J)
        once = Path(path).read_bytes()
        w.inject_heif(path, J)
        self.assertEqual(once, Path(path).read_bytes())
        parsed = _parse(Path(path).read_bytes())
        aigc = [ie for ie in parsed["infes"]
                if (ie["name"] or "").upper() == "AIGC"]
        self.assertEqual(len(aigc), 1)

    def test_replace_with_different_json(self):
        path = self.p("a.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        w.inject_heif(path, J)
        other = '{"AIGC":{"Label":2,"ProduceID":"P-2"}}'
        w.inject_heif(path, other)
        data = Path(path).read_bytes()
        parsed = _parse(data)
        aigc = [ie for ie in parsed["infes"]
                if (ie["name"] or "").upper() == "AIGC"]
        self.assertEqual(len(aigc), 1)           # 不重复增
        item = next(it for it in parsed["items"] if it["id"] == aigc[0]["id"])
        self.assertEqual(_entry_data(data, item), other.encode())
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "AIGC"]
        self.assertEqual(cands[0]["raw"], other)

    # ------------------------------------------------------- 失败面 / 公共
    def test_bad_inputs(self):
        cases = {
            "not.heic": b"not a heif file",
            "nometa.heic": (b"\x00\x00\x00\x10ftypheic\x00\x00\x00\x00"
                            b"mif1heic"),
            "nomdat.heic": b"\x00\x00\x00\x10ftypheic\x00\x00\x00\x00"
                           b"mif1heic\x00\x00\x00\x0cmeta\x00\x00\x00\x00",
            "trunc.heic": (b"\x00\x00\x00\x20ftypheic\x00\x00\x00\x00"
                           b"mif1heic"),
        }
        for name, blob in cases.items():
            path = self.p(name)
            Path(path).write_bytes(blob)
            with self.assertRaises(ValueError):
                w.inject_heif(path, J)
        path = self.p("ok.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        with self.assertRaises(ValueError):
            w.inject_heif(path, "{bad json}")

    def test_atomic_write_no_residue_and_permissions(self):
        path = self.p("a.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        os.chmod(path, 0o640)
        before = sorted(p.name for p in self.dir.iterdir())
        w.inject_heif(path, J)
        after = sorted(p.name for p in self.dir.iterdir())
        self.assertEqual(before, after)
        self.assertFalse(any(n.endswith(".tmp") for n in after))
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o640)

    def test_large_json_roundtrip(self):
        path = self.p("big.heic")
        make_heif(path, iinf_ver=0, iloc_ver=0)
        big = json.dumps({"AIGC": {"Label": 1, "Pad": "x" * 4000}},
                         ensure_ascii=False)
        w.inject_heif(path, big)
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "AIGC"]
        self.assertEqual(cands[0]["raw"], big)


if __name__ == "__main__":
    unittest.main()
