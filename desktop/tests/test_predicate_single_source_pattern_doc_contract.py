#!/usr/bin/env python3
"""patterns/predicate-single-source/PATTERN.md 契约：单一谓词仍被唯一实现、消费方走导入、不钉条数。

为什么必须有：这条 pattern 的可检面是「一条判据只准有一处实现」——如果哪天有人又在某模块里写回
目录白名单/裸 os.walk，pattern 就失效；而文档里 2026-10-03 的「206→103 / 614→307」是**历史留痕**，
容易被误读成当前值。本轮补「§现状对照」「§复现与引用口径」并加判据，把三件事钉住：
谓词载体仍在、消费方仍走导入、正文不把历史数值当现状。

范围：只判本文与 repo_face/消费方/判据事实自洽（不改实现）。
同族判据：test_repo_face.py（12 例）/ test_fail_closed_pattern_doc_contract.py（同骨架）。
契约：6 必填键、3 规则、applies_to 四目标在场、
evidence（repo_face + test_repo_face + check12/check23）可解析、
为什么/怎么用/反例/现状对照/复现口径五段、消费方 ≥3 走导入、
谓词函数在文、历史留痕与「不钉」口径。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "predicate-single-source" / "PATTERN.md"
CORE = ROOT / "desktop" / "src" / "core"


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"pattern 正文不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("pattern 正文为空")
    return text


def entry() -> dict:
    for e in pat.entries(str(ROOT)):
        if e["dir"] == "predicate-single-source":
            return e
    raise ValueError("patterns 里找不到 predicate-single-source")


def consumers() -> list:
    out = []
    for p in CORE.glob("*.py"):
        if "from core import repo_face" in p.read_text(encoding="utf-8", errors="replace"):
            out.append(p.name)
    return sorted(out)


def predicate_issues(text: str) -> list:
    issues = []
    e = entry()
    fm = e["fm"]
    for key in pat.REQUIRED:
        if key not in fm:
            issues.append(f"frontmatter 缺 {key}")
    rules = pat._as_list(fm.get("rules"))
    if len(rules) != 3:
        issues.append(f"规则数已变（{len(rules)}，应为 3）")
    verify_text = (ROOT / "verify.sh").read_text(encoding="utf-8")
    for target in pat._as_list(fm.get("applies_to")):
        if not (ROOT / target).exists():
            issues.append(f"applies_to 不在场：{target}")
    for ev in pat._as_list(fm.get("evidence")):
        rel = str(ev).replace("\\", "/")
        if rel.startswith("check") and rel[5:].isdigit():
            if f"check{rel[5:]}()" not in verify_text:
                issues.append(f"evidence 的 check 不存在：{rel}")
            continue
        if not (ROOT / rel).exists():
            issues.append(f"evidence 不在场：{rel}")
    face = CORE / "repo_face.py"
    if not face.is_file() or "def walk_repo_paths" not in face.read_text(encoding="utf-8"):
        issues.append("repo_face.walk_repo_paths 不在场（单一谓词消失）")
    cons = consumers()
    if len(cons) < 3:
        issues.append(f"消费方少于 3（{cons}）——单一谓词可能被绕过")
    for section in ("## 为什么", "## 怎么用", "## 反例", "## 现状对照",
                    "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "walk_repo_paths" not in text:
        issues.append("正文未点名 walk_repo_paths")
    if "实测（2026-10-03）" not in text:
        issues.append("缺历史留痕（实测 2026-10-03）")
    if "不钉" not in text:
        issues.append("缺「扫描面/台账数不钉」口径")
    if "以实读为准" not in text:
        issues.append("缺「以实读为准」的现状口径")
    for cmd in ("python -m pytest desktop/tests/test_repo_face.py",
                "python scripts/nf.py asset inventory"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PredicateSingleSourceTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pattern_matches_contract(self):
        self.assertEqual([], predicate_issues(self.text), "predicate-single-source 不满足契约")

    def test_predicate_and_consumers_live(self):
        self.assertIn("def walk_repo_paths", (CORE / "repo_face.py").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(consumers()), 3)

    def test_repo_face_judge_passes(self):
        import subprocess
        proc = subprocess.run([sys.executable, "-m", "pytest",
                               "desktop/tests/test_repo_face.py", "-q"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, proc.stdout[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：缺现状段 / 缺谓词点名 / 缺不钉口径 / 缺留痕。"""
        no_sec = self.text.replace("## 现状对照", "## 附注")
        self.assertTrue(any("现状对照" in i for i in predicate_issues(no_sec)))
        no_fn = self.text.replace("walk_repo_paths", "某个函数")
        self.assertTrue(any("walk_repo_paths" in i for i in predicate_issues(no_fn)))
        no_pin = self.text.replace("不钉", "已钉死")
        self.assertTrue(any("不钉" in i for i in predicate_issues(no_pin)))
        no_hist = self.text.replace("实测（2026-10-03）", "实测")
        self.assertTrue(any("留痕" in i for i in predicate_issues(no_hist)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_predicate.md")


if __name__ == "__main__":
    unittest.main()
