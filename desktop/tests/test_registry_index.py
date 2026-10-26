#!/usr/bin/env python3
"""契约注册表 CID 索引（T8.2）判据：确定性 / 幂等 / 篡改 / 增删 / 顺序无关 / 空集合。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import registry_index as ri  # noqa: E402


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _pack(root: Path, pid: str, version: str = "1.0.0",
          extra: dict | None = None) -> None:
    base = "community/%s" % pid
    _write(root, base + "/protocol.yaml",
           "package:\n  id: %s\n  version: \"%s\"\n" % (pid, version))
    _write(root, base + "/README.md", "# %s\n" % pid)
    _write(root, base + "/modules/M01_x.md", "module %s\n" % pid)
    _write(root, base + "/assets/A01_x.md", "asset %s\n" % pid)
    _write(root, base + "/pipelines/P01_x.md", "pipeline %s\n" % pid)
    for rel, text in (extra or {}).items():
        _write(root, base + "/" + rel, text)


def _scene(pids=("b包", "a包"), versions=None) -> Path:
    """建最小可算仓库：registry.json + community/<id>/ 五类件。"""
    tmp = Path(tempfile.mkdtemp(prefix="nf-regidx-"))
    versions = versions or {p: "1.0.0" for p in pids}
    reg = {"registry_schema_version": "2",
           "protocols": [{"id": p, "version": versions[p]} for p in pids]}
    _write(tmp, "desktop/src/core/registry.json",
           json.dumps(reg, ensure_ascii=False, indent=2))
    for pid in pids:
        _pack(tmp, pid, versions[pid])
    return tmp


def _write_index(root: Path):
    issues, doc = ri.write(str(root))
    assert not issues, issues
    return doc


class ManifestTest(unittest.TestCase):
    def test_paths_sorted_and_scope_bounded(self):
        root = _scene(("a包",))
        files = ri.collect_manifest(str(root / "community" / "a包"))
        paths = [p for p, _ in files]
        self.assertEqual(sorted(paths), paths, "manifest 文件路径未按码点序排序")
        self.assertEqual(["README.md", "assets/A01_x.md", "modules/M01_x.md",
                          "pipelines/P01_x.md", "protocol.yaml"], paths)
        # 范围即契约：包根杂物不进 manifest（且会触发未登记扫描的是包目录，不是文件）
        _write(root, "community/a包/notes.txt", "杂物\n")
        self.assertEqual(files, ri.collect_manifest(str(root / "community" / "a包")),
                         "manifest 混入了范围外的包根文件")

    def test_content_change_changes_cid(self):
        root = _scene(("a包",))
        pack = str(root / "community" / "a包")
        before = ri.pack_cid(ri.collect_manifest(pack))
        _write(root, "community/a包/assets/A01_x.md", "tampered\n")
        after = ri.pack_cid(ri.collect_manifest(pack))
        self.assertNotEqual(before, after, "内容改动未改变 CID")

    def test_bom_and_newline_are_content(self):
        root = _scene(("a包",))
        pack = root / "community" / "a包"
        before = ri.pack_cid(ri.collect_manifest(str(pack)))
        raw = (pack / "README.md").read_bytes()
        (pack / "README.md").write_bytes(b"\xef\xbb\xbf" + raw)      # 仅加 BOM
        after = ri.pack_cid(ri.collect_manifest(str(pack)))
        self.assertNotEqual(before, after, "字节级改动（BOM）未改变 CID")


class ComputeTest(unittest.TestCase):
    def test_write_idempotent_and_check_clean(self):
        root = _scene()
        doc1 = _write_index(root)
        text1 = (root / ri.INDEX_REL).read_text(encoding="utf-8")
        doc2 = _write_index(root)
        text2 = (root / ri.INDEX_REL).read_text(encoding="utf-8")
        self.assertEqual(text1, text2, "同树两次 --write 字节不一致（非确定性）")
        self.assertEqual(doc1, doc2)
        issues, _ = ri.check(str(root))
        self.assertEqual([], issues, issues)

    def test_registry_order_does_not_change_root(self):
        root = _scene(("a包", "b包", "c包"))
        doc1 = _write_index(root)
        reg = json.loads((root / "desktop/src/core/registry.json").read_text(encoding="utf-8"))
        reg["protocols"] = list(reversed(reg["protocols"]))
        _write(root, "desktop/src/core/registry.json",
               json.dumps(reg, ensure_ascii=False, indent=2))
        doc2, issues = ri.compute(str(root))
        self.assertEqual([], issues)
        self.assertEqual(doc1["root"], doc2["root"], "protocols 顺序影响了 root")
        self.assertEqual([e["id"] for e in doc2["entries"]], ["a包", "b包", "c包"])

    def test_empty_set_is_deterministic(self):
        root = _scene(pids=())
        doc = _write_index(root)
        self.assertEqual([], doc["entries"])
        self.assertEqual(ri.root_of([]), doc["root"])
        issues, _ = ri.check(str(root))
        self.assertEqual([], issues, issues)
        # 空集 root 必须等于「schema + 空 entries」的 canonical 摘要（域分隔不省略）
        self.assertEqual(doc["root"], ri._h(ri._canonical({"schema": ri.SCHEMA, "entries": []})))


class TamperTest(unittest.TestCase):
    def test_pack_file_tamper_reports_file(self):
        root = _scene(("a包",))
        _write_index(root)
        _write(root, "community/a包/modules/M01_x.md", "tampered!\n")
        issues, _ = ri.check(str(root))
        joined = "\n".join(issues)
        self.assertIn("CID 不一致", joined, issues)
        self.assertIn("community/a包/modules/M01_x.md", joined, issues)
        self.assertIn("内容已变", joined, issues)
        self.assertIn("registry_index.json:", joined, "差异未给索引行号")

    def test_add_and_remove_file_change_count_and_cid(self):
        root = _scene(("a包",))
        doc = _write_index(root)
        old = doc["entries"][0]
        _write(root, "community/a包/assets/A02_new.md", "new asset\n")
        issues, _ = ri.check(str(root))
        joined = "\n".join(issues)
        self.assertIn("files_count 变", joined, issues)
        self.assertIn("新增文件：community/a包/assets/A02_new.md", joined, issues)
        # 重生成后基线 = 6 件；再删一件 → 5 件，且删文件被抓
        doc_mid = _write_index(root)
        (root / "community/a包/pipelines/P01_x.md").unlink()
        issues2, _ = ri.check(str(root))
        joined2 = "\n".join(issues2)
        self.assertIn("文件不在索引/manifest 内：community/a包/pipelines/P01_x.md", joined2,
                      issues2)
        new = ri.compute(str(root))[0]["entries"][0]
        self.assertNotEqual(old["cid"], new["cid"])
        self.assertLess(new["files_count"], doc_mid["entries"][0]["files_count"])

    def test_index_itself_tampered_is_caught(self):
        root = _scene(("a包",))
        _write_index(root)
        p = root / ri.INDEX_REL
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["entries"][0]["cid"] = "0" * 64
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        issues, _ = ri.check(str(root))
        joined = "\n".join(issues)
        self.assertIn("cid 与自身 files 不匹配", joined, issues)
        self.assertIn("root 与 entries 实时重算不一致", joined, issues)

    def test_sig_non_empty_fails_closed(self):
        doc, _ = ri.compute(str(_scene(("a包",))))
        doc["entries"][0]["sig"] = "hmac:deadbeef"
        issues = ri.verify_doc(doc)
        self.assertTrue(any("sig 非空但无验证器" in i for i in issues), issues)

    def test_missing_index_and_unregistered_pack(self):
        root = _scene(("a包",))
        issues, _ = ri.check(str(root))
        self.assertTrue(any("缺 protocol/registry_index.json" in i for i in issues), issues)
        _write_index(root)
        _pack(root, "b包")                                    # 盘上新增、registry 未登记
        issues2, _ = ri.check(str(root))
        self.assertTrue(any("未登记包目录" in i for i in issues2), issues2)
        reg = json.loads((root / "desktop/src/core/registry.json").read_text(encoding="utf-8"))
        reg["protocols"].append({"id": "ghost包", "version": "1.0.0"})
        _write(root, "desktop/src/core/registry.json",
               json.dumps(reg, ensure_ascii=False, indent=2))
        issues3, _ = ri.check(str(root))
        self.assertTrue(any("登记包在盘上不存在：community/ghost包" in i for i in issues3), issues3)


class RealRepoTest(unittest.TestCase):
    """真仓库常驻判据：committed 的 index 必须与实时重算一致（相当于门禁的那一条）。"""

    def test_repo_index_in_sync(self):
        if not (ROOT / ri.INDEX_REL).is_file():
            self.skipTest("protocol/registry_index.json 尚未生成")
        issues, doc = ri.check(str(ROOT))
        self.assertEqual([], issues, issues[:5])
        self.assertGreater(len(doc["entries"]), 100, "登记包数量异常")
        self.assertEqual("", doc["entries"][0]["sig"], "本版 sig 必须留空")


if __name__ == "__main__":
    unittest.main()
