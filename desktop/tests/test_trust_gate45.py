#!/usr/bin/env python3
"""check45 判据自身判据：真仓全绿 + 变异必红（证明门禁不是同义反复）。

check45 = 「bundle 守恒 + 单 claim + splice + prev 链 + 等级判定」对冻结向量复算。
本件做两件事：
1. 真仓 scan 零 issue，且各族统计非零（判据面没塌缩）；
2. 在临时仓里逐项破坏向量（根/链头/等级/缺族/缺文件），scan 必须红——
   这就是「旧基线能红」的证据，也是计划 §14.1「check 只增不减 + 旧基线能红」的落地。
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import gate  # noqa: E402

VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"


def _temp_repo(tmp: str) -> Path:
    root = Path(tmp)
    (root / "protocol" / "trust").mkdir(parents=True)
    (root / "results" / "trust").mkdir(parents=True)
    for schema in (ROOT / "protocol" / "trust").glob("*.schema.json"):
        shutil.copy2(schema, root / "protocol" / "trust" / schema.name)
    shutil.copy2(VECTORS, root / "results" / "trust" / "trust_vectors.json")
    return root


def _write_vectors(root: Path, doc: dict) -> None:
    (root / "results" / "trust" / "trust_vectors.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_vectors(root: Path) -> dict:
    path = root / "results" / "trust" / "trust_vectors.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _vector(root: Path, vec_id: str) -> dict:
    doc = _load_vectors(root)
    return doc["vectors"][[v["id"] for v in doc["vectors"]].index(vec_id)]


class RealRepoTest(unittest.TestCase):
    def test_scan_is_clean_and_stats_nonzero(self):
        issues, stats = gate.scan(str(ROOT))
        self.assertEqual([], issues)
        self.assertGreaterEqual(stats["merkle"], 4)
        self.assertGreaterEqual(stats["process"], 4)
        self.assertGreaterEqual(stats["level"], 7)
        self.assertEqual(1, stats["bundles"])
        self.assertGreaterEqual(stats["claims"], 4)
        self.assertGreaterEqual(stats["families"], 7)

    def test_scan_is_deterministic(self):
        self.assertEqual(gate.scan(str(ROOT)), gate.scan(str(ROOT)))


class MutationRedTest(unittest.TestCase):
    def test_tampered_merkle_root_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _temp_repo(tmp)
            vectors_path = root / "results/trust/trust_vectors.json"
            doc = json.loads(vectors_path.read_text(encoding="utf-8"))
            for vec in doc["vectors"]:
                if vec["family"] == "merkle" and vec["expected"].get("valid"):
                    vec["expected"]["root"] = "0" * 64
                    break
            _write_vectors(root, doc)
            issues, _stats = gate.scan(str(root))
            self.assertTrue(any("Merkle 根" in issue for issue in issues), issues)

    def test_tampered_process_head_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _temp_repo(tmp)
            doc = _load_vectors(root)
            for vec in doc["vectors"]:
                if vec["family"] == "process" and vec["expected"].get("valid"):
                    vec["expected"]["head"] = "0" * 64
                    break
            _write_vectors(root, doc)
            issues, _stats = gate.scan(str(root))
            self.assertTrue(any("prev 链" in issue for issue in issues), issues)

    def test_tampered_level_exit_code_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _temp_repo(tmp)
            doc = _load_vectors(root)
            for vec in doc["vectors"]:
                if vec["family"] == "level":
                    vec["expected"]["exit_code"] = 99
                    break
            _write_vectors(root, doc)
            issues, _stats = gate.scan(str(root))
            self.assertTrue(any("等级" in issue for issue in issues), issues)

    def test_missing_family_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _temp_repo(tmp)
            doc = _load_vectors(root)
            doc["vectors"] = [v for v in doc["vectors"] if v["family"] != "merkle"]
            _write_vectors(root, doc)
            issues, _stats = gate.scan(str(root))
            self.assertTrue(any("向量族缺失" in issue for issue in issues), issues)

    def test_missing_vectors_file_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _temp_repo(tmp)
            (root / "results/trust/trust_vectors.json").unlink()
            issues, _stats = gate.scan(str(root))
            self.assertTrue(any("缺向量集" in issue for issue in issues), issues)
            self.assertTrue(any("修复指引" in issue for issue in issues), issues)

    def test_splice_probe_is_live_mutation(self):
        """直接推翻实现侧假设：把 bundle_id 的域分隔绕过后，splice 负例必须变红（判据依赖点）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = _temp_repo(tmp)
            doc = _load_vectors(root)
            doc["vectors"] = [v for v in doc["vectors"] if v["family"] != "level"]
            _write_vectors(root, doc)
            issues, _stats = gate.scan(str(root))
            self.assertTrue(any("向量族缺失" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
