#!/usr/bin/env python3
"""投稿面一致性门回归测试（2026-10-13 · 整体架构对齐）。

本测试守住两件事：
  1. 真仓当前**零漂移**（投稿面唯一真源 = library/intake.json 的 submission 段）；
  2. 判据对各类漂移**真的会红**（缺字段 / 悬空路径 / 声明了没有落点的闸门 /
     被禁的长度归因 / 口径锚点行不一致）。
第 2 项用临时夹具做变异，避免「判据写了但从没红过」的自欺。
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import intake_surface as isf  # noqa: E402

BT = chr(96)

#: 夹具依赖的在场物（判据会解析这些路径，缺一个就会多出无关 issue）
_STUB_FILES = (
    "scripts/nf.py",
    "verify.sh",
    ".github/scripts/library_ingest.py",
    "desktop/src/core/license_gate.py",
    "desktop/src/core/rating_gate.py",
)
_COPY_FILES = ("library/intake.json", "library/INDEX.md", "docs/agent/ROUTES.md")


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")


def _mutate(path: Path, old: str, new: str) -> None:
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def _fixture(tmp: str) -> None:
    """最小可判夹具：声明件 + 须知 + 路由 + 四份模板 + 判据依赖的全部在场物。"""
    root = Path(tmp)
    for rel in _COPY_FILES:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    tpl_dir = ROOT / ".github" / "ISSUE_TEMPLATE"
    for p in sorted([*tpl_dir.glob("*.md"), *tpl_dir.glob("*.yml")]):
        dst = root / ".github" / "ISSUE_TEMPLATE" / p.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
    (root / ".gitee" / "ISSUE_TEMPLATE").mkdir(parents=True, exist_ok=True)
    for rel in _STUB_FILES:
        _touch(root / rel)
    for d in ("scripts", "desktop", "tui", "engine", "integrations", "site"):
        (root / d).mkdir(parents=True, exist_ok=True)


class TestIntakeSurface(unittest.TestCase):
    def test_repo_is_aligned(self):
        issues, stats = isf.scan(str(ROOT))
        self.assertEqual([], issues, f"投稿面漂移：{issues}")
        self.assertGreater(stats["templates"], 0)
        self.assertGreater(stats["fields"], 0)
        self.assertGreater(stats["gates"], 0)

    def test_missing_field_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            p = Path(tmp) / ".github" / "ISSUE_TEMPLATE" / "library_submission.md"
            _mutate(p, "分级：", "等第：")
            issues, _ = isf.scan(tmp)
            self.assertTrue(any("缺可见字段" in i and "分级" in i for i in issues), issues)

    def test_dangling_path_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            p = Path(tmp) / ".github" / "ISSUE_TEMPLATE" / "library_submission.md"
            p.write_text(p.read_text(encoding="utf-8") + f"\n见 {BT}docs/nope.md{BT}。\n",
                          encoding="utf-8")
            issues, _ = isf.scan(tmp)
            self.assertTrue(any("悬空引用" in i for i in issues), issues)

    def test_gate_without_impl_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            p = Path(tmp) / "library" / "intake.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            d["channels"]["gitee"]["gate"].append("no_such_gate")
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            issues, _ = isf.scan(tmp)
            self.assertTrue(any("no_such_gate" in i for i in issues), issues)

    def test_banned_attribution_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            p = Path(tmp) / "library" / "INDEX.md"
            _mutate(p, "256 KiB", "256 KiB（平台限制），")
            issues, _ = isf.scan(tmp)
            self.assertTrue(any("平台限制" in i for i in issues), issues)

    def test_anchor_line_drift_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            p = Path(tmp) / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
            _mutate(p, "community 包", "community包")
            issues, _ = isf.scan(tmp)
            self.assertTrue(any("锚点行" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
