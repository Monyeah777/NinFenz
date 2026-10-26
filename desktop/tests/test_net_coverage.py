"""引擎线（engine/dotnet/）的 verify.sh 覆盖率口径必须与真源自洽（防分母陈旧）。

为什么（2026-10-14 实测）：engine/dotnet/README.md 的覆盖率行长期钉在
「39 道 check：覆盖 32 / 不适用 6 / 范围外 1」；而真源 verify.sh 于 2026-10-04
新增 check40（数字资产契约），分母没跟着走，且 .NET 线内零处引用
asset_contract / protocol/asset_contracts.json ⇒ 新 check 静默落在矩阵之外。
本判据把「钉死的三个桶必须与 EXPECTED_CHECKS 自洽」变成常驻断言（随 check12）。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import quality_baseline as qb  # noqa: E402

README_REL = "engine/dotnet/README.md"
_ROW = re.compile(r"^\|[^|]*verify\.sh[^|]*覆盖率[^|]*\|(.*)\|[ \t]*$", re.M)
_BUCKET = re.compile(r"(覆盖|不适用|范围外)\s*(\d+)")
TRUTH = ("EXPECTED_CHECKS", "quality_baseline")


def coverage_issues(text: str, expected: int):
    """覆盖率行的确定性判据 -> issue 列表（正例与负例共用）。"""
    m = _ROW.search(text)
    if not m:
        return ["缺 verify.sh 覆盖率行"]
    row = m.group(1)
    buckets = {k: int(v) for k, v in _BUCKET.findall(row)}
    out = []
    for key in ("覆盖", "不适用", "范围外"):
        if key not in buckets:
            out.append(f"覆盖率行缺桶：{key}")
    if not any(t in row for t in TRUTH):
        out.append("覆盖率行未指向真源（{}）".format(" / ".join(TRUTH)))
    if not out and sum(buckets.values()) != expected:
        out.append(f"覆盖率分母与真源不一致：行内合计 {sum(buckets.values())}"
                   f" != EXPECTED_CHECKS {expected}（修复指引：逐条裁定新 check 后同步本行）")
    return out


class NetCoverageAdjudicationTest(unittest.TestCase):
    def test_real_readme_is_consistent_with_truth_source(self):
        text = (ROOT / README_REL).read_text(encoding="utf-8")
        self.assertEqual([], coverage_issues(text, qb.EXPECTED_CHECKS))

    def test_stale_denominator_is_fail(self):
        text = ("| verify.sh 覆盖率 | 39 道：**覆盖 32 / 不适用 6 / 范围外 1**；"
                "真源见 EXPECTED_CHECKS |")
        self.assertTrue(any("不一致" in i for i in coverage_issues(text, 40)))

    def test_missing_truth_pointer_is_fail(self):
        text = "| verify.sh 覆盖率 | **覆盖 32 / 不适用 6 / 范围外 2** |"
        self.assertTrue(any("未指向真源" in i for i in coverage_issues(text, 40)))


if __name__ == "__main__":
    unittest.main()
