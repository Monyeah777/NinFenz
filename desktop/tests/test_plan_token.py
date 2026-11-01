"""plan_token 单测。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import plan_token as T  # noqa: E402


class Test(unittest.TestCase):
    def test_happy_path_and_single_use(self):
        tok = T.issue("plan", "digest1", "YES-GO", 60, now=100)
        ok, _ = T.consume(tok, "YES-GO", "digest1", now=110)
        self.assertTrue(ok)
        ok2, why = T.consume(tok, "YES-GO", "digest1", now=111)
        self.assertFalse(ok2)
        self.assertIn("消费", why)

    def test_expired_and_mismatch(self):
        tok = T.issue("p", "d", "P", 10, now=0)
        self.assertFalse(T.consume(tok, "P", "d", now=11)[0])
        tok = T.issue("p", "d", "P", 10, now=0)
        self.assertFalse(T.consume(tok, "p", "d", now=1)[0])
        tok = T.issue("p", "d", "P", 10, now=0)
        self.assertFalse(T.consume(tok, "P", "other", now=1)[0])
