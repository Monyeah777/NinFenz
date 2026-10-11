import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import schema_pins as P  # noqa: E402


class Test(unittest.TestCase):
    def test_validate_and_covers(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "v1.json")
            f.write_text("{}", encoding="utf-8")
            import hashlib
            dig = hashlib.sha256(f.read_bytes()).hexdigest()
            self.assertEqual([], P.validate([{"schema_version": "1", "fixture": "v1.json", "digest": dig}], d))
            self.assertEqual(["2"], P.covers(["1", "2"], [{"schema_version": "1", "fixture": "v1.json", "digest": dig}]))

    def test_drift(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "v1.json").write_text("{}", encoding="utf-8")
            self.assertTrue(any("漂移" in i for i in P.validate(
                [{"schema_version": "1", "fixture": "v1.json", "digest": "0" * 64}], d)))
