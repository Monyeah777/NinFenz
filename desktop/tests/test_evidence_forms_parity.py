"""证据面双实现 parity 收口：receipts / attest 两形态 + 仓外单文件复验。

判据：`core.evidence.verify_any` 与 `scripts/nf_verify.py`（零依赖单文件）对**同一输入**
必须给出同一判定。两套实现相互独立，结论不一致即至少一边有 bug——那时「第三方复验」
的结论不可信，所以这是硬门，不是风格检查。

本文件补 M2-T8 的三处缺口（既有 test_evidence.py 的 TestStandaloneParity 只断言了
bundle 形态与 receipts/attest 的 verdict，未覆盖 level/root，也未证明「仓外单文件」）：

1) receipts 形态（nf-receipts/1 + --root）：verdict / level / root 三项同判；
2) attest 形态（nf-attest-set/1 + hmac）：带 key 时 verdict / level 同判，
   缺 key 时两边都必须 fail-closed 判 invalid（不许一边静默降级成 digest_only）；
3) 仓外单文件：把 nf_verify.py 拷到仓外临时目录、cwd 也在那里（再用 -I 隔离模式跑一遍），
   判定必须与 core 一致——证明「不装仓库也能验」不是靠仓库路径/周边模块。

确定性：bundle 用 created_at="2026-01-01T00:00:00Z"；信封 issued_at 用
SOURCE_DATE_EPOCH 钉在同一时刻；不联网、不写仓库、只用标准库。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import attest, evidence, receipts  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf_verify.py"
#: 固定签发时刻：同输入可重放（不靠墙钟）
PIN = "2026-01-01T00:00:00Z"
PIN_EPOCH = "1767225600"          # 2026-01-01T00:00:00Z
KEY = b"0123456789abcdef0123456789abcdef"


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_forms_parity_")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "a.md").write_text("# A\n\n正文甲\n", encoding="utf-8")
        (self.tmp / "docs" / "b.md").write_text("# B\n\n正文乙\n", encoding="utf-8")
        self.key = KEY
        self.key_file = self.tmp / "key.bin"
        self.key_file.write_bytes(self.key)

    def _standalone(self, *args, **kw):
        """跑零依赖验证器 → (returncode, 解析出的 JSON 或 None, stderr)。"""
        argv = [sys.executable, str(SCRIPT), *args]
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", **kw)
        try:
            doc = json.loads(proc.stdout)
        except ValueError:
            doc = None
        return proc.returncode, doc, proc.stderr

    def _assert_fields_agree(self, core, standalone, fields, where):
        self.assertIsNotNone(standalone, f"{where}：独立验证器没给出可解析结论")
        for field in fields:
            self.assertEqual(core.get(field), standalone.get(field),
                             f"{where}：字段 {field} 双实现不一致"
                             f"（core={core.get(field)!r} standalone={standalone.get(field)!r}）")


class TestReceiptsFormParity(_Base):
    """receipts 形态：单根 + 每条包含证明，成员从 --root 目录取。"""

    def _write_receipts(self):
        doc = receipts.build_scope(str(self.tmp), ["docs/a.md", "docs/b.md"],
                                   scope="evidence")
        self.assertEqual(receipts.SCHEMA, doc["schema"])
        path = self.tmp / "RECEIPTS.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return doc, path

    def _standalone_receipts(self, path):
        return self._standalone("--evidence", str(path), "--root", str(self.tmp),
                                "--kind", "receipts", "--json")

    def test_receipts_form_verdict_level_root_agree(self):
        doc, path = self._write_receipts()
        core = evidence.verify_any(str(path), root=str(self.tmp))
        rc, standalone, err = self._standalone_receipts(path)
        self.assertEqual(0, rc, err[-300:])
        self.assertEqual("ok", core["verdict"], core["issues"])
        self.assertEqual("receipts_only", core["level"])
        self.assertEqual(doc["root"], core["root"])
        self.assertEqual(len(doc["entries"]), core["count"])
        self._assert_fields_agree(core, standalone, ("verdict", "level", "root"),
                                  "receipts 形态 ok")

        # 篡改成员实体：两边都必须判 invalid（且 level/root 仍同口径）
        (self.tmp / "docs" / "a.md").write_text("# A\n\n正文被改\n", encoding="utf-8")
        core_bad = evidence.verify_any(str(path), root=str(self.tmp))
        rc_bad, standalone_bad, err_bad = self._standalone_receipts(path)
        self.assertEqual(1, rc_bad, err_bad[-300:])
        self.assertEqual("invalid", core_bad["verdict"])
        self._assert_fields_agree(core_bad, standalone_bad, ("verdict", "level", "root"),
                                  "receipts 形态篡改")


class TestAttestFormParity(_Base):
    """attest 形态：nf-attest-set/1 信封集 + hmac 签名（缺 key 一律拒绝）。"""

    def _write_attest_set(self):
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": PIN_EPOCH}):
            envs = [attest.sign_hmac(attest.build(rel, str(self.tmp)), self.key)
                    for rel in ("docs/a.md", "docs/b.md")]
        self.assertEqual({PIN}, {env["issued_at"] for env in envs})
        path = self.tmp / "ATTEST.json"
        path.write_text(json.dumps({"schema": "nf-attest-set/1", "attestations": envs},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        return envs, path

    def test_attest_form_verdict_level_agree(self):
        envs, path = self._write_attest_set()
        core = evidence.verify_any(str(path), root=str(self.tmp), key=self.key)
        rc, standalone, err = self._standalone(
            "--evidence", str(path), "--root", str(self.tmp), "--kind", "attest",
            "--key-file", str(self.key_file), "--json")
        self.assertEqual(0, rc, err[-300:])
        self.assertEqual("ok", core["verdict"], core["issues"])
        self.assertEqual("hmac-sha256", core["level"])
        self.assertEqual(len(envs), core["count"])
        self._assert_fields_agree(core, standalone, ("verdict", "level"),
                                  "attest 形态 ok（带 key）")

        # 缺 key：hmac 级信封两边都必须 fail-closed，绝不静默降级
        core_nokey = evidence.verify_any(str(path), root=str(self.tmp))
        rc_nokey, standalone_nokey, err_nokey = self._standalone(
            "--evidence", str(path), "--root", str(self.tmp), "--kind", "attest",
            "--json")
        self.assertEqual(1, rc_nokey, err_nokey[-300:])
        self.assertEqual("invalid", core_nokey["verdict"])
        self._assert_fields_agree(core_nokey, standalone_nokey, ("verdict", "level"),
                                  "attest 形态缺 key")


class TestOutOfRepoStandalone(_Base):
    """仓外单文件：把 nf_verify.py 拷走、cwd 换到仓外，判定不得依赖仓库。"""

    def setUp(self):
        super().setUp()
        self.outside = self.tmp / "outside"
        self.outside.mkdir()
        self.copied = self.outside / "nf_verify.py"
        shutil.copy(str(SCRIPT), str(self.copied))
        self.data, _info = evidence.build(str(self.tmp), ["docs/a.md", "docs/b.md"],
                                          created_at=PIN)
        self.good = self.outside / "bundle.zip"
        self.good.write_bytes(self.data)
        self.bad = self.outside / "bad.zip"
        with zipfile.ZipFile(self.good) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members["payload/docs/a.md"] = "# A\n\n正文被改\n".encode()
        self.bad.write_bytes(evidence._zip_bytes(list(members.items())))
        # 跑的是同一份零依赖实现（拷走的是字节，不是另一个版本）
        self.assertEqual(SCRIPT.read_bytes(), self.copied.read_bytes())

    def _run_copied(self, evidence_path, *extra):
        tail = [str(self.copied), "--evidence", str(evidence_path), "--json", *extra]
        # cwd 在仓外；-I（隔离）再断掉 PYTHONPATH / 用户 site，证明不靠仓库路径
        for isolated in (False, True):
            full = [sys.executable] + (["-I"] if isolated else []) + tail
            env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            proc = subprocess.run(full, cwd=str(self.outside), capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", env=env)
            try:
                doc = json.loads(proc.stdout)
            except ValueError:
                self.fail(f"仓外单文件没给出可解析结论（isolated={isolated}）："
                          f"{proc.stderr[-300:]}")
            yield proc.returncode, doc

    def test_copied_verifier_outside_repo_agrees(self):
        core = evidence.verify(str(self.good))
        self.assertEqual("ok", core["verdict"], core["issues"])
        for rc, standalone in self._run_copied(self.good):
            self.assertEqual(0, rc)
            self.assertEqual(core["verdict"], standalone["verdict"])
            self.assertEqual(core["level"], standalone["level"])
            self.assertEqual(core["root"], standalone["root"])
            self.assertEqual(core["count"], standalone["count"])

        # 篡改件：仓外复验同样必须判 invalid（不是「仓外就放行」）
        core_bad = evidence.verify(str(self.bad))
        self.assertEqual("invalid", core_bad["verdict"])
        for rc, standalone in self._run_copied(self.bad):
            self.assertEqual(1, rc)
            self.assertEqual(core_bad["verdict"], standalone["verdict"])
            self.assertEqual(core_bad["level"], standalone["level"])


if __name__ == "__main__":
    unittest.main()
