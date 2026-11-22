import unittest
from flash_fill import InferError, Transform, apply_all, infer


class FlashFillTest(unittest.TestCase):
    def test_suffix(self):
        self.assertEqual(infer([("标题", "标题！"), ("正文", "正文！")]), Transform("suffix", "！"))

    def test_prefix(self):
        self.assertEqual(infer([("文", "【文"), ("稿", "【稿")]), Transform("prefix", "【"))

    def test_strip_prefix(self):
        self.assertEqual(infer([("# 文", "文"), ("# 稿", "稿")]), Transform("strip_prefix", "# "))

    def test_strip_suffix(self):
        self.assertEqual(infer([("文！", "文"), ("稿！", "稿")]), Transform("strip_suffix", "！"))

    def test_truncate(self):
        self.assertEqual(infer([("abcdef", "abc"), ("uvwxyz", "uvw")]), Transform("truncate", "3"))

    def test_replace(self):
        self.assertEqual(infer([("请报名", "请登记"), ("报名入口", "登记入口")]), Transform("replace", "报名", "登记"))

    def test_apply_all(self):
        t = infer([("a", ">a"), ("b", ">b")])
        self.assertEqual(apply_all(t, ["x", "y"]), [">x", ">y"])

    def test_no_rule(self):
        with self.assertRaises(InferError):
            infer([("a", "b")])

    def test_same_rejected(self):
        with self.assertRaises(InferError):
            infer([("a", "a")])


if __name__ == "__main__":
    unittest.main()
