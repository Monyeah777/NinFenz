"""nf labeling（并入 NF 的 nf-labelcheck）快速核心回归。

作者：impl（DSH agent）· 2026-11-02
运行：cd <repo> && python3 -m unittest desktop.tests.test_labeling_core -v

覆盖：SM3 国标向量、SM2 GB/T 32918 向量、TBS 黄金切片、SecurityData 构建/验签、
X.509 链、可信时间戳往返、容器冒烟、五段判定冒烟（不跑容器全量矩阵）。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import checker, metadata, security_data as sd, sm, tsa, x509  # noqa: E402

RAW = json.dumps(
    {"AIGC": {"Label": "1",
              "ContentProducer": "001091350100M000100Y4300000",
              "ProduceID": "pid20250101v123456"}},
    ensure_ascii=False, indent=2)
META = {"Label": "1",
        "ContentProducer": "001091350100M000100Y4300000",
        "ProduceID": "pid20250101v123456"}

#: GB/T 32918.5—2017 附录 A.2（推荐曲线）向量
SM2_D = "3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8"
SM2_K = "59276E27D506861A16680F3AD9C02DCCEF3CC1FA3CDBE4CE6D54B80DEAC1BC21"
SM2_R = "f5a03b0648d2c4630eeac513e1bb81a15944da3827d5b74143ac7eaceee720b3"
SM2_S = ("b1b6aa29df212fd8763182bc0d421ca1bb9038fd1f7f42d4840b69c485bb"
         "c1aa")
SM2_PUB = ("09f9df311e5421a150dd7d161e4bc5c672179fad1833fc076bb08ff356f35020"
           "ccea490ce26775a52dc6ea718cc1aa600aed05fbf35e084a6632f6072da9ad13")


class SmTest(unittest.TestCase):
    def test_sm3_gb_vector_abc(self):
        self.assertEqual(
            sm.sm3_hex(b"abc"),
            "66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0")

    def test_sm3_gb_vector_512bit(self):
        self.assertEqual(
            sm.sm3_hex(b"abcd" * 16),
            "debe9ff92275b8a138604889c18e5a4d6fdb70e5387e5765293dcba39c0c5732")

    def test_sm3_block_boundaries(self):
        for n in (55, 56, 63, 64, 65):
            self.assertEqual(len(sm.sm3(b"a" * n)), 32)

    def test_sm2_public_from_private_matches_vector(self):
        self.assertEqual(sm.sm2_public_from_private(SM2_D), SM2_PUB)

    def test_sm2_golden_signature(self):
        # k_hex 只为标准向量复算；生产路径仍走随机 k
        sig = sm.sm2_sign(SM2_D, b"message digest", k_hex=SM2_K)
        self.assertEqual(sig, SM2_R + SM2_S)

    def test_sm2_verify_golden(self):
        self.assertTrue(
            sm.sm2_verify(SM2_PUB, b"message digest", SM2_R + SM2_S))

    def test_sm2_verify_rejects_tampered_message(self):
        self.assertFalse(
            sm.sm2_verify(SM2_PUB, b"message digest!", SM2_R + SM2_S))


class TbsTest(unittest.TestCase):
    def test_golden_slice_producer(self):
        raw = ('{"AIGC":{"Label":"1",'
               '"ContentProducer":"001091350100M000100Y4300000",'
               '"ProduceID":"pid20250101v123456"}}')
        want = ('"Label":"1","ContentProducer":"001091350100M000100Y4300000",'
                '"ProduceID":"pid20250101v123456"')
        self.assertEqual(sd.tbs_slice(raw, 3), want.encode("utf-8"))

    def test_slice_propagator_six_fields(self):
        raw = json.dumps({"AIGC": {
            "Label": "1", "ContentProducer": "A" * 27, "ProduceID": "p1",
            "ReservedCode1": {"x": 1}, "ContentPropagator": "B" * 27,
            "PropagateID": "p2"}}, ensure_ascii=False, indent=2)
        got = sd.tbs_slice(raw, 6).decode("utf-8")
        self.assertTrue(got.startswith('"Label"'))
        self.assertTrue(got.endswith('"p2"'))
        self.assertIn('"ReservedCode1"', got)

    def test_slice_missing_label_raises(self):
        with self.assertRaises(ValueError):
            sd.tbs_slice('{"AIGC":{}}', 3)


class SecurityDataTest(unittest.TestCase):
    def setUp(self):
        self.keys = sm.sm2_keygen()
        self.content = b"content-bytes"
        self.bindings = sd.build_bindings(self.content, "DFT")
        self.box = sd.build_security_data(RAW, self.bindings,
                                          self.keys["private"])
        self.sd = self.box["SecurityData"]

    def test_structure_ok(self):
        self.assertEqual(sd.structure_issues(self.box), [])

    def test_binding_ok(self):
        ok, issues, got = sd.check_binding(self.sd, self.content)
        self.assertTrue(ok, issues)
        self.assertEqual(got, sm.sm3_hex(self.content))

    def test_signature_ok(self):
        ok, issues = sd.verify_signatures(self.sd, META, RAW,
                                          self.bindings, self.content)
        self.assertTrue(ok, issues)

    def test_signature_detects_meta_change(self):
        meta2 = dict(META, ProduceID="pid20250101v999999")
        raw2 = RAW.replace("pid20250101v123456", "pid20250101v999999")
        ok, _issues = sd.verify_signatures(self.sd, meta2, raw2,
                                           self.bindings, self.content)
        self.assertFalse(ok)

    def test_signature_detects_binding_change(self):
        box = json.loads(json.dumps(self.box))
        box["SecurityData"]["Bindings"][0]["Value"] = "0" * 64
        sd2 = box["SecurityData"]
        ok, _issues = sd.verify_signatures(sd2, META, RAW,
                                           sd2["Bindings"], self.content)
        self.assertFalse(ok)


class CertChainTest(unittest.TestCase):
    def test_self_signed_verifies(self):
        keys = sm.sm2_keygen()
        der_bytes = x509.make_cert("CA", "CA", keys["public"],
                                   keys["private"], is_ca=True)
        cert = x509.parse_cert(der_bytes)
        self.assertTrue(cert.is_ca)
        self.assertTrue(x509.verify_cert_signature(cert, cert.pub_hex))

    def test_ca_to_leaf_chain(self):
        ca_k = sm.sm2_keygen()
        leaf_k = sm.sm2_keygen()
        ca = x509.parse_cert(x509.make_cert(
            "NF CA", "NF CA", ca_k["public"], ca_k["private"],
            serial=1, is_ca=True))
        leaf = x509.parse_cert(x509.make_cert(
            "Signer", "NF CA", leaf_k["public"], ca_k["private"],
            serial=2))
        ok, issues, chain = x509.build_chain(leaf, [], [ca])
        self.assertTrue(ok, issues)
        self.assertEqual([c.subject_cn for c in chain], ["Signer", "NF CA"])

    def test_untrusted_root_fails(self):
        ca_k = sm.sm2_keygen()
        other_k = sm.sm2_keygen()
        leaf_k = sm.sm2_keygen()
        ca = x509.parse_cert(x509.make_cert(
            "NF CA", "NF CA", ca_k["public"], ca_k["private"], is_ca=True))
        other = x509.parse_cert(x509.make_cert(
            "Other CA", "Other CA", other_k["public"], other_k["private"],
            is_ca=True))
        leaf = x509.parse_cert(x509.make_cert(
            "Signer", "NF CA", leaf_k["public"], ca_k["private"]))
        ok, issues, _chain = x509.build_chain(leaf, [], [other])
        self.assertFalse(ok)
        self.assertTrue(issues)


class TimestampTest(unittest.TestCase):
    def setUp(self):
        self.ca_k = sm.sm2_keygen()
        self.tsa_k = sm.sm2_keygen()
        self.ca = x509.make_cert("NF CA", "NF CA", self.ca_k["public"],
                                 self.ca_k["private"], serial=1, is_ca=True)
        self.tsa_cert = x509.make_cert(
            "TSA", "NF CA", self.tsa_k["public"], self.ca_k["private"],
            serial=2)
        self.roots = [x509.parse_cert(self.ca)]

    def test_token_roundtrip(self):
        tok = tsa.make_token(b"message", self.tsa_cert,
                             self.tsa_k["private"])
        ok, issues = tsa.verify_token(tok, b"message", self.roots)
        self.assertTrue(ok, issues)
        parsed = tsa.parse_token(tok)
        self.assertEqual(parsed.tst.version, 2)

    def test_token_detects_tampered_message(self):
        tok = tsa.make_token(b"message", self.tsa_cert,
                             self.tsa_k["private"])
        ok, _issues = tsa.verify_token(tok, b"message-2", self.roots)
        self.assertFalse(ok)

    def test_time_value_branches(self):
        self.assertEqual(tsa.time_value_issues(None), ["缺少时间"])
        self.assertEqual(tsa.time_value_issues("20261102120000Z"), [])
        self.assertTrue(tsa.time_value_issues("not-base64!!"))

    def test_token_without_signed_attrs(self):
        tok = tsa.make_token(b"content", self.tsa_cert,
                             self.tsa_k["private"],
                             with_signed_attrs=False)
        ok, issues = tsa.verify_token(tok, b"content", self.roots)
        self.assertTrue(ok, issues)


class ContainerSmokeTest(unittest.TestCase):
    def test_png_text_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            png = str(Path(td) / "a.png")
            metadata.make_png(png, {"AIGC": '{"Label":1}'})
            self.assertEqual(metadata.sniff(png), "png")
            items = metadata.extract(png)
            self.assertEqual(items[0]["key"], "AIGC")
            cands = metadata.extract_json_candidates(png)
            self.assertEqual(cands[0]["obj"], {"Label": 1})

    def test_checker_png_signed_pass(self):
        with tempfile.TemporaryDirectory() as td:
            png = str(Path(td) / "a.png")
            metadata.make_png(png)
            keys = sm.sm2_keygen()
            content = metadata.content_bytes(png, "PNG")
            bind = sd.build_bindings(content, "PNG")
            sec = sd.build_security_data(RAW, bind, keys["private"])
            meta = dict(META, ReservedCode1=sec)
            metadata.inject_png_text(
                png, "AIGC",
                json.dumps({"AIGC": meta}, ensure_ascii=False, indent=2))
            report = checker.check_file(png)
            self.assertEqual(report["verdict"], "PASS", report)
            self.assertEqual(report["container"], "png")


if __name__ == "__main__":
    unittest.main()
