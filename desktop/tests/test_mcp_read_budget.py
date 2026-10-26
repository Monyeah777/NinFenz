"""MCP 工具面的**读取面预算**（稳态计数判据，不测墙钟）。

口径同 `test_nf_cli.LightCommandReadBudgetTest`：**能数就别计时**——一旦有人把「全仓扫描」
塞进本该只读几个文件的工具，打开次数会从个位数跳到四位数，当场红；内容自然增长不会误伤
（面板留了两个数量级余量）。

2026-10-23 起工具面走 `core.repo_index.RepoIndex`：**每个 family 首次使用时构建一次**
（冷建），其后按 id/key O(1) 命中；条目按 `mtime_ns+size` 校验，目录成员按 TTL 复核。
本判据分两段：
  - `setUpClass` 预热各 family，稳态调用必须是个位数 open（不许每次全扫）；
  - `test_cold_build_is_one_time` 单独钉住「冷建一次、第二次 O(1)」。
"""
import builtins
import collections
import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import mcp_runtime as mrt  # noqa: E402
from core import repo_index  # noqa: E402

LIGHT = {"spec_list": {}, "registry_search": {"query": "M90"},
         "pattern_read": {"pattern_id": "single-source-truth"},
         "pipeline_read": {"pipeline": "P01"},
         "knowledge_order_read": {"clearance": "public"},
         "library_read": {"entry_id": "NF-1"}}
LIGHT_BUDGET = 8
SCAN = {"pipeline_list": {}, "library_search": {"query": "雨天"},
        "module_read": {"module_id": "M90"}, "asset_read": {"key": "STYLE_DNA"}}
SCAN_BUDGET = 8


def _warm(root):
    idx = repo_index.get(root)
    idx.modules(); idx.pipelines(); idx.assets(); idx.library()
    idx.patterns(); idx.registry(); idx.docs()


def _opens(srv, name, args):
    """一次 `tools/call` 期间打开的文件数（计数与机器快慢无关）。"""
    counts = collections.Counter()
    orig = io.open

    def spy(file, *a, **k):
        try:
            path = os.path.normcase(os.path.abspath(str(file)))
            if ".git" not in path and ".rivet" not in path:
                counts[path] += 1
        except Exception:                    # noqa: BLE001 - 计数失败不影响被测逻辑
            pass
        return orig(file, *a, **k)

    io.open = spy
    builtins.open = spy
    try:
        srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": name, "arguments": args}})
    finally:
        io.open = orig
        builtins.open = orig
    return sum(counts.values())


class McpReadBudgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 预热各 family：本判据测的是**稳态**（每次调用），冷建由下一条判据单独覆盖。
        _warm(Path(__file__).resolve().parents[2])
        cls.srv = mrt.McpRuntime({"mcp": {"name": "budget", "version": "0", "resources": []}})

    def test_light_tools_do_not_scan_the_repo(self):
        for name, args in LIGHT.items():
            got = _opens(self.srv, name, args)
            self.assertLessEqual(
                got, LIGHT_BUDGET,
                "MCP 工具 `%s` 打开了 %d 个文件（>%d）——轻面里混进了全仓扫描？"
                % (name, got, LIGHT_BUDGET))

    def test_scan_tools_stay_within_the_known_ceiling(self):
        for name, args in SCAN.items():
            got = _opens(self.srv, name, args)
            self.assertLessEqual(
                got, SCAN_BUDGET,
                "MCP 工具 `%s` 打开了 %d 个文件（>%d）——扫树面比在册上限更宽了？"
                % (name, got, SCAN_BUDGET))

    def test_repeat_calls_do_not_amplify(self):
        """稳态：连续两次同一调用，第二次的开销不得**放大**（防「每次调用都加一层扫描」）。"""
        first = _opens(self.srv, "registry_search", {"query": "M90"})
        second = _opens(self.srv, "registry_search", {"query": "M90"})
        self.assertLessEqual(second, max(first, 1) * 2)

    def test_cold_build_is_one_time(self):
        """冷建一次后，同一调用第二次必须是 O(1)（不许每次都重建索引）。"""
        root = Path(__file__).resolve().parents[2]
        repo_index.clear(root)
        first = _opens(self.srv, "module_read", {"module_id": "M90"})
        second = _opens(self.srv, "module_read", {"module_id": "M90"})
        self.assertGreater(first, 0, "冷建应读取模块面（否则索引判据空转）")
        self.assertLessEqual(second, 5, "同一工具第二次仍在全量读盘：%d" % second)
        _warm(root)          # 复原预热态，供后续稳态用例

    def test_snapshot_read_does_not_build_repo_index(self):
        srv = mrt.McpRuntime({"mcp": {
            "name": "snapshot-only", "version": "0",
            "resources": [{"uri": "nf://snapshot/one", "name": "one", "text": "payload"}],
        }})
        self.assertIsNone(srv._repo_meta)
        out = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                          "params": {"uri": "nf://snapshot/one"}})
        self.assertEqual("payload", out["result"]["contents"][0]["text"])
        self.assertIsNone(srv._repo_meta, "快照读取不应构建全仓索引")


if __name__ == "__main__":
    unittest.main()
