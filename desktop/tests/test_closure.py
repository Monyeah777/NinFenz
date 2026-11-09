"""闭包台账判据（P7）：断言必须指向**真实在场**的判据，债务必须写明。

这套判据的意义：它能抓「声称有判据」。第一次跑就抓到我写错的 C-01 方法名——
如果只靠人工检查，这条会一直躺在台账里当装饰。

判据：
① 台账合法：id 唯一、status 合法、claim/reverse_fixture/evidence 齐备；
② 引用真实：criteria 里的 [文件, 方法名] 必须在 desktop/tests 的 AST 里存在；
③ 债务明示：status=debt 必须写 debt 原因；closed 必须有判据；
④ 可复算：脚本 --write/--check 一致；汇总只计数不打分。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import closure  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "closure_audit.py"))


class LedgerTest(unittest.TestCase):
    def test_ledger_is_valid(self):
        doc = closure.load(str(ROOT))
        self.assertEqual([], closure.validate(doc, str(ROOT)))

    def test_ledger_has_entries(self):
        doc = closure.load(str(ROOT))
        self.assertGreaterEqual(len(doc["entries"]), 20)

    def test_every_closed_entry_has_criteria(self):
        doc = closure.load(str(ROOT))
        for item in doc["entries"]:
            if item["status"] == "closed":
                self.assertTrue(item["criteria"], item["id"])

    def test_every_debt_entry_has_reason(self):
        doc = closure.load(str(ROOT))
        for item in doc["entries"]:
            if item["status"] == "debt":
                self.assertTrue(item.get("debt"), item["id"])

    def test_summary_counts(self):
        doc = closure.load(str(ROOT))
        summary = closure.summary(doc)
        self.assertEqual(len(doc["entries"]), summary["total"])
        self.assertEqual(summary["total"],
                         summary["by_status"].get("closed", 0)
                         + summary["by_status"].get("debt", 0))


class ReferenceTest(unittest.TestCase):
    def test_all_criteria_exist(self):
        """核心判据：台账引用的每个测试方法都必须真实存在。"""
        doc = closure.load(str(ROOT))
        available = closure.test_methods(str(ROOT))
        missing = []
        for item in doc["entries"]:
            for fname, method in item["criteria"]:
                if fname not in available or method not in available[fname]:
                    missing.append(item["id"] + " → " + fname + "::" + method)
        self.assertEqual([], missing)

    def test_missing_method_is_caught(self):
        """反例：引用不存在的方法 → 校验必须报错。"""
        doc = json.loads((Path(ROOT) / closure.REL).read_text(encoding="utf-8"))
        doc["entries"] = json.loads(json.dumps(doc["entries"]))
        doc["entries"][0]["criteria"] = [["test_closure.py", "test_does_not_exist"]]
        issues = closure.validate(doc, str(ROOT))
        self.assertTrue(any("不存在的测试方法" in i for i in issues), issues)

    def test_missing_file_is_caught(self):
        doc = json.loads((Path(ROOT) / closure.REL).read_text(encoding="utf-8"))
        doc["entries"] = json.loads(json.dumps(doc["entries"]))
        doc["entries"][0]["criteria"] = [["no_such_test.py", "test_x"]]
        self.assertTrue(any("不存在的测试文件" in i
                            for i in closure.validate(doc, str(ROOT))))

    def test_bad_evidence_is_caught(self):
        doc = json.loads((Path(ROOT) / closure.REL).read_text(encoding="utf-8"))
        doc["entries"] = json.loads(json.dumps(doc["entries"]))
        doc["entries"][0]["evidence"] = ["看起来能跑"]
        self.assertTrue(any("可跑命令" in i for i in closure.validate(doc, str(ROOT))))

    def test_duplicate_id_is_caught(self):
        doc = json.loads((Path(ROOT) / closure.REL).read_text(encoding="utf-8"))
        doc["entries"] = json.loads(json.dumps(doc["entries"]))
        doc["entries"].append(dict(doc["entries"][0]))
        self.assertTrue(any("重复" in i for i in closure.validate(doc, str(ROOT))))

    def test_closed_without_criteria_is_caught(self):
        doc = json.loads((Path(ROOT) / closure.REL).read_text(encoding="utf-8"))
        doc["entries"] = json.loads(json.dumps(doc["entries"]))
        doc["entries"][0]["criteria"] = []
        doc["entries"][0]["status"] = "closed"
        self.assertTrue(any("closed" in i for i in closure.validate(doc, str(ROOT))))

    def test_debt_without_reason_is_caught(self):
        doc = json.loads((Path(ROOT) / closure.REL).read_text(encoding="utf-8"))
        doc["entries"] = json.loads(json.dumps(doc["entries"]))
        for item in doc["entries"]:
            if item["status"] == "debt":
                item.pop("debt", None)
                break
        self.assertTrue(any("债务原因" in i for i in closure.validate(doc, str(ROOT))))


class ScriptTest(unittest.TestCase):
    def test_report_is_reproducible(self):
        proc = subprocess.run([*NF, "--json"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        report = json.loads(proc.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["summary"]["total"], len(report["rows"]))

    def test_human_output_mentions_debt(self):
        proc = subprocess.run([*NF], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        self.assertIn("债", proc.stdout)


if __name__ == "__main__":
    unittest.main()
