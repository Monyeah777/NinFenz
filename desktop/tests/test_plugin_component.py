"""P5-03 判据：**类型化组件**形态必须能装载、能校验类型段、能互证结果。

为什么单列一档：CLI 形态的接口是「约定」（argv + 管道），接口对不对只能靠清单里的字符串；
组件形态的接口是 **WIT 类型**，装载期可以直接从二进制的类型段读出来。后者才是 P5-03
「装载时校验」想收紧的那一格——本判据把这件事做成可执行的。

工具链/产物姿态：wasm-tools 与组件产物缺席即 skip（dist/ 是忽略面，这里**不构建**）。
"""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from core import plugin_manifest as pm  # noqa: E402

_HOST = ROOT / "scripts" / "plugin_host.py"
_SPEC = importlib.util.spec_from_file_location("nf_plugin_host_c", str(_HOST))
host = importlib.util.module_from_spec(_SPEC)
sys.modules["nf_plugin_host_c"] = host
_SPEC.loader.exec_module(host)

WIT_SPEC = ROOT / "engine" / "wasm" / "ninfenz-plugin.wit"
WIT_CRATE = ROOT / "engine" / "wasm" / "sha256-component" / "wit" / "ninfenz-plugin.wit"
MANIFEST = ROOT / "engine" / "wasm" / "manifests" / "sha256-component.json"
COMPONENT = (ROOT / "engine" / "wasm" / "sha256-component" / "dist"
             / "nf-plugin-sha256.component.wasm")
WASM_TOOLS = next((p for p in (ROOT.parent / "no",) if False), None)


def _wasm_tools():
    for cand in (Path.home() / ".nftools" / "wasm-tools" / "wasm-tools.exe",
                 Path.home() / ".nftools" / "wasm-tools" / "wasm-tools"):
        if cand.is_file():
            return cand
    return None


WASM_TOOLS = _wasm_tools()


class WitContractTest(unittest.TestCase):
    """接口语义不许在「规范面」与「构建输入」之间漂。"""

    def test_crate_wit_is_byte_identical_to_the_repo_spec(self):
        self.assertEqual(WIT_SPEC.read_bytes(), WIT_CRATE.read_bytes(),
                         "crate 内的 WIT 与仓级规范面分叉了（接口语义会静默漂）")

    def test_exported_method_names_match(self):
        spec = pm.wit_exports(WIT_SPEC.read_text(encoding="utf-8"))
        crate = pm.wit_exports(WIT_CRATE.read_text(encoding="utf-8"))
        self.assertEqual(["sha256"], spec)
        self.assertEqual(spec, crate)


class ManifestShapeTest(unittest.TestCase):
    def test_component_manifest_is_loadable(self):
        doc = pm.load(str(MANIFEST))
        self.assertEqual([], pm.validate(doc), pm.validate(doc))
        self.assertEqual([], pm.validate_against_wit(doc, WIT_SPEC.read_text(encoding="utf-8")))
        self.assertEqual("wasi-preview2-component", doc["abi"])

    def test_component_abi_requires_an_invoke_name(self):
        doc = pm.load(str(MANIFEST))
        doc["methods"][0]["io"] = {"stdin": "bytes"}     # CLI 形状接到组件 ABI 上
        issues = pm.validate(doc)
        self.assertTrue(any("invoke" in i for i in issues), issues)

    def test_cli_abi_still_requires_stdin_or_argv(self):
        doc = pm.load(str(ROOT / "engine" / "wasm" / "manifests" / "sha256.json"))
        doc["methods"][0]["io"] = {"invoke": "x"}        # 组件形状接到 CLI ABI 上
        issues = pm.validate(doc)
        self.assertTrue(any("stdin" in i or "argv" in i for i in issues), issues)


class WaveResultTest(unittest.TestCase):
    """WAVE 结果解析必须 fail-closed（错形态不许当成功）。"""

    def test_parses_ok_list(self):
        self.assertEqual(b"\xba\x78", host.parse_wave_result("ok([186, 120])"))

    def test_parses_empty_list(self):
        self.assertEqual(b"", host.parse_wave_result("ok([])"))

    def test_rejects_err_and_junk(self):
        for bad in ('err("boom")', "ok(1)", "", "ok([1,", "ok([a,b])"):
            self.assertIsNone(host.parse_wave_result(bad), bad)


@unittest.skipUnless(WASM_TOOLS, "wasm-tools 缺席（~/.nftools/wasm-tools）")
class ComponentArtifactTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([str(WASM_TOOLS), *args], capture_output=True, cwd=str(ROOT))  # nosec B603

    @unittest.skipUnless(COMPONENT.is_file(), "组件产物缺席（dist/ 是忽略面）")
    def test_component_has_a_valid_type_section_with_our_signature(self):
        self.assertEqual(0, self._run("validate", str(COMPONENT)).returncode)
        wit = self._run("component", "wit", str(COMPONENT)).stdout.decode("utf-8")
        self.assertIn("export ninfenz:plugin/methods@0.1.0;", wit)
        self.assertIn("sha256: func(data: list<u8>) -> result<list<u8>, string>;", wit)

    def test_a_plain_core_module_is_not_a_component(self):
        # 反面自证：CLI 形态的 .wasm 不该通过组件校验——否则「类型段校验」是空转。
        core = (ROOT / "engine" / "wasm" / "sha256" / "target"
                / "wasm32-wasip1" / "release" / "nf-plugin-sha256.wasm")
        if not core.is_file():
            self.skipTest("CLI 插件产物缺席")
        out = self._run("component", "wit", str(core))
        self.assertNotEqual(0, out.returncode, "核心模块被当成了组件")


@unittest.skipUnless(COMPONENT.is_file(), "组件产物缺席（dist/ 是忽略面）")
class ComponentEquivalenceTest(unittest.TestCase):
    def test_component_matches_hashlib_through_the_typed_abi(self):
        import hashlib
        doc = pm.load(str(MANIFEST))
        artifact = pm.artifact_path(doc, str(ROOT))
        self.assertIsNotNone(artifact)
        self.assertTrue(artifact.is_file())
        for data in (b"", b"abc", b"ninfenz-plugin"):
            got = host.invoke(doc, artifact, "sha256", data)
            self.assertTrue(got["ok"], got["meta"])
            self.assertFalse(got["meta"]["degraded"])
            self.assertEqual("wasi-preview2-component", got["meta"]["abi"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), got["data"])

    def test_component_and_cli_agree_byte_for_byte(self):
        cli_manifest = ROOT / "engine" / "wasm" / "manifests" / "sha256.json"
        doc_c = pm.load(str(MANIFEST))
        doc_cli = pm.load(str(cli_manifest))
        art_c = pm.artifact_path(doc_c, str(ROOT))
        art_cli = pm.artifact_path(doc_cli, str(ROOT))
        if art_cli is None or not art_cli.is_file():
            self.skipTest("CLI 插件产物缺席")
        for data in (b"", b"abc"):
            got_c = host.invoke(doc_c, art_c, "sha256", data)
            got_cli = host.invoke(doc_cli, art_cli, "sha256", data)
            self.assertTrue(got_c["ok"] and got_cli["ok"], (got_c["meta"], got_cli["meta"]))
            self.assertEqual(got_cli["data"], got_c["data"],
                             "两条形态必须给同一摘要（同一实现语义）")


if __name__ == "__main__":
    unittest.main()
