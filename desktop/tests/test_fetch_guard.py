import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import fetch_guard as G  # noqa: E402


class Test(unittest.TestCase):
    def test_ok(self):
        self.assertEqual([], G.check_url("https://api.github.com/x", ["api.github.com"]))

    def test_http_and_host_not_pinned(self):
        issues = G.check_url("http://evil.example/x", ["api.github.com"])
        self.assertTrue(any("https" in i for i in issues))
        self.assertTrue(any("宿主" in i for i in issues))

    def test_credentials_and_redirects(self):
        issues = G.check_url("https://u:p@api.github.com/x", ["api.github.com"], allow_redirects=True)
        self.assertTrue(any("凭据" in i for i in issues))
        self.assertTrue(any("重定向" in i for i in issues))
