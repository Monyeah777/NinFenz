"""P-C1/P-C3 跨语言实现矩阵的**常驻**判据（三实现真跑同一批契约向量）。

为什么单列一档（与 test_cross_lang_verify 分工）：
  那边判**仲裁规则**与环境无关的形状/棘轮；这边判**真实现的对拍结果**。

工具链与产物姿态（照 test_rust_fastlane 的既有纪律）：
  - Python 侧**总是**跑（本体在本进程内，无外部依赖）；
  - Rust / C# 侧只在**构建产物在场**时跑（engine/rust/canonical/target 与
    engine/dotnet/tools/nf-canonical/bin 都是忽略面，干净克隆里没有）；
  - 这里**不调用 cargo/dotnet build**——常驻面不做构建。产物缺席即 skip（如实，不假装跑过）。

矩阵必须真的看见**三**个独立实现，否则「跨语言」名不副实：三实现齐备时
'MatrixAgreementTest' 断言 verdict=PASS 且每语言每条向量都 PASS（不许有 UNKNOWN 混过去）。
"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "clv_matrix", str(ROOT / "scripts" / "cross_lang_verify.py"))
clv = importlib.util.module_from_spec(_SPEC)
sys.modules["clv_matrix"] = clv
_SPEC.loader.exec_module(clv)

VECTOR_DIR = ROOT / "protocol" / "generated" / "test_vectors"
MANIFESTS = ("jcs_conformance.json", "jcs_reject.json")
CS_DLL = (ROOT / "engine" / "dotnet" / "tools" / "nf-canonical"
          / "bin" / "Release" / "net8.0" / "nf-canonical.dll")


def _rust_bin():
    base = ROOT / "engine" / "rust" / "canonical" / "target" / "release" / "nf-canonical"
    for cand in (base.with_suffix(".exe"), base):
        if cand.is_file():
            return cand
    return None


RUST_BIN = _rust_bin()
DOTNET = clv.toolchains().get("csharp")
CS_READY = CS_DLL.is_file() and DOTNET is not None


def _vectors(name):
    return clv.json_doc.loads((VECTOR_DIR / name).read_text(encoding="utf-8"), dict, what=name)


def _run(argv):
    proc = subprocess.run([str(x) for x in argv], cwd=str(ROOT), capture_output=True)  # nosec B603
    return proc.returncode, proc.stdout


class _ImplCaseMixin:
    """逐向量断言某实现面：正例逐字节等于 expected；负例非零退出且无标准输出。"""

    def run_impl(self, name, argv):  # pragma: no cover - 由子类提供
        raise NotImplementedError

    def check_manifest(self, name, argv_of):
        checked = 0
        for v in _vectors(name)["vectors"]:
            rc, out = self.run_impl(name, argv_of(v["input"]))
            if (v.get("expect") or "ok") == "fail":
                self.assertNotEqual(0, rc, f"{v['id']}：{name} 应被拒")
                self.assertEqual(b"", out.strip(), f"{v['id']}：拒绝时不许有标准输出")
            else:
                self.assertEqual(0, rc, f"{v['id']}：{name} 退出码非 0")
                self.assertEqual(v["expected"].encode("utf-8"), out,
                                 f"{v['id']}：{name} 字节不符")
            checked += 1
        return checked


class PythonJcsSpecTest(unittest.TestCase):
    """Python 侧总是跑（本进程内）；它同时把向量期望值钉在规范实现上。"""

    def test_python_impl_matches_every_vector(self):
        for name in MANIFESTS:
            for v in _vectors(name)["vectors"]:
                text = (ROOT / v["input"]).read_text(encoding="utf-8")
                if (v.get("expect") or "ok") == "fail":
                    with self.assertRaises(ValueError, msg=f"{v['id']} 应被拒"):
                        clv._jcs.canonical_jcs(clv._jcs.loads_strict(text))
                else:
                    got = clv._jcs.canonical_jcs(clv._jcs.loads_strict(text))
                    self.assertEqual(v["expected"].encode("utf-8"), got, v["id"])


@unittest.skipUnless(RUST_BIN is not None, "Rust 侧产物缺席（target 是忽略面）")
class RustJcsBinaryTest(_ImplCaseMixin, unittest.TestCase):
    def run_impl(self, name, argv):
        return _run(argv)

    def test_rust_impl_matches_every_vector(self):
        self.assertEqual(8, self.check_manifest(
            "jcs_conformance.json", lambda inp: [RUST_BIN, "--file", inp]))
        self.assertEqual(6, self.check_manifest(
            "jcs_reject.json", lambda inp: [RUST_BIN, "--file", inp]))


@unittest.skipUnless(CS_READY, "C# 侧产物或 SDK 缺席（bin 是忽略面）")
class CSharpJcsBinaryTest(_ImplCaseMixin, unittest.TestCase):
    def run_impl(self, name, argv):
        return _run(argv)

    def test_csharp_impl_matches_every_vector(self):
        self.assertEqual(8, self.check_manifest(
            "jcs_conformance.json", lambda inp: [DOTNET, str(CS_DLL), "--file", inp]))
        self.assertEqual(6, self.check_manifest(
            "jcs_reject.json", lambda inp: [DOTNET, str(CS_DLL), "--file", inp]))


@unittest.skipUnless(RUST_BIN is not None and CS_READY, "三实现齐备才判「矩阵真跑」")
class MatrixAgreementTest(unittest.TestCase):
    """把清单的命令改写到**在场产物**上再走真对拍器：不构建，只对拍。"""

    @staticmethod
    def _artifact_doc(name):
        doc = _vectors(name)
        for v in doc["vectors"]:
            for lang, spec in (v.get("langs") or {}).items():
                spec.pop("build", None)
                if lang == "rust":
                    spec["cmd"] = [str(RUST_BIN), "--file", v["input"]]
                elif lang == "csharp":
                    spec["cmd"] = [str(DOTNET), str(CS_DLL), "--file", v["input"]]
        return doc

    def test_three_implementations_agree_on_every_vector(self):
        tools = {"python": clv.toolchains().get("python"),
                 "rust": str(RUST_BIN), "csharp": str(DOTNET)}
        self.assertTrue(all(tools.values()), "三实现须齐备（skip 判据已保证）")
        for name in MANIFESTS:
            rep = clv.verify(self._artifact_doc(name), root=str(ROOT), tools=tools)
            self.assertEqual("PASS", rep["verdict"], f"{name}：{rep['vectors']}")
            self.assertEqual("PASS", rep["arbitration"]["outcome"], rep["arbitration"])
            for row in rep["vectors"]:
                for lang, st in sorted(row["langs"].items()):
                    self.assertEqual("PASS", st["status"],
                                     f"{row['id']}/{lang} 不是 PASS：{st}")

    def test_matrix_actually_sees_three_languages(self):
        # 反面自证：若某语言被降级成 probe 或缺席，本判据必须能看出「只有两实现」。
        doc = self._artifact_doc("jcs_basic.json")
        rep = clv.verify(doc, root=str(ROOT),
                         tools={"python": clv.toolchains().get("python"),
                                "rust": None, "csharp": str(DOTNET)})
        statuses = rep["vectors"][0]["langs"]
        self.assertEqual("UNKNOWN", statuses["rust"]["status"])
        self.assertEqual("PASS", statuses["csharp"]["status"])


class ExeSubstitutionTest(unittest.TestCase):
    """声明命令的首元素必须被换成**解析到的**可执行文件（本机 cargo/dotnet 常不在 PATH）。"""

    def test_with_exe_replaces_head_only(self):
        self.assertEqual(["/resolved/cargo", "run", "--release"],
                         clv._with_exe(["cargo", "run", "--release"], "/resolved/cargo"))

    def test_verify_runs_the_resolved_exe(self):
        seen = []
        tools = {"python": "/resolved/python", "rust": None, "csharp": None}

        def runner(cmd, cwd, timeout=120, stdin=None):
            seen.append(cmd[0])
            return 0, b"ok"

        doc = {"schema": "nf-test-vectors/1", "vectors": [
            {"id": "t", "compare_rule": "byte", "expected": "ok",
             "langs": {"python": {"cmd": ["python", "-c", "print('ok')"]}}}]}
        self.assertEqual("PASS", clv.verify(doc, runner=runner, tools=tools)["verdict"])
        self.assertEqual(["/resolved/python"], seen)


def _all_c0_and_quoting_case():
    """→ (输入 JSON 文本, 期望规范化文本)：全 C0 + 引号/反斜杠/斜杠 + DEL。

    RFC 8785 §3.2.2.2 的最小转义只覆盖 `"`、`\\` 与 C0；`/` 与 DEL 必须原样保留。
    短转义（\\b \\t \\n \\f \\r）优先于 \\u00XX 形态。
    """
    src, want = [], []
    for cp in range(0x20):
        short = {0x08: "b", 0x09: "t", 0x0A: "n", 0x0C: "f", 0x0D: "r"}.get(cp)
        if short:
            src.append("\\" + short)
            want.append("\\" + short)
        else:
            src.append(f"\\u{cp:04x}")
            want.append(f"\\u{cp:04x}")
    src.extend(["\\\\", "\\/", '\\"', "\\u007f"])
    want.extend(["\\\\", "/", '\\"', chr(0x7F)])
    return '"' + "".join(src) + '"', '"' + "".join(want) + '"'


def _edge_cases():
    """→ [(id, 输入 JSON 文本, 期望规范化文本)]：矩阵清单受卫生门限制未收录的边界夹具。"""
    c0_src, c0_want = _all_c0_and_quoting_case()
    return (
        ("numbers/ieee754-boundaries",
         "[5e-324,1.7976931348623157e308,2.2250738585072014e-308,"
         "9007199254740993,1e21,1e-7,-0,123456789012345678901234567890]",
         "[5e-324,1.7976931348623157e+308,2.2250738585072014e-308,"
         "9007199254740992,1e+21,1e-7,0,1.2345678901234568e+29]"),
        ("strings/all-c0-and-quoting", c0_src, c0_want),
        ("strings/surrogate-pair-nonascii",
         '"\\ud83d\\ude00\\u4e2d\\u00e9\\u2028\\u007f"',
         '"' + chr(0x1F600) + chr(0x4E2D) + chr(0xE9) + chr(0x2028) + chr(0x7F) + '"'),
        ("keys/utf16-vs-byte-order",
         '{"\\ue000":1,"\\ud83d\\ude00":2,"\\uffff":3,"a":4,"\\u00e9":5}',
         '{"a":4,"' + chr(0xE9) + '":5,"' + chr(0x1F600) + '":2,"'
         + chr(0xE000) + '":1,"' + chr(0xFFFF) + '":3}'),
    )


class EdgeFixtureParityTest(unittest.TestCase):
    """边界夹具的三实现逐字节对拍（补齐矩阵清单因卫生门无法收录的类别）。

    矩阵清单要求 JSON 键只含 ASCII+CJK，故星平面键、全 C0 控制字符只能放**内联夹具**；
    期望值由 RFC 8785 规则导出并在此**写死**（不拿某一实现的输出当真源），再要求
    Python 真源与在场 Rust / C# 产物逐字节相同。产物缺席时仍判 Python 侧（不假装跑过）。
    键序用例同时区分 UTF-16 码元序、UTF-8 字节序与码点序（三者在本例各给一个不同结果）。
    """

    def test_edge_fixtures_are_byte_identical_across_implementations(self):
        for cid, text, want in _edge_cases():
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "input.json"
                path.write_bytes(text.encode("utf-8"))
                truth = clv._jcs.canonical_jcs(clv._jcs.loads_strict(text))
                self.assertEqual(want.encode("utf-8"), truth, f"{cid}：Python 真源偏离规范期望")
                if RUST_BIN is not None:
                    rc, out = _run([RUST_BIN, "--file", str(path)])
                    self.assertEqual(0, rc, f"{cid}：Rust 退出码非 0")
                    self.assertEqual(truth, out, f"{cid}：Rust 字节与 Python 真源不符")
                if CS_READY:
                    rc, out = _run([DOTNET, str(CS_DLL), "--file", str(path)])
                    self.assertEqual(0, rc, f"{cid}：C# 退出码非 0")
                    self.assertEqual(truth, out, f"{cid}：C# 字节与 Python 真源不符")


if __name__ == "__main__":
    unittest.main()
