import unittest
from property_test import check_canonical, check_float_rejected, check_key_order_ignored, check_unicode_preserved


class PropertyTest(unittest.TestCase):
    def test_generated_roundtrip(self):
        self.assertEqual([], check_canonical())

    def test_float_rejected(self):
        self.assertTrue(check_float_rejected())

    def test_key_order_ignored(self):
        self.assertTrue(check_key_order_ignored())

    def test_unicode_preserved(self):
        self.assertTrue(check_unicode_preserved())


if __name__ == "__main__":
    unittest.main()
