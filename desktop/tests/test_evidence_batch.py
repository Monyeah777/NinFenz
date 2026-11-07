"""批量复验（core.evidence.verify_batch / nf evidence batch）判据。

批量面的核心承诺只有一句：**任何一件非 ok 就整体 ok=False**——批量是「这一批能不能用」，
不是「平均下来还行」。所以判据集中在：目录挑选规则、空/超限带指引拒绝、混合批次逐件记账、
以及 CLI 退出码（0 只代表每一件都 ok）。
"""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import evidence  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"
STAMP = "2026-01-01T00:00:00Z"


def _fixture(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
    (root / "docs" / "b.md").write_text("# B\n", encoding="utf-8")


def _bundle(root: Path, rels: list, name: str) -> Path:
    data, _info = evidence.build(str(root), rels, created_at=STAMP)
    out = root / name
    out.write_bytes(data)
    return out


def _tamper(path: Path) -> None:
    """改一个 payload 成员的字节（摘要/根都会对不上）。"""
    with zipfile.ZipFile(path) as zf:
        members = {n: zf.read(n) for n in zf.namelist()}
    target = next(n for n in sorted(members) if n.startswith(evidence.PAYLOAD_DIR))
    members[target] = members[target] + b"tampered"
    path.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zf.writestr(info, members[name])


class BatchPathsTest(unittest.TestCase):
    """目录挑选规则：只取 *.zip/*.json、按名排序、空目录要拒绝（空结果最像全绿）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nf_batch_")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _fixture(self.dir)

    def test_single_file_target(self):
        p = _bundle(self.dir, ["docs/a.md"], "a.zip")
        self.assertEqual([str(p)], evidence.batch_paths(str(p)))

    def test_directory_picks_zip_and_json_sorted(self):
        _bundle(self.dir, ["docs/a.md"], "b.zip")
        _bundle(self.dir, ["docs/b.md"], "a.zip")
        (self.dir / "note.txt").write_text("x", encoding="utf-8")
        (self.dir / "meta.json").write_text("{}", encoding="utf-8")
        names = [Path(x).name for x in evidence.batch_paths(str(self.dir))]
        self.assertEqual(["a.zip", "b.zip", "meta.json"], names)

    def test_empty_directory_is_rejected_with_guidance(self):
        empty = self.dir / "empty"
        empty.mkdir()
        with self.assertRaises(ValueError) as ctx:
            evidence.batch_paths(str(empty))
        self.assertIn("修复指引", str(ctx.exception))

    def test_missing_target_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            evidence.batch_paths(str(self.dir / "nope"))
        self.assertIn("修复指引", str(ctx.exception))

    def test_too_many_files_is_rejected(self):
        for i in range(3):
            (self.dir / f"x{i}.zip").write_bytes(b"PK\x03\x04junk")
        with self.assertRaises(ValueError) as ctx:
            evidence.batch_paths(str(self.dir), max_files=2)
        self.assertIn("上限", str(ctx.exception))


class VerifyBatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nf_batch2_")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _fixture(self.dir)

    def test_all_ok(self):
        _bundle(self.dir, ["docs/a.md"], "a.zip")
        _bundle(self.dir, ["docs/b.md"], "b.zip")
        res = evidence.verify_batch(str(self.dir))
        self.assertTrue(res["ok"])
        self.assertEqual(2, res["total"])
        self.assertEqual({"ok": 2}, res["counts"])
        self.assertEqual(0, res["failures"])

    def test_one_bad_makes_whole_batch_fail(self):
        _bundle(self.dir, ["docs/a.md"], "a.zip")
        bad = _bundle(self.dir, ["docs/b.md"], "b.zip")
        _tamper(bad)
        res = evidence.verify_batch(str(self.dir))
        self.assertFalse(res["ok"], "批量的意义是整批可用，不是平均")
        self.assertEqual(1, res["failures"])
        self.assertEqual(1, res["counts"].get("invalid"))
        self.assertEqual("a.zip", res["rows"][0]["path"])

    def test_rows_carry_verdict_and_root(self):
        _bundle(self.dir, ["docs/a.md"], "a.zip")
        row = evidence.verify_batch(str(self.dir))["rows"][0]
        self.assertEqual("ok", row["verdict"])
        self.assertTrue(row["root"])
        self.assertTrue(row["level"])

    def test_single_file_target_works(self):
        p = _bundle(self.dir, ["docs/a.md"], "a.zip")
        res = evidence.verify_batch(str(p))
        self.assertEqual(1, res["total"])
        self.assertTrue(res["ok"])


class CliBatchTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "evidence", "batch", *args],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def test_json_summary_and_zero_exit(self):
        with tempfile.TemporaryDirectory(prefix="nf_batch_cli_") as tmp:
            root = Path(tmp)
            _fixture(root)
            _bundle(root, ["docs/a.md"], "a.zip")
            proc = self._run(str(root), "--json")
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            doc = json.loads(proc.stdout)
            self.assertEqual(1, doc["total"])
            self.assertTrue(doc["ok"])

    def test_bad_bundle_exits_nonzero(self):
        with tempfile.TemporaryDirectory(prefix="nf_batch_cli2_") as tmp:
            root = Path(tmp)
            _fixture(root)
            bad = _bundle(root, ["docs/a.md"], "a.zip")
            _tamper(bad)
            proc = self._run(str(root), "--json")
            self.assertEqual(1, proc.returncode)
            self.assertFalse(json.loads(proc.stdout)["ok"])

    def test_empty_dir_is_usage_error(self):
        with tempfile.TemporaryDirectory(prefix="nf_batch_cli3_") as tmp:
            proc = self._run(str(Path(tmp)), "--json")
            self.assertEqual(2, proc.returncode)


if __name__ == "__main__":
    unittest.main()
