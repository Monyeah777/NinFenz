"""文档里引用的探针数字必须与结果件一致（第 133 轮）。

依据：`docs/ccos/judge-families.md` 写了「变异探针（5 判据 / 15 变异体）、负向用例覆盖率（0.84）」，
但这些数字与 `results/ccos/*.json` 之间**没有任何绑定**——探针方法改一次，文档就会静默过期。

口径：只认固定措辞（「N 判据 / N 变异体」「覆盖率（N）」），避免把任意数字都当断言。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "ccos" / "judge-families.md"
MUTATION = ROOT / "results" / "ccos" / "judge_mutation.json"
GATES = ROOT / "results" / "ccos" / "gate_negative_tests.json"


def probe_number_issues(text: str, mutation: dict, gates: dict) -> list:
    """纯函数核：文档里的探针数字必须等于结果件（供变异测试喂坏数据）。"""
    issues = []
    want = (int(mutation["judges"]), int(mutation["mutants"]))
    found = re.findall(r"(\d+)\s*判据\s*/\s*(\d+)\s*变异体", text)
    if not found:
        issues.append("文档没写「N 判据 / N 变异体」（修复指引：按固定措辞写，便于机械核对）")
    for judges, mutants in found:
        if (int(judges), int(mutants)) != want:
            issues.append("文档写 %s 判据 / %s 变异体，实际 %d / %d"
                          % (judges, mutants, want[0], want[1]))
    want_ratio = "%.2f" % float(gates["ratio"])
    found_ratio = re.findall(r"覆盖率（([0-9.]+)）", text)
    if not found_ratio:
        issues.append("文档没写「覆盖率（N）」（修复指引：按固定措辞写）")
    for ratio in found_ratio:
        if ratio != want_ratio:
            issues.append("文档写覆盖率 %s，实际 %s" % (ratio, want_ratio))
    return issues


class ProbeNumberDocsTest(unittest.TestCase):
    def _docs(self):
        return DOC.read_text(encoding="utf-8")

    def test_doc_numbers_match_results(self):
        mutation = json.loads(MUTATION.read_text(encoding="utf-8"))
        gates = json.loads(GATES.read_text(encoding="utf-8"))
        self.assertEqual([], probe_number_issues(self._docs(), mutation, gates))

    def test_judge_can_be_killed(self):
        """变异自证：把文档数字改错，纯函数核必须报出来。"""
        mutation = json.loads(MUTATION.read_text(encoding="utf-8"))
        gates = json.loads(GATES.read_text(encoding="utf-8"))
        good = "变异探针（%d 判据 / %d 变异体）、覆盖率（%s）" % (
            mutation["judges"], mutation["mutants"], "%.2f" % gates["ratio"])
        self.assertEqual([], probe_number_issues(good, mutation, gates))
        bad = good.replace(" 判据", " 条判据").replace("覆盖率（0", "覆盖率（9")
        self.assertTrue(probe_number_issues(bad, mutation, gates))
        self.assertTrue(probe_number_issues("没有数字", mutation, gates))


if __name__ == "__main__":
    unittest.main()
