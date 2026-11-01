"""P5-07 绑定层判据：C ABI（ctypes）与 PyO3（扩展模块）两条路径都要**真装载、真调用**。

为什么两条都判：P5-07 的验收是「ABI 符号一致」。只判一条的话，另一条就是「写了没人核的声称」
（本仓 2026-10-03 的原话）。两条的维护成本不同，故都要有可跑判据，晋升门才有得比。

工具链与产物姿态（照 test_rust_fastlane 的既有纪律）：产物缺席即 skip
（engine/rust/**/target 与 dist 都是忽略面，干净克隆里没有）；这里**不构建**。
"""
import ctypes
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import engine_loader as el  # noqa: E402

FFI_LIB = ROOT / "engine" / "rust" / "ffi" / "target" / "release" / "nf_ffi.dll"
PYO3_LIB = ROOT / "engine" / "rust" / "pyo3" / "target" / "release" / "nf_pyengine.dll"
FFI_SRC = ROOT / "engine" / "rust" / "ffi" / "src" / "lib.rs"


class ContractTest(unittest.TestCase):
    """环境无关的一半：符号名与失败语义。"""

    def test_exported_symbol_name_is_the_declared_contract(self):
        # engine_loader.ABI_SYMBOL 是**单一出处**；产出方（Rust）必须导出同名符号，
        # 否则「装载面」与「产出面」各写一份名字，迟早分叉。
        self.assertIn(f"fn {el.ABI_SYMBOL}(", FFI_SRC.read_text(encoding="utf-8"))

    def test_missing_library_is_fail_closed(self):
        self.assertIsNone(el.load(""))
        self.assertIsNone(el.engine_abi(""))
        self.assertIsNone(el.engine_abi(str(ROOT / "no" / "such" / "lib.dll")))

    def test_engine_abi_rejects_a_library_without_the_symbol(self):
        # 平台 C 运行库在场但没有 nf_engine_abi_version ⇒ 必须按「未产出」处理，不假装。
        self.assertIsNone(el.engine_abi(el.c_library()))


@unittest.skipUnless(FFI_LIB.is_file(), "C ABI 产物缺席（target 是忽略面）")
class CAbiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = el.load(str(FFI_LIB))
        assert cls.lib is not None, "自产 cdylib 应能装载"
        cls.lib.nf_reverse_bytes.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                             ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.nf_reverse_bytes.restype = ctypes.c_size_t

    def test_version_symbol_is_readable_through_engine_loader(self):
        self.assertEqual(1, el.engine_abi(str(FFI_LIB)))

    def test_self_test_symbol_returns_the_abi_version(self):
        self.assertEqual(1, int(self.lib.nf_engine_abi_self_test()))

    def test_reverse_round_trip(self):
        buf = ctypes.create_string_buffer(6)
        n = self.lib.nf_reverse_bytes(b"abcdef", 6, buf, 6)
        self.assertEqual(6, n)
        self.assertEqual(b"fedcba", buf.raw[:6])

    def test_invalid_out_buffer_is_refused_by_the_library(self):
        # F1（VULN-02）：非法输出缓冲必须**拒绝**（返回 0），不许用返回值暗示所需长度——
        # 否则调用方会把「一个字节都没写」当成功（静默失败 / CWE-393）。
        small = ctypes.create_string_buffer(2)
        n = self.lib.nf_reverse_bytes(b"abc", 3, small, 2)
        self.assertEqual(0, n, "容量不足必须拒绝（返回 0），不得用返回值暗示所需长度")
        self.assertEqual(b"\x00\x00", small.raw[:2], "拒绝时一个字节都不许写")
        self.assertEqual(0, self.lib.nf_reverse_bytes(b"abc", 3, None, 0), "out 为空必须拒绝")
        self.assertEqual(0, self.lib.nf_reverse_bytes(b"abc", 3, None, 3),
                         "out 为空且 cap 足够也必须拒绝")

    def test_null_input_is_refused_not_crashed(self):
        self.assertEqual(0, self.lib.nf_reverse_bytes(None, 5, None, 0))


@unittest.skipUnless(PYO3_LIB.is_file(), "PyO3 产物缺席（target 是忽略面）")
class PyO3Test(unittest.TestCase):
    def test_extension_module_loads_and_agrees_with_the_c_abi_version(self):
        # Windows 上 .pyd 一旦被装载就无法删除（映射仍在），故容忍清理失败——
        # 那是平台事实，不是判据失败。
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            pyd = Path(tmp) / "nf_pyengine.pyd"
            shutil.copyfile(PYO3_LIB, pyd)
            spec = importlib.util.spec_from_file_location("nf_pyengine", pyd)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        self.assertEqual(el.engine_abi(str(FFI_LIB)) if FFI_LIB.is_file() else 1,
                         mod.abi_version(), "两条绑定路径必须报同一个 ABI 版本")
        self.assertEqual(b"cba", mod.reverse_bytes(b"abc"))
        self.assertEqual(b"", mod.reverse_bytes(b""))


if __name__ == "__main__":
    unittest.main()
