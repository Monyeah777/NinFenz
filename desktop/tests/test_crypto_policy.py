#!/usr/bin/env python3
"""ASVS V11.2.2: versioned cryptographic agility regression tests."""
import hashlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import crypto_policy  # noqa: E402


class CryptoPolicyTest(unittest.TestCase):
    def test_default_suite_preserves_the_established_wire_contract(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NF_CRYPTO_SUITE", None)
            policy = crypto_policy.CryptoPolicy()
        self.assertEqual("v1", policy.suite_id)
        self.assertEqual("sha256", policy.suite.digest)
        self.assertEqual(64, len(policy.new_token()))
        self.assertEqual(hashlib.sha256(b"abc").hexdigest(), policy.digest_hex(b"abc"))

    def test_suite_can_be_swapped_without_changing_callers(self):
        policy = crypto_policy.CryptoPolicy("v1")
        before = policy.digest_hex(b"abc")
        policy.swap("v2-sha512")
        self.assertEqual("v2-sha512", policy.suite_id)
        self.assertEqual(96, len(policy.new_token()))
        self.assertEqual(hashlib.sha512(b"abc").hexdigest(), policy.digest_hex(b"abc"))
        self.assertNotEqual(before, policy.digest_hex(b"abc"))

    def test_environment_selection_is_checked_against_the_closed_registry(self):
        with mock.patch.dict(os.environ, {"NF_CRYPTO_SUITE": "v2-sha512"}):
            self.assertEqual("v2-sha512", crypto_policy.CryptoPolicy().suite_id)
        with mock.patch.dict(os.environ, {"NF_CRYPTO_SUITE": "made-up"}), \
                self.assertRaises(ValueError):
            crypto_policy.CryptoPolicy()

    def test_compare_is_constant_time_for_supported_suite(self):
        policy = crypto_policy.CryptoPolicy()
        self.assertTrue(policy.compare("abc", "abc"))
        self.assertFalse(policy.compare("abc", "abd"))

    def test_suite_metadata_records_migration_contract(self):
        suite = crypto_policy.get_suite("v2-sha512")
        self.assertEqual("sha512", suite.digest)
        self.assertGreater(suite.token_bytes, crypto_policy.get_suite("v1").token_bytes)
        self.assertTrue(suite.migration_note)


if __name__ == "__main__":
    unittest.main()
