#!/usr/bin/env python3
"""integrations/README.md 契约：接入面说明必须「行数 / 状态分布 / 词表使用 / 校验入口」自洽。

为什么必须有：这份 README 的生成区由 `core.integrations.render_index()` 渲染、
check38 子扫描逐字对账，但**散文部分**（字段口径 / 边界 / 规模）没有判据——
实测读者无法从文档得知「到底几个接入面、哪些 kind 真被用到、词表里有几个值没人用」。
本轮补「§现状对照」「§复现与引用口径」并加本判据。

范围：只判本文与 integration.json / schema / check38 事实自洽（不改政策）。
同族判据：test_engine_registry.py / test_interop_thirdparty_kit.py / check38。
契约：生成区行数 == stats.count == 14、status 分布 12/2、已用 kind 7 类、
词表 kind 8 / status 3 / tier 2、check38 子扫描在场、
**「没有 nf integrations 子命令」诚实标注**、复现命令可用、边界口径在场。
"""
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import integrations as it  # noqa: E402

DOC = ROOT / "integrations" / "README.md"
DIR = ROOT / "integrations"
SCHEMA = ROOT / "protocol" / "schema" / "integration.schema.json"
VERIFY = ROOT / "verify.sh"


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"接入面 README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("接入面 README 为空")
    return text


def rows() -> list:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(DIR.glob("*/integration.json"))]


def readme_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 接入面（integrations）"):
        issues.append("缺标题「# NF 接入面（integrations）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for section in ("## 字段口径", "## 现状对照", "## 复现与引用口径", "## 边界（不宣称）"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    issues_list, stats = it.check(str(ROOT))
    if issues_list:
        issues.append(f"integrations.check 有缺口：{issues_list[:2]}")
    if stats["count"] != 14:
        issues.append(f"接入面数已变（{stats['count']}）")
    if "**14**" not in text:
        issues.append("现状未写 14 个接入面")
    st = Counter(r["status"] for r in rows())
    if st != {"active": 12, "proposed": 2}:
        issues.append(f"状态分布已变（{dict(st)}）")
    if "**active 12 · proposed 2**" not in text:
        issues.append("现状未写状态分布 active 12 · proposed 2")
    used = sorted({r["kind"] for r in rows()})
    if len(used) != 7:
        issues.append(f"已用 kind 数已变（{len(used)}）")
    if "**7 类**" not in text:
        issues.append("现状未写已用 7 类 kind")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]
    if len(schema["kind"]["enum"]) != 8 or "**8 类**" not in text:
        issues.append("词表 kind 数（8）与文档不一致")
    if len(schema["status"]["enum"]) != 3 or "**3 值**" not in text:
        issues.append("词表 status 数（3）与文档不一致")
    if len(schema["tier"]["enum"]) != 2 or "**2 值**" not in text:
        issues.append("词表 tier 数（2）与文档不一致")
    if "integrations" not in VERIFY.read_text(encoding="utf-8"):
        issues.append("verify.sh 缺 check38 integrations 子扫描")
    if "没有** `nf integrations` 子命令" not in text and "nf integrations" not in text:
        issues.append("缺「没有 nf integrations 子命令」诚实标注")
    if "≠" not in text or "外部互操作" not in text:
        issues.append("缺「接入面声明 ≠ 外部互操作实测」边界")
    out = subprocess.run([sys.executable, "-c",
                          "import sys;sys.path.insert(0,'desktop/src');"
                          "from core import integrations as i;"
                          "print(i.check('.')[0] or 'zero issues')"],
                         cwd=str(ROOT), capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120, check=False)
    if "zero issues" not in out.stdout:
        issues.append(f"复现命令未得零缺口：{out.stdout[-80:]}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class IntegrationsReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "接入面 README 不满足契约")

    def test_data_live(self):
        issues_list, stats = it.check(str(ROOT))
        self.assertEqual([], issues_list)
        self.assertEqual(14, stats["count"])

    def test_contract_catches_mutations(self):
        """变异自证：规模回退 / 状态分布漂移 / 缺诚实标注 / 缺边界。"""
        bad = self.text.replace("**14**", "**12**")
        self.assertTrue(any("14" in i for i in readme_issues(bad)))
        st_bad = self.text.replace("**active 12 · proposed 2**", "**active 14**")
        self.assertTrue(any("状态分布" in i for i in readme_issues(st_bad)))
        no_cmd = self.text.replace("nf integrations", "nf integ")
        self.assertTrue(any("nf integrations" in i for i in readme_issues(no_cmd)))
        no_edge = self.text.replace("外部互操作", "互操作")
        self.assertTrue(any("边界" in i for i in readme_issues(no_edge)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_integrations_readme.md")


if __name__ == "__main__":
    unittest.main()
