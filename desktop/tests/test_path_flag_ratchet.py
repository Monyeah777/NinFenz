"""路径类旗标的覆盖棘轮：新旗标必须有测试真跑，旧缺口冻结在案。

为什么（第 123 轮，来自 operations 域的「面板与判据同源」）：
CLI 里收**路径**的旗标有 59 个，其中 22 个从未被任何测试提到。路径处理写错的风险是
「写到仓库外」或「读到错文件」——比普通开关严重得多。

本件不假装这 22 个都已覆盖：把它们**冻结**成已知缺口（LEGACY_UNCOVERED），
并禁止新增未覆盖的路径旗标；缺口减少时也要同步删条目（另一条判据保证不陈旧）。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import nf  # noqa: E402

#: 第 123 轮审计时已知未被测试提及的路径旗标（冻结；新增的不许进这里）
LEGACY_UNCOVERED = frozenset({
    "--ballots", "--build-dest", "--check-file", "--check-md",
    "--context-dir", "--decision", "--experiment",
    "--job-id", "--journal",
    "--label-object", "--prev", "--responses", "--save-path", "--script-file",
    "--session-path", "--sidecar", "--state-path", "--template",
})


def _test_text() -> str:
    """除本件外的测试文本（本件自己列着旗标名，不排除会自我满足）。"""
    files = sorted(p for p in (ROOT / "desktop" / "tests").glob("test_*.py")
                   if p.name != Path(__file__).name)
    return "".join(p.read_text(encoding="utf-8", errors="replace") for p in files)


def _path_flags() -> list:
    return sorted({"--" + d.replace("_", "-") for d in nf._PATH_FLAG_DESTS})


class PathFlagRatchetTest(unittest.TestCase):
    def test_no_new_uncovered_path_flags(self):
        text = _test_text()
        uncovered = [f for f in _path_flags() if f not in text]
        new = sorted(set(uncovered) - LEGACY_UNCOVERED)
        hint = ("新增了未被测试覆盖的路径旗标：" + ", ".join(new)
                + "（修复指引：加一条真跑测试，或评审后写进 LEGACY_UNCOVERED 说明理由）")
        self.assertEqual([], new, hint)

    def test_legacy_list_is_not_stale(self):
        text = _test_text()
        covered_now = sorted(f for f in LEGACY_UNCOVERED if f in text)
        hint = "这些旗标已被测试覆盖，应从 LEGACY_UNCOVERED 删除：" + ", ".join(covered_now)
        self.assertEqual([], covered_now, hint)

    def test_path_flags_are_discoverable(self):
        self.assertGreaterEqual(len(_path_flags()), 50, "没扫到路径旗标（判据可能失效）")


if __name__ == "__main__":
    unittest.main()
