#!/usr/bin/env python3
"""工作流工业级加固判据（`core/workflow_hardening.py`）回归测试。

本件守的是 **CI 运行面**五条：并发分组 / 凭据最小化 / 依赖缓存 / CODEOWNERS / dependabot 生态。
每条都带**变异必红**用例——判据写了却从没红过，等于没有判据。
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import workflow_hardening as wh  # noqa: E402

SHA = "1" * 40
CHECKOUT = (f"  - uses: actions/checkout@{SHA}  # v4\n"
            "    with:\n      persist-credentials: false\n")
CONC = "concurrency:\n  group: ci-${ github.ref }\n  cancel-in-progress: true\n"
GOOD = ("name: ok\npermissions:\n  contents: read\n" + CONC
        + "jobs:\n  build:\n    runs-on: ubuntu-latest\n    timeout-minutes: 10\n"
        + "    steps:\n" + CHECKOUT)
WRITER = ("name: w\npermissions:\n  contents: write\n"
          "concurrency:\n  group: library-write\n  cancel-in-progress: false\n"
          "jobs:\n  j:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    steps:\n"
          f"      - uses: actions/checkout@{SHA}  # v4\n"
          "      - run: git push origin HEAD:main\n")


def _wf(tmp: str, name: str, body: str) -> None:
    d = Path(tmp) / wh.WORKFLOWS_REL
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def _gov(tmp: str, eco=("github-actions",)) -> None:
    d = Path(tmp) / ".github"
    d.mkdir(parents=True, exist_ok=True)
    (d / "CODEOWNERS").write_text("* @owner\n", encoding="utf-8")
    (d / "dependabot.yml").write_text(
        "version: 2\nupdates:\n"
        + "".join(f"  - package-ecosystem: {e}\n    directory: /\n" for e in eco),
        encoding="utf-8")


class WorkflowHardeningTest(unittest.TestCase):
    def test_repo_is_hardened(self):
        issues, stats = wh.scan(str(ROOT))
        self.assertEqual([], issues, issues)
        self.assertGreaterEqual(stats["workflows"], 10)
        self.assertEqual(stats["workflows"], stats["with_concurrency"],
                         "每个工作流都须显式 concurrency")
        self.assertGreaterEqual(stats["writer_workflows"], 1)
        self.assertTrue(stats["writers_share_group"], "写入型须共享同一并发组")
        for eco in ("github-actions", "pip", "npm"):
            self.assertIn(eco, stats["dependabot_ecosystems"])

    def test_missing_concurrency_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _wf(tmp, "noconc.yml", GOOD.replace(CONC, ""))
            _gov(tmp)
            issues, _st = wh.scan(tmp)
        self.assertTrue(any("缺 concurrency" in i for i in issues), issues)

    def test_writer_must_not_cancel_and_must_share_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            _wf(tmp, "w.yml", WRITER.replace("cancel-in-progress: false",
                                             "cancel-in-progress: true"))
            _gov(tmp)
            issues, _st = wh.scan(tmp)
            self.assertTrue(
                any("写入型" in i and "cancel-in-progress" in i for i in issues), issues)
        with tempfile.TemporaryDirectory() as tmp2:
            _wf(tmp2, "w1.yml", WRITER)
            _wf(tmp2, "w2.yml", WRITER.replace("library-write", "other-write"))
            _gov(tmp2)
            issues2, _st2 = wh.scan(tmp2)
        self.assertTrue(any("未共享同一并发组" in i for i in issues2), issues2)

    def test_credential_persistence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _wf(tmp, "leak.yml", GOOD.replace("    with:\n      persist-credentials: false\n", ""))
            _gov(tmp)
            issues, _st = wh.scan(tmp)
        self.assertTrue(any("凭据持久化" in i for i in issues), issues)
        with tempfile.TemporaryDirectory() as tmp2:
            _wf(tmp2, "writer.yml", WRITER)
            _gov(tmp2)
            issues2, _st2 = wh.scan(tmp2)
        self.assertFalse(any("凭据持久化" in i for i in issues2),
                         f"写入型保留凭据是必需的：{issues2}")

    def test_pip_cache_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            _wf(tmp, "nocache.yml", GOOD.replace(
                "    steps:\n", "    steps:\n      - run: pip install -r req.txt\n"))
            _gov(tmp)
            issues, _st = wh.scan(tmp)
        self.assertTrue(any("依赖缓存" in i for i in issues), issues)

    def test_codeowners_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            _wf(tmp, "ok.yml", GOOD)
            _gov(tmp)
            (Path(tmp) / ".github" / "CODEOWNERS").unlink()
            issues, _st = wh.scan(tmp)
        self.assertTrue(any("CODEOWNERS" in i for i in issues), issues)

    def test_dependabot_must_cover_real_ecosystems(self):
        with tempfile.TemporaryDirectory() as tmp:
            _wf(tmp, "ok.yml", GOOD)
            _gov(tmp)
            (Path(tmp) / "packaging" / "npm").mkdir(parents=True, exist_ok=True)
            (Path(tmp) / "packaging" / "npm" / "package.json").write_text("{}", encoding="utf-8")
            issues, _st = wh.scan(tmp)
        self.assertTrue(any("未覆盖仓库真实生态" in i and "npm" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
