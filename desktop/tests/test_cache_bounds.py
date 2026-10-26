"""常驻缓存**必须有界**（稳态毫秒级响应的隐含前提：长驻守护不能随会话增长而吃内存）。

依据（2026-09-30 取证）：仓库的「稳态」靠守护把语料/响应缓存在**进程生命周期内**活着——但
此前只有实现里的上限常量，**没有一条判据**。谁把 `MAX_ENTRIES` 去掉、或新加一个不设上限的
常驻容器，门禁一条都不会红，只有用户在长会话里慢慢感觉「越来越慢/越来越吃内存」。

判据两面：① 行为面——响应缓存真到上限就整批作废（且**先证它确实在存**，防「永不命中⇒永远不超」）；
② 声明面——已知的每个常驻容器都带着正的容量上限常量（新增常驻容器须在这里登记）。
"""
import unittest
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import conformance_scan as csc  # noqa: E402
from core import disk_cache as dc  # noqa: E402
from core import lazy_yaml  # noqa: E402
from core import pack_combo as pc  # noqa: E402
from core import repo_index as ri  # noqa: E402
from core import response_cache as rc  # noqa: E402

#: 常驻容器 → 其上限常量（新增常驻容器必须在此登记，否则本判据不知情）
CAPS = (
    (rc, "MAX_ENTRIES"),
    (csc, "_FENCE_CACHE_MAX"),
    (csc, "_FENCE_CACHE_MAX_BYTES"),
    (csc, "_BODY_CACHE_MAX"),
    (csc, "_BODY_CACHE_MAX_BYTES"),
    (csc, "_RESIDENT_DIR_MAX"),
    (csc, "_RESIDENT_TEXT_MAX"),
    (csc, "_RESIDENT_RAW_MAX_BYTES"),
    (csc, "_FACE_FP_MAX"),
    (dc, "KEEP"),
    (pc, "_CACHE_MAX"),
    (pc, "_CONTENT_CACHE_MAX"),
    (ri, "MAX_INDEXES"),
)


class CacheBoundsTest(unittest.TestCase):
    def test_yaml_unavailable_is_not_cached_as_a_content_result(self):
        """可选依赖暂时不可用时，不得把 None 固化进内容键缓存并污染后续请求。"""
        text = "```yaml\nmachine_contract:\n  id: M00\n```\n"
        key = ("machine_contract", text)
        saved = csc._FENCE_CACHE.copy()
        saved_bytes = csc._FENCE_CACHE_BYTES
        try:
            csc._FENCE_CACHE.pop(key, None)
            with mock.patch.object(lazy_yaml, "module", return_value=None):
                self.assertIsNone(csc._fence_yaml_opt(text, "machine_contract"))
            self.assertEqual(
                {"machine_contract": {"id": "M00"}},
                csc._fence_yaml_opt(text, "machine_contract"),
                "依赖恢复后仍读到旧 None ⇒ 可选依赖降级污染了内容键缓存",
            )
        finally:
            csc._FENCE_CACHE.clear()
            csc._FENCE_CACHE.update(saved)
            csc._FENCE_CACHE_BYTES = saved_bytes

    def test_response_cache_evicts_at_its_cap(self):
        rc.clear()
        self.addCleanup(rc.clear)
        gen = 1
        for i in range(10):                       # 先证「确实在存」（否则下面的断言是空转）
            rc.store(["stats", "--json", "--case=%d" % i], gen, True, 0, b"{}", b"")
        self.assertEqual(10, rc.entries(), "响应缓存没在存 ⇒ 本判据空转")

        for i in range(rc.MAX_ENTRIES + 50):
            rc.store(["stats", "--json", "--bulk=%d" % i], gen, True, 0, b"{}", b"")
        self.assertLessEqual(rc.entries(), rc.MAX_ENTRIES,
                             "响应缓存超上限（长驻守护会无界增长）")

    def test_every_long_lived_cache_declares_a_positive_cap(self):
        missing = []
        for mod, attr in CAPS:
            value = getattr(mod, attr, None)
            if not isinstance(value, int) or value <= 0:
                missing.append("%s.%s=%r" % (mod.__name__, attr, value))
        self.assertEqual([], missing, "常驻上限缺位/非法（修复指引：给该容器设正的容量上限）")


if __name__ == "__main__":
    unittest.main()
