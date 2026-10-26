"""P5-02/P5-04/P5-05/P5-06 宿主判据：真插件在真沙箱里跑，且失败路径真能回退。

工具链/产物姿态（照 test_rust_fastlane 的既有纪律）：wasmtime 或 .wasm 产物不在场即 skip
（都是忽略面：target/ 不入仓）。这里**不构建**——构建由 .rivet 的内部脚本与开发机仪器负责。

判据分三组：
  1) 直通：插件输出与 Python 参考（hashlib）**逐字节相等**；
  2) 隔离：宿主 argv 显式 deny（无 --dir、无 inherit-network、无 inherit-env）；
     且**燃料耗尽真的会触发**，并被识别成语义原因 + 回退（不是静默或裸崩溃）；
  3) 回退：宿主/产物缺席、方法未声明 → 一律回退并标记 degraded，宿主自身不抛。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from core import plugin_manifest as pm  # noqa: E402

_HOST_PATH = ROOT / "scripts" / "plugin_host.py"
_spec = importlib.util.spec_from_file_location("nf_plugin_host", str(_HOST_PATH))
host = importlib.util.module_from_spec(_spec)
sys.modules["nf_plugin_host"] = host
_spec.loader.exec_module(host)

WASMTIME = host.resolve_wasmtime()
DOC, ISSUES, ARTIFACT = host.load_declared(root=ROOT)
ARTIFACT_READY = bool(ARTIFACT) and Path(ARTIFACT).is_file()
WIT_READY = not [i for i in ISSUES if "WIT" in i]


class LoadTest(unittest.TestCase):
    # 2026-10-22：本文件头写明「wasmtime 或 .wasm 产物不在场即 skip（target/ 是忽略面，
    # 这里不构建）」——但这两条断言装载无 issue，而产物缺席本身就会进 ISSUES，CI 必红。
    # 按同一姿态补 skip 守卫：产物在场时断言照旧全跑，不删断言、不降判据。
    @unittest.skipUnless(ARTIFACT_READY, "插件产物缺席（target/ 是忽略面）")
    def test_declared_manifest_is_loadable_without_issues(self):
        self.assertEqual([], ISSUES, "自带清单+WIT 不该有装载问题")

    def test_wit_contract_is_checked_at_load_time(self):
        self.assertTrue(WIT_READY)
        bad = dict(DOC)
        bad["methods"] = [dict(DOC["methods"][0], name="nope")]
        wit_text = (ROOT / host.WIT_REL).read_text(encoding="utf-8")
        self.assertTrue(pm.validate_against_wit(bad, wit_text))


class IsolationTest(unittest.TestCase):
    """能力收窄是**显式 deny**，不靠默认值——argv 即可机检。"""

    def test_argv_denies_capabilities_explicitly(self):
        argv = host.isolation_argv("wasmtime", Path("x.wasm"), 1000, 5000)
        joined = " ".join(argv)
        for forbidden in ("--dir", "inherit-network", "inherit-env=y", "tcplisten"):
            self.assertNotIn(forbidden, joined, f"宿主 argv 出现越权开关：{forbidden}")
        for required in ("fuel=1000", "timeout=5000ms", "inherit-env=n", "epoch-interruption=y"):
            self.assertIn(required, joined)

    def test_fuel_budget_scales_with_linear_cost(self):
        entry = pm.method(DOC, "sha256")
        small = host.fuel_for(entry, 1024)
        big = host.fuel_for(entry, 4 * 1024 * 1024)
        self.assertLess(small, big, "线性成本必须随输入伸缩，否则预算=隐式输入上限")
        # 上限兜底：再大也不越过 hard_cap
        self.assertLessEqual(host.fuel_for(entry, 1 << 40),
                             entry["fuel"]["hard_cap"])

    def test_granted_capabilities_are_all_denied(self):
        granted = pm.granted_capabilities(DOC)
        self.assertEqual([], granted["fs"])
        self.assertEqual([], granted["net"])
        self.assertEqual("deny", granted["clocks"])
        self.assertEqual("deny", granted["random"])


@unittest.skipUnless(WASMTIME and ARTIFACT_READY, "wasmtime 或插件产物缺席（target/ 是忽略面）")
class RealPluginTest(unittest.TestCase):
    def test_plugin_matches_python_reference_byte_for_byte(self):
        import hashlib
        for data in (b"", b"abc", b"ninfenz" * 1000):
            got = host.invoke(DOC, ARTIFACT, "sha256", data, wasmtime=WASMTIME)
            self.assertTrue(got["ok"], got["meta"])
            self.assertFalse(got["meta"]["degraded"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), got["data"])

    def test_fuel_exhaustion_is_detected_and_falls_back(self):
        # 用极小燃料强制耗尽：这是 P5-05 的失败路径，必须**被识别**并回退，不许静默。
        tiny = {"methods": [dict(DOC["methods"][0],
                                 fuel={"base": 1000, "per_kib": 1, "hard_cap": 1000})]}
        got = host.invoke_with_fallback(tiny, ARTIFACT, "sha256", b"x" * 4096, wasmtime=WASMTIME)
        self.assertTrue(got["ok"])
        self.assertTrue(got["meta"]["degraded"], got["meta"])
        self.assertEqual("fuel_exhausted", got["meta"]["reason"], got["meta"])
        self.assertEqual("scripts/plugin_reference.py", got["meta"]["fallback"])
        import hashlib
        self.assertEqual(hashlib.sha256(b"x" * 4096).hexdigest(), got["data"])


class FallbackTest(unittest.TestCase):
    """宿主自身不死：任何缺席都收敛成退化返回值。"""

    def test_absent_host_falls_back_and_is_marked(self):
        got = host.invoke_with_fallback(DOC, ARTIFACT, "sha256", b"abc", wasmtime=None)
        self.assertTrue(got["ok"])
        self.assertTrue(got["meta"]["degraded"])
        self.assertEqual("host_absent", got["meta"]["reason"])

    def test_absent_artifact_falls_back(self):
        got = host.invoke_with_fallback(DOC, None, "sha256", b"abc", wasmtime=WASMTIME or "wt")
        self.assertTrue(got["ok"])
        self.assertEqual("artifact_absent", got["meta"]["reason"])

    def test_undeclared_method_does_not_fallback(self):
        got = host.invoke_with_fallback(DOC, ARTIFACT, "md5", b"abc", wasmtime=WASMTIME or "wt")
        self.assertFalse(got["ok"])
        self.assertEqual("method_not_declared", got["meta"]["reason"])

    def test_oversized_input_is_refused_before_spawning_host(self):
        data = b"x" * (host.MAX_PLUGIN_INPUT_BYTES + 1)
        got = host.invoke(DOC, ARTIFACT, "sha256", data, wasmtime="never-spawn")
        self.assertFalse(got["ok"])
        self.assertEqual("input_too_large", got["meta"]["reason"])

    def test_subprocess_output_is_capped_and_drained(self):
        rc, out, err, timed_out, overflow = host._run_bounded(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000)"],
            cwd=str(ROOT), input_data=None, timeout_s=5, output_cap=64)
        self.assertTrue(overflow)
        self.assertFalse(timed_out)
        self.assertLessEqual(len(out) + len(err), 64)
        self.assertNotEqual(0, rc)

    def test_component_argv_has_a_command_line_budget(self):
        entry = {"io": {"invoke": "sha256"}}
        with self.assertRaises(ValueError):
            host.component_argv("wasmtime", Path("x.wasm"), entry,
                                b"\xff" * (host.MAX_COMPONENT_INPUT_BYTES + 1),
                                host.MAX_PLUGIN_OUTPUT_BYTES, 1000)

    @unittest.skipUnless(ARTIFACT_READY, "插件产物缺席（target/ 是忽略面）")
    def test_host_self_test_passes(self):
        self.assertEqual(0, host._self_test())


if __name__ == "__main__":
    unittest.main()
