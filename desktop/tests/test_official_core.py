#!/usr/bin/env python3
"""官方核心件清单的一致性（审计 Z1 F6：4 处硬编码、1 处写成 12）。

真源 = desktop/src/core/registry.json 的 modules[]。本判据钉三件事：
① Python 单一实现 official_core.CORE_MODULES == 真源；
② 三个消费方（pack_combo / market_analyzer / protocol_wizard）逐项一致且都是 13 件；
③ Rust 端 output_tables.rs 的 CORE13 转录同集合（跨语言夹具）。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import market_analyzer, official_core, pack_combo, protocol_wizard  # noqa: E402

REGISTRY = ROOT / "desktop" / "src" / "core" / "registry.json"
RUST_TABLE = ROOT / "engine" / "rust" / "src" / "output_tables.rs"
VERIFY = ROOT / "verify.sh"


def _bash_blocks(text: str, name: str) -> list:
    return re.findall(name + r"\s*=\s*\[(.*?)\]", text, re.S)


def _quoted(block: str) -> list:
    return re.findall(r"'([^']+)'", block)


def _raw(mid: str) -> str:
    return str(mid).split(":")[-1]


def _file_num(path: str) -> str:
    m = re.search(r"/M(\d+)_", path)
    return "M" + m.group(1) if m else ""


def registry_core_ids(root: Path = ROOT) -> list:
    doc = json.loads((root / "desktop" / "src" / "core" / "registry.json")
                     .read_text(encoding="utf-8"))
    return [str(m["id"]) for m in doc.get("modules") or []]


class OfficialCoreTest(unittest.TestCase):
    def test_single_source_matches_registry_truth(self):
        truth = registry_core_ids()
        self.assertEqual(len(truth), 13, "registry.json 官方核心件数变了：%d" % len(truth))
        self.assertEqual(set(truth), set(official_core.CORE_MODULES),
                         "official_core 与 registry.json 真源分叉")
        self.assertEqual(len(official_core.CORE_MODULES),
                         len(set(official_core.CORE_MODULES)), "清单有重复项")

    def test_three_consumers_are_identical_and_include_m90(self):
        want = list(official_core.CORE_MODULES)
        self.assertEqual(want, list(pack_combo.CORE13), "pack_combo.CORE13 分叉")
        self.assertEqual(want, list(market_analyzer.OFFICIAL13), "market_analyzer.OFFICIAL13 分叉")
        self.assertEqual(want, list(protocol_wizard.DEFAULT_CORE_MODULES),
                         "protocol_wizard.DEFAULT_CORE_MODULES 分叉（F6 的 12 件缺 M90）")
        self.assertEqual(13, len(want))
        self.assertIn("M90", want, "技术文档件 M90 是官方核心第 13 件")

    def test_rust_transcription_matches(self):
        text = RUST_TABLE.read_text(encoding="utf-8")
        block = text.split("pub const CORE13", 1)[1].split("];", 1)[0]
        rust_ids = [seg.split('"')[1] for seg in block.split(",") if '"' in seg]
        self.assertEqual(set(official_core.CORE_MODULES), set(rust_ids),
                         "Rust output_tables.rs 的 CORE13 与 Python 单一实现分叉")

    def test_verify_sh_lists_match_single_source(self):
        """bash 侧（verify.sh 的 OFFICIAL13 / CORE13）也不许各写一份（跨实现夹具）。"""
        text = VERIFY.read_text(encoding="utf-8")
        want = {_raw(x) for x in official_core.CORE_MODULES}
        off_blocks = _bash_blocks(text, "OFFICIAL13")
        self.assertEqual(2,
 len(off_blocks),
 "verify.sh 的 OFFICIAL13 块数变了：%d" % len(off_blocks))
        for b in off_blocks:
            self.assertEqual(want, {_raw(x) for x in _quoted(b)},
                             "verify.sh OFFICIAL13 与单一实现分叉")
        core_blocks = _bash_blocks(text, "CORE13")
        self.assertTrue(core_blocks, "verify.sh 找不到 CORE13 数组")
        files = _quoted(core_blocks[0])
        self.assertEqual(13, len(files), "verify.sh CORE13 不是 13 件")
        self.assertEqual(want, {_file_num(p) for p in files},
                         "verify.sh CORE13 文件清单与单一实现分叉")

    def test_missing_m90_would_be_caught(self):
        truncated = tuple(x for x in official_core.CORE_MODULES if x != "M90")
        self.assertNotEqual(set(registry_core_ids()), set(truncated),
                            "夹具自证：缺 M90 必须被判为分叉")


if __name__ == "__main__":
    unittest.main()
