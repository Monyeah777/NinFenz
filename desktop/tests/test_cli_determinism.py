"""CLI JSON 输出确定性：同一命令跑两次必须**逐字节相同**。

为什么（第 112 轮）：可复现性不只针对构建产物，也针对**命令输出**。CLI 若每次输出顺序/浮点格式不同，
复制输出做证据的人就无法核对；本判据用两条只读命令做最小闭环。

口径：同一命令跑两次，stdout 的 sha256 必须相同（不比对 stderr；不看耗时）。
"""
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))

#: 只读、无需外部输入的命令（避免写盘与网络）
CASES = (
    (("cognition", "--packs-list", "--json"), "方法包清单"),
    (("cognition", "--packs-list"), "方法包清单（文本面）"),
)


def _run_twice(args):
    outs = []
    for _ in range(2):
        res = subprocess.run(list(NF) + list(args), cwd=str(ROOT),
                             capture_output=True, timeout=600)
        outs.append((res.returncode, res.stdout))
    return outs


class CliDeterminismTest(unittest.TestCase):
    def test_read_only_commands_are_byte_identical(self):
        for args, label in CASES:
            first, second = _run_twice(args)
            self.assertEqual(first[0], second[0], label + " 两次退出码不同")
            self.assertEqual(0, first[0], label + " 应成功")
            self.assertTrue(first[1], label + " 输出为空")
            self.assertEqual(hashlib.sha256(first[1]).hexdigest(),
                             hashlib.sha256(second[1]).hexdigest(),
                             label + " 两次输出不一致（不可复现）")

    def test_detector_can_be_killed(self):
        """变异自证：人为让两份输出不同，比较逻辑必须判不等。"""
        a = hashlib.sha256(b"one").hexdigest()
        b = hashlib.sha256(b"two").hexdigest()
        self.assertNotEqual(a, b, "比较逻辑本身失效")


if __name__ == "__main__":
    unittest.main()
