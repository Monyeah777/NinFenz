#!/usr/bin/env python3
"""THIRD-PARTY-NOTICES.md 可复现性：入库件必须**逐字节等于生成器输出**（在线时才判）。

为什么必须有：`test_third_party_notices_contract` 判了格式/许可/摘要/失败即不写盘，
但它**没判**「入库这份就是生成器刚生成的」——理论上它可以被人手改后仍然格式合法。
本轮首次在本机跑通生成器（此前网络挂住，该件一直标 BLOCKED）：
`python scripts/gen_third_party_notices.py --write` 输出「44 个组件」且**工作区零差异**，
即入库件 == 生成器输出。把这个事实变成判据：在线时重生成并逐字节比对；
离线时 **skip**（不假装通过）。

范围：只判「可复现」这一件事（格式/许可/摘要由 test_third_party_notices_contract 负责）。
同族判据：test_third_party_notices_contract.py / test_license_chain.py / nf sbom 对账。
契约：在线 → 重生成后字节不变；离线 → 明确 skip 且原因可见。
"""
import socket
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"
GEN = ROOT / "scripts" / "gen_third_party_notices.py"


def online(timeout: float = 5.0) -> bool:
    try:
        socket.create_connection(("pypi.org", 443), timeout=timeout).close()
        return True
    except OSError:
        return False


class NoticesReproducibleTest(unittest.TestCase):
    def test_regenerating_is_byte_identical(self):
        if not online():
            self.skipTest("离线：无法重生成，跳过可复现性判据（不假装通过）")
        before = NOTICES.read_bytes()
        proc = subprocess.run(
            [sys.executable, "scripts/gen_third_party_notices.py", "--write"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300, check=False,
        )
        detail = (proc.stdout or "")[-400:] + (proc.stderr or "")[-400:]
        self.assertEqual(0, proc.returncode, "生成器失败（应 fail-closed 不写盘）：" + detail)
        after = NOTICES.read_bytes()
        self.assertEqual(
            before,
            after,
            "入库件与生成器输出不一致——被手改过或口径变了（重跑 --write 并提交）",
        )

    def test_generator_documents_fail_closed(self):
        self.assertTrue(GEN.is_file())
        src = GEN.read_text(encoding="utf-8")
        self.assertIn("失败即不写盘", src)


if __name__ == "__main__":
    unittest.main()
