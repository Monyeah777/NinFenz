import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import error_codes as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "protocol" / "error_codes.json"

#: CCOS ABI v0 声明的 14 条错误码（docs/ccos/abi-v0.md §7 个调用）
ABI_CODES = sorted({
    "cc.attest.empty_key", "cc.attest.no_subject", "cc.attest.verifier_missing",
    "cc.label.embed_failed", "cc.label.no_contract", "cc.label.unsupported_carrier",
    "cc.verify.digest_mismatch", "cc.verify.expired", "cc.verify.key_required",
    "cc.verify.no_attestation", "cc.verify.not_a_bundle", "cc.verify.proof_mismatch",
    "cc.verify.revoked", "cc.verify.root_mismatch",
})


class Test(unittest.TestCase):
    def test_validate_and_lookup(self):
        reg = {"codes": [{"id": "NF_NO_MODULE", "message": "缺模块", "fix": "补模块"}]}
        self.assertEqual([], E.validate(reg))
        self.assertEqual(("缺模块", "补模块"), E.lookup(reg, "NF_NO_MODULE"))

    def test_duplicate_and_bad_lexis(self):
        reg = {"codes": [{"id": "bad", "message": "m", "fix": "f"},
                         {"id": "NF_X", "message": "m", "fix": "f"},
                         {"id": "NF_X", "message": "m", "fix": "f"}]}
        issues = E.validate(reg)
        self.assertTrue(any("词法" in i for i in issues))
        self.assertTrue(any("重复" in i for i in issues))

    def test_unknown_code_raises(self):
        with self.assertRaises(ValueError):
            E.lookup({"codes": []}, "NF_X")

    def test_cc_lexis_accepted_and_junk_rejected(self):
        good = {"codes": [{"id": "cc.verify.revoked", "message": "m", "fix": "修复指引：f"},
                          {"id": "NF_X", "message": "m", "fix": "修复指引：f"}]}
        self.assertEqual([], E.validate(good))
        for bad in ("cc", "cc.verify", "CC.VERIFY.REVOKED", "cc..x"):
            issues = E.validate({"codes": [{"id": bad, "message": "m", "fix": "修复指引：f"}]})
            self.assertTrue(any("词法" in i for i in issues), bad)

    def test_registry_file_covers_abi_error_face(self):
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual([], E.validate(reg))
        ids = {e["id"] for e in reg["codes"]}
        self.assertEqual(sorted(set(ABI_CODES) - ids), [], "ABI 错误码未登记")
        for code in ABI_CODES:
            message, fix = E.lookup(reg, code)
            self.assertTrue(message, code)
            self.assertTrue(fix.startswith("修复指引："), code)
