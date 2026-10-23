"""H1（2026-10-22 安全审计）：`nf verify` 执行目标仓库代码前的**信任门**。

判据面：
- origin owner 解析（GitHub 形态；解析不出/无 origin ⇒ 不可信，fail-closed）；
- 允许列表（默认含本仓作者；`NF_TRUST_OWNERS` 可追加）；
- `--trust-repo` / `NF_TRUST_REPO=1` 显式放行；
- 引擎 inproc 面拒绝不可信仓库（如实 FAIL，不执行代码）；
- `gate_inproc` 纵深防御：直接调用 exec 入口也拒绝，且**没有产生任何执行副作用**。
"""
import os
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from core import gate_engine, gate_inproc, gate_labels, repo_trust  # noqa: E402


def _load_nf():
    """按路径加载 CLI；裸 `import nf` 在分片进程里会撞同名包/缓存。"""
    spec = importlib.util.spec_from_file_location("nfcli_repo_trust", ROOT / "scripts" / "nf.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _repo(origin: str = "") -> Path:
    """临时 git 仓库（可带 origin）；调用方负责清理（TemporaryDirectory）。"""
    d = tempfile.mkdtemp(prefix="nf_trust_")
    subprocess.run(["git", "init", "-q", str(d)], check=True, capture_output=True)
    if origin:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", origin],
                       check=True, capture_output=True)
    return Path(d)


class _Base(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k) for k in (repo_trust.ENV_TRUST, repo_trust.ENV_OWNERS)}
        os.environ.pop(repo_trust.ENV_TRUST, None)
        os.environ.pop(repo_trust.ENV_OWNERS, None)
        self.addCleanup(self._restore)

    def _restore(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _tmp_repo(self, origin: str = "") -> Path:
        d = _repo(origin)
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return d


class OriginParseTest(_Base):
    def test_parses_github_url_forms(self):
        cases = {
            "https://github.com/Monyeah777/NinFenz.git": "Monyeah777",
            "https://github.com/Monyeah777/NinFenz": "Monyeah777",
            "git@github.com:Monyeah777/NinFenz.git": "Monyeah777",
            "ssh://git@github.com/Monyeah777/NinFenz": "Monyeah777",
        }
        for url, owner in cases.items():
            with self.subTest(url=url):
                self.assertEqual(owner, repo_trust.origin_owner(str(self._tmp_repo(url))))

    def test_unparseable_or_absent_origin_is_untrusted(self):
        for origin in ("", "https://gitlab.com/evil/repo.git", "/local/path/repo",
                       "https://github.com/evil/repo.git"):
            with self.subTest(origin=origin):
                d = self._tmp_repo(origin)
                ok, why = repo_trust.trust_status(str(d))
                self.assertFalse(ok, why)

    def test_allowlisted_owner_is_trusted(self):
        d = self._tmp_repo("git@github.com:Monyeah777/NinFenz.git")
        ok, why = repo_trust.trust_status(str(d))
        self.assertTrue(ok, why)
        self.assertIn("Monyeah777", why)

    def test_non_git_dir_is_untrusted(self):
        with tempfile.TemporaryDirectory() as d:
            ok, _why = repo_trust.trust_status(d)
            self.assertFalse(ok, "非 git 检出必须不可信（无法证明来源）")

    def test_env_trust_and_owner_extension(self):
        d = self._tmp_repo("https://github.com/evil/repo.git")
        os.environ[repo_trust.ENV_TRUST] = "1"
        self.assertTrue(repo_trust.trust_status(str(d))[0], "--trust-repo 等价开关应放行")
        os.environ.pop(repo_trust.ENV_TRUST, None)
        os.environ[repo_trust.ENV_OWNERS] = "someoneelse, evil"
        self.assertTrue(repo_trust.trust_status(str(d))[0], "NF_TRUST_OWNERS 可追加允许 owner")


class GateRefusalTest(_Base):
    def test_gate_inproc_refuses_and_does_not_execute(self):
        evil = self._tmp_repo("https://github.com/evil/repo.git")
        marker = evil / "pwned.txt"
        src = f"open({str(marker)!r}, 'w').write('executed')"
        with self.assertRaises(repo_trust.UntrustedRepoError):
            gate_inproc.run_inproc(src, evil, "checkX")
        self.assertFalse(marker.exists(), "被拒时不得执行目标仓库代码（无副作用）")

    def test_gate_inproc_executes_for_trusted_repo(self):
        good = self._tmp_repo("https://github.com/Monyeah777/NinFenz.git")
        code, _out = gate_inproc.run_inproc("x = 1", good, "checkX")
        self.assertEqual(0, code)

    def test_gate_inproc_executes_with_explicit_trust(self):
        evil = self._tmp_repo("https://github.com/evil/repo.git")
        os.environ[repo_trust.ENV_TRUST] = "1"
        code, _out = gate_inproc.run_inproc("x = 1", evil, "checkX")
        self.assertEqual(0, code)

    def test_gate_engine_inproc_verdict_refuses(self):
        evil = self._tmp_repo("https://github.com/evil/repo.git")
        labels = gate_labels.parse_labels(
            (ROOT / "verify.sh").read_text(encoding="utf-8"), 39)
        v = gate_engine._inproc(39, "== [39/x] test ==", labels)(evil)
        self.assertEqual(gate_engine.FAIL, v.status)
        text = " ".join(m for _s, m in v.verdicts)
        self.assertIn("拒绝", text)
        self.assertIn("--trust-repo", text, "拒绝文案必须给修复指引")

    def test_cli_verify_preflight_refuses_untrusted_repo(self):
        """`nf verify` 在**执行前**拒绝（rc=2 + 风险文案），而不是跑完再报失败。"""
        evil = self._tmp_repo("https://github.com/evil/repo.git")
        nf = _load_nf()

        args = Namespace(only="", json=False, memo=False, cached=False, jobs=0,
                         trust_repo=False)
        with mock.patch.object(gate_engine, "ROOT", evil):
            rc = nf._cmd_verify(args)
        self.assertEqual(2, rc)

    def test_cli_verify_preflight_allows_with_trust_repo(self):
        """`--trust-repo` 放行：走完预检（后续执行用 mock 收口，避免真跑全量引擎）。"""
        evil = self._tmp_repo("https://github.com/evil/repo.git")
        nf = _load_nf()

        args = Namespace(only="", json=True, memo=False, cached=False, jobs=0,
                         trust_repo=True)
        with (mock.patch.object(gate_engine, "ROOT", evil),
              mock.patch.object(gate_engine, "build_registry"),
              mock.patch.object(gate_engine, "run_checks", return_value=[])):
            rc = nf._cmd_verify(args)
        self.assertEqual(0, rc, "显式信任后应放行（本轮 run_checks 已 mock）")


if __name__ == "__main__":
    unittest.main()
