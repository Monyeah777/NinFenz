#!/usr/bin/env python3
"""Python 发行包（T9.1）判据：元数据真源一致 / wheel 构建产物断言 / 篡改与禁入面。

分两层：
1. **源码层**（不构建）：pyproject ↔ facts.json ↔ scripts/nf.py ↔ ninfenz.__version__ 的
   name/version/license/requires-python/entry_point 必须一致；
2. **产物层**（真构建一次 wheel，离线、无网络）：`scripts/check_pypi_package.py` 全判据通过，
   并额外验证「解包后 `python -m ninfenz --version` 可跑」与「注入面逐字节 == 仓库根」。
另加负例：篡改/缺失/禁入面必须让校验器变红（防校验器空转）。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packaging" / "pypi"))       # `ninfenz` 包源码（元数据只读）

import importlib.util  # noqa: E402

import ninfenz  # noqa: E402


def _load_checker():
    path = ROOT / "scripts" / "check_pypi_package.py"
    spec = importlib.util.spec_from_file_location("nf_check_pypi", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


CK = _load_checker()


def _facts():
    return json.loads((ROOT / "protocol" / "facts.json").read_text(encoding="utf-8"))


def _pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _nf_cli_version() -> str:
    text = (ROOT / "scripts" / "nf.py").read_text(encoding="utf-8")
    m = re.search(r'^NF_CLI_VERSION = "([^"]+)"', text, re.M)
    assert m, "scripts/nf.py 里找不到 NF_CLI_VERSION"
    return m.group(1)


_BUILD = {"dir": None, "wheel": None, "error": None}


def _build_wheel() -> Path:
    """离线构建一次（模块级缓存）。--no-build-isolation + --no-cache-dir：不联网、不写用户缓存。"""
    if _BUILD["wheel"] is not None:
        return Path(_BUILD["wheel"])
    if _BUILD["error"] is not None:
        raise AssertionError(_BUILD["error"])
    out = Path(tempfile.mkdtemp(prefix="nf-wheel-build-"))
    cmd = [sys.executable, "-m", "pip", "wheel", str(ROOT), "--no-deps",
           "--no-build-isolation", "--no-cache-dir", "-w", str(out)]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600, env=env)
    wheels = sorted(out.glob("*.whl"))
    if proc.returncode != 0 or not wheels:
        _BUILD["error"] = ("离线构建 wheel 失败（rc=%s）：%s"
                           % (proc.returncode, (proc.stderr or proc.stdout)[-800:]))
        raise AssertionError(_BUILD["error"])
    _BUILD["dir"] = str(out)
    _BUILD["wheel"] = str(wheels[0])
    return Path(_BUILD["wheel"])


class MetadataSourceTest(unittest.TestCase):
    """源码层：发行包元数据必须与仓库单一真源一致（不需要构建）。"""

    def test_version_chain(self):
        facts = _facts()
        ver = facts["release"]["cli_version"]
        self.assertEqual(_nf_cli_version(), ver, "nf.py NF_CLI_VERSION ≠ facts")
        self.assertEqual(_pyproject()["project"]["version"], ver,
                         "pyproject [project].version ≠ facts")
        self.assertEqual(ninfenz.__version__, ver, "ninfenz.__version__ ≠ facts")

    def test_project_fields(self):
        proj = _pyproject()["project"]
        self.assertEqual(proj["name"], "ninfenz")
        self.assertEqual(proj["requires-python"], ">=3.11")
        self.assertEqual(proj["scripts"]["nf"], "ninfenz._launcher:main")
        self.assertEqual(proj["dependencies"], [])          # 本体零硬依赖
        lic = str(proj.get("license") or "")
        if isinstance(proj.get("license"), dict):           # 兼容旧式 {text=...}
            lic = str((proj["license"] or {}).get("text") or "")
        self.assertIn("AGPL-3.0-only", lic, "license 未声明 AGPL-3.0-only")
        self.assertIn("LicenseRef-Commercial", lic, "license 未声明商业替代许可")
        self.assertNotIn("MIT", lic.upper(), "license 仍写 MIT（当前许可不是 MIT）")
        self.assertFalse([c for c in proj.get("classifiers") or [] if "MIT License" in c],
                         "classifiers 仍声明 MIT License（与分层许可冲突）")

    def test_build_system(self):
        bs = _pyproject()["build-system"]
        self.assertEqual(bs["build-backend"], "setuptools.build_meta")
        self.assertTrue(any(r.startswith("setuptools") for r in bs["requires"]),
                        "build-system 未声明 setuptools（离线构建需要 --no-build-isolation）")

    def test_expected_payload_matches_tree(self):
        payload = CK.expected_payload(str(ROOT))
        self.assertIn("ninfenz/scripts/nf.py", payload)
        self.assertIn("ninfenz/protocol/facts.json", payload)
        self.assertIn("ninfenz/desktop/src/core/__init__.py", payload)
        schemas = [p for p in payload if "/protocol/schema/" in p]
        self.assertGreaterEqual(len(schemas), 8, "schema 注入面过小：%s" % schemas[:3])
        for whl_path, src in payload.items():
            self.assertTrue(Path(src).is_file(), "注入面源文件不存在：%s" % src)
            self.assertNotIn("__pycache__", whl_path)


class WheelBuildTest(unittest.TestCase):
    """产物层：真构建一次 wheel，跑全判据 + 运行入口。"""

    @classmethod
    def setUpClass(cls):
        cls.wheel = _build_wheel()

    def test_checker_passes_on_fresh_wheel(self):
        issues, stats = CK.inspect_wheel(str(self.wheel), str(ROOT))
        self.assertEqual([], issues, issues[:8])
        self.assertEqual(stats["name"], "ninfenz")
        self.assertEqual(stats["version"], _facts()["release"]["cli_version"])
        self.assertEqual(stats["payload_missing"], 0)
        self.assertEqual(stats["payload_extra"], 0)
        self.assertEqual(stats["payload_mismatch"], 0)
        self.assertEqual(stats["forbidden"], 0)
        self.assertGreater(stats["payload_files"], 250, "注入面文件数异常：%s"
                           % stats["payload_files"])
        self.assertGreater(stats["wheel_bytes"], 200_000, "wheel 过小，疑似漏注入")
        self.assertLess(stats["wheel_bytes"], 20_000_000, "wheel 过大，疑似把整棵仓库打进包")
        self.assertTrue(any("AGPL-3.0-only.txt" in p for p in stats["license_files"]),
                        "wheel 未带 AGPL 许可文本")

    def test_wheel_runs_standalone(self):
        """解包后 `python -m ninfenz --version` 必须可跑（证明 console 入口树自洽）。"""
        tmp = Path(tempfile.mkdtemp(prefix="nf-wheel-run-"))
        try:
            with zipfile.ZipFile(self.wheel) as zf:
                zf.extractall(tmp)
            env = dict(os.environ, PYTHONPATH=str(tmp), PYTHONUTF8="1",
                       PYTHONIOENCODING="utf-8")
            proc = subprocess.run([sys.executable, "-m", "ninfenz", "--version"],
                                  cwd=str(tmp), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=120, env=env)
            self.assertEqual(0, proc.returncode, proc.stderr[-800:])
            self.assertEqual("nf %s" % _facts()["release"]["cli_version"],
                             proc.stdout.strip())
            # `--help` 也要能建出命令面（证明 bundled core 可导入，不只是版本短路）
            proc2 = subprocess.run([sys.executable, "-m", "ninfenz", "--help"],
                                   cwd=str(tmp), capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=120, env=env)
            self.assertEqual(0, proc2.returncode, proc2.stderr[-800:])
            self.assertIn("usage: nf", proc2.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class WheelMutationTest(unittest.TestCase):
    """负例：篡改/缺失/禁入面必须被抓（防校验器空转）。"""

    @classmethod
    def setUpClass(cls):
        cls.wheel = _build_wheel()

    def _mutated(self, mutate) -> str:
        """把真 wheel 复制并套用 mutate({name: bytes}) → 返回新 wheel 路径。"""
        tmp = Path(tempfile.mkdtemp(prefix="nf-wheel-mut-"))
        dst = tmp / "ninfenz-mut-py3-none-any.whl"
        with zipfile.ZipFile(self.wheel) as src, zipfile.ZipFile(dst, "w") as out:
            data = {n: src.read(n) for n in src.namelist() if not n.endswith("/")}
            mutate(data)
            for name, blob in data.items():
                out.writestr(name, blob)
        return str(dst)

    def _issues(self, mutate):
        wheel = self._mutated(mutate)
        try:
            issues, _ = CK.inspect_wheel(wheel, str(ROOT))
        finally:
            shutil.rmtree(Path(wheel).parent, ignore_errors=True)
        return issues

    def test_missing_core_file_is_caught(self):
        issues = self._issues(lambda d: d.pop("ninfenz/desktop/src/core/__init__.py"))
        self.assertTrue(any("缺必需件：ninfenz/desktop/src/core/__init__.py" in i
                            for i in issues), issues)

    def test_payload_drift_is_caught(self):
        def mutate(d):
            name = "ninfenz/scripts/nf.py"
            d[name] = d[name] + b"\n# tampered by test\n"
        issues = self._issues(mutate)
        self.assertTrue(any("与仓库根原件不一致" in i and "scripts/nf.py" in i
                            for i in issues), issues)

    def test_forbidden_cache_is_caught(self):
        issues = self._issues(lambda d: d.__setitem__(
            "ninfenz/desktop/src/core/__pycache__/x.pyc", b"pyc"))
        self.assertTrue(any("禁入面文件" in i for i in issues), issues)

    def test_metadata_version_mismatch_is_caught(self):
        def mutate(d):
            di = [n for n in d if n.endswith(".dist-info/METADATA")][0]
            d[di] = d[di].replace(b"Version: 1.1.0", b"Version: 9.9.9")
        issues = self._issues(mutate)
        self.assertTrue(any("元数据 Version" in i for i in issues), issues)

    def test_missing_entry_point_is_caught(self):
        def mutate(d):
            ep = [n for n in d if n.endswith(".dist-info/entry_points.txt")][0]
            d.pop(ep)
        issues = self._issues(mutate)
        self.assertTrue(any("entry_points" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
