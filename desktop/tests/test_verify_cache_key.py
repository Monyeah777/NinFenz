"""verify_cache key 的输入面（D2/D3/D5/D6）：忽略面产物 / 历史 tag / 失败即不缓存。"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
spec = importlib.util.spec_from_file_location("vc", ROOT / "scripts" / "verify_cache.py")
assert spec is not None and spec.loader is not None
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True,
                   capture_output=True, text=True)


class VerifyCacheKeyTest(unittest.TestCase):
    def setUp(self):
        self._old_root = vc.ROOT
        self.tmp = tempfile.TemporaryDirectory(prefix="nf-cache-key-")
        self.root = Path(self.tmp.name)
        _git(self.root, "init", "-q")
        _git(self.root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
             "--allow-empty", "-m", "init")
        (self.root / "a.txt").write_text("a", encoding="utf-8")
        _git(self.root, "add", "a.txt")
        _git(self.root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
             "-m", "a")
        vc.ROOT = self.root

    def tearDown(self):
        vc.ROOT = self._old_root
        self.tmp.cleanup()

    def test_clean_key_is_stable(self):
        self.assertEqual(vc.compute_key("quick"), vc.compute_key("quick"))

    def test_ignored_inputs_change_key(self):
        k1 = vc.compute_key("quick")
        (self.root / ".gitignore").write_text(".gitee/\n", encoding="utf-8")
        _git(self.root, "add", ".gitignore")
        _git(self.root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
             "-m", "gitignore")
        k2 = vc.compute_key("quick")
        self.assertNotEqual(k1, k2, "加 .gitignore 本身就该改 key（tracked 内容变了）")
        (self.root / ".gitee" / "ISSUE_TEMPLATE").mkdir(parents=True)
        k3 = vc.compute_key("quick")
        self.assertNotEqual(k2, k3, "忽略面目录出现必须改 key（D2）")

    def test_tag_history_changes_key(self):
        k1 = vc.compute_key("quick")
        _git(self.root, "tag", "v1")
        self.assertNotEqual(k1, vc.compute_key("quick"), "tag 面必须进 key（D3）")


if __name__ == "__main__":
    unittest.main()
