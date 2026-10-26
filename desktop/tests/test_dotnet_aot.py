"""P5-08 判据：NativeAOT 产物必须**与 Python/规范逐字节等价**，且不依赖 .NET 运行时。

为什么判「等价」而不只判「编出来了」：计划 §20.5 的 P5-08 验收原文是「验收=与 Python 等价」。
AOT 变换（裁剪 + 提前编译 + 内联）最容易悄悄改掉的正是**数字格式化**这类边缘行为，故必须
拿规范向量逐字节对拍，而不是看一眼体积。

本机实测（2026-10-12）：
  - AOT 单文件：engine/dotnet/tools/nf-canonical/dist-aot/nf-canonical.exe 1,478,656 B
  - 裁剪自包含：dist-trim/ 28 件合计约 19 MB
即 AOT ≈ 1/13 体积且无需运行时。产物是忽略面，缺席即 skip（不构建）。
"""
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VECTOR_DIR = ROOT / "protocol" / "generated" / "test_vectors"
AOT_EXE = ROOT / "engine" / "dotnet" / "tools" / "nf-canonical" / "dist-aot" / "nf-canonical.exe"
JIT_DLL = (ROOT / "engine" / "dotnet" / "tools" / "nf-canonical"
           / "bin" / "Release" / "net8.0" / "nf-canonical.dll")
TRIM_DIR = ROOT / "engine" / "dotnet" / "tools" / "nf-canonical" / "dist-trim"
MANIFESTS = ("jcs_conformance.json", "jcs_reject.json")


def _vectors(name):
    import json
    return json.loads((VECTOR_DIR / name).read_text(encoding="utf-8"))["vectors"]


def _minimal_env():
    """只给 SystemRoot（Windows 进程启动的最低要求）——用来证明**不需要** DOTNET_ROOT。"""
    return {"SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows")}


def _dotnet_runtime_usable():
    """→ (是否可用, 理由, 可执行件路径)。

    为什么要探测而不是直接 `subprocess.run(["dotnet", …])`（2026-10-16 实测）：
    某些机器上 PATH 里那个 `dotnet` 是**残缺安装**——命令在、但一跑就回
    「The command could not be loaded」，于是 `--file` 那条 JIT 腿直接
    `FileNotFoundError: [WinError 2]`，把**环境缺口**报成**判据失败**。
    故这里先探一次 `--list-runtimes`：不可用就如实 skip（缺什么写清楚），
    可用就用**解析出的绝对路径**，免得 PATH 抖动又变成间歇红。
    """
    import shutil
    exe = shutil.which("dotnet")
    if not exe:
        return False, "dotnet 不在 PATH（修复指引：装 .NET 运行时或把 dotnet 加入 PATH）", "dotnet"
    try:
        proc = subprocess.run([exe, "--list-runtimes"], capture_output=True,  # nosec B603
                              timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "dotnet 不可用：{}（修复指引：本机 dotnet 可能是残缺安装）".format(exc), exe
    if proc.returncode != 0:
        return False, ("dotnet 自检失败（rc={}）：{}".format(proc.returncode,
                          proc.stderr.decode("utf-8", "replace").strip()[:120])), exe
    return True, "", exe


#: 在模块级**算一次**（decorator 里不重复探测；同一次进程内结论稳定）。
_DOTNET_OK, _DOTNET_WHY, _DOTNET_EXE = _dotnet_runtime_usable()


class ArtifactShapeTest(unittest.TestCase):
    def test_gitignore_keeps_publish_output_out_of_the_repo(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for rel in ("dist-aot/", "dist-trim/"):
            self.assertIn(rel, text, f".gitignore 须忽略 {rel}")

    @unittest.skipUnless(AOT_EXE.is_file() and TRIM_DIR.is_dir(),
                         "AOT/裁剪产物缺席（均为忽略面，需先发布）")
    def test_aot_is_much_smaller_than_trimmed_self_contained(self):
        aot = AOT_EXE.stat().st_size
        trimmed = sum(p.stat().st_size for p in TRIM_DIR.rglob("*") if p.is_file())
        self.assertLess(aot * 5, trimmed, f"AOT {aot} 应远小于裁剪自包含 {trimmed}")


@unittest.skipUnless(AOT_EXE.is_file(), "AOT 产物缺席（忽略面）")
class AotEquivalenceTest(unittest.TestCase):
    def test_aot_matches_spec_on_every_conformance_vector(self):
        checked = 0
        for name in MANIFESTS:
            for v in _vectors(name):
                inp = ROOT / v["input"]
                proc = subprocess.run([str(AOT_EXE), "--file", str(inp)],  # nosec B603
                                      capture_output=True, cwd=str(ROOT), env=_minimal_env())
                if (v.get("expect") or "ok") == "fail":
                    self.assertNotEqual(0, proc.returncode, f"{v['id']} 应被拒")
                    self.assertEqual(b"", proc.stdout.strip(), f"{v['id']} 拒绝时不许有输出")
                else:
                    self.assertEqual(0, proc.returncode, f"{v['id']} 退出码非 0")
                    self.assertEqual(v["expected"].encode("utf-8"), proc.stdout, v["id"])
                checked += 1
        self.assertEqual(14, checked, "两条清单共 14 条向量")

    @unittest.skipUnless(JIT_DLL.is_file(), "JIT 产物缺席")
    @unittest.skipUnless(_DOTNET_OK, _DOTNET_WHY or "dotnet 不可用")
    def test_aot_and_jit_are_byte_identical(self):
        self.assertEqual(AOT_EXE.read_bytes()[:2], b"MZ", "AOT 产物应是原生 PE")
        for v in _vectors("jcs_conformance.json")[:3]:
            inp = ROOT / v["input"]
            aot = subprocess.run([str(AOT_EXE), "--file", str(inp)], capture_output=True,  # nosec B603
                                 cwd=str(ROOT), env=_minimal_env())
            jit = subprocess.run([_DOTNET_EXE, str(JIT_DLL), "--file", str(inp)],  # nosec B603
                                 capture_output=True, cwd=str(ROOT))
            self.assertEqual(jit.returncode, aot.returncode, v["id"])
            self.assertEqual(jit.stdout, aot.stdout, v["id"])


if __name__ == "__main__":
    unittest.main()
