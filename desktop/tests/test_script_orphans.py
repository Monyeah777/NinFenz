"""脚本孤儿棘轮：不许新增「没有任何入口指向」的脚本（第 141 轮）。

为什么：第 125–129 轮补的是「引用有效吗」（指向的东西存在不存在），方向相反的问题——
「有没有东西指向它」——没人管。76 个脚本里 5 个没有任何引用（一次性审计脚本，保留但不该继续增加）。

口径：脚本名（去扩展名）必须出现在**任何文本面**（测试 / 其他脚本 / 文档 / 打包 / shell），
排除自身与本件（否则自指会自我满足）；已知 5 个冻结，修复后须删条目。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: 第 141 轮已知无引用的脚本（历史一次性审计，理由见 docs/ccos/one-shot-audits.md）
ORPHANS = frozenset({
    "abi_call_vectors", "adr_check", "atom_invariants",
    "engine_status", "plugin_promote", "gen_third_party_notices",
})


def _texts(exclude: set) -> list:
    """全仓**可执行面**文本（测试 / 脚本 / 打包 / shell），排除指定文件名。"""
    # 文档点名不算「有入口」，否则孤儿判据会被文档稀释。
    pats = ("desktop/tests/*.py", "scripts/*.py", "packaging/**/*.mjs", "*.sh")
    out = []
    for pat in pats:
        for p in ROOT.glob(pat):
            if p.is_file() and p.name not in exclude:
                out.append((p, p.read_text(encoding="utf-8", errors="replace")))
    return out


def orphan_scripts(texts: list) -> list:
    """没有**其他**可执行面提及的脚本（排除脚本自身，否则 usage 行会自我满足）。"""
    out = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        stem = path.stem
        if not any(stem in text for other, text in texts if other != path):
            out.append(stem)
    return out


class ScriptOrphanTest(unittest.TestCase):
    def _texts(self) -> list:
        return _texts({Path(__file__).name})

    def test_no_new_orphan_scripts(self):
        texts = self._texts()
        orphans = orphan_scripts(texts)
        new = sorted(set(orphans) - ORPHANS)
        self.assertEqual([], new,
                         "新增了没有任何引用的脚本（修复指引：在文档/测试里给它一个入口，"
                         "或评审后写进 ORPHANS 并说明理由）：" + ", ".join(new))

    def test_frozen_list_is_not_stale(self):
        texts = self._texts()
        still = set(orphan_scripts(texts))
        fixed = sorted(ORPHANS - still)
        self.assertEqual([], fixed,
                         "这些脚本已有引用，应从 ORPHANS 删除：" + ", ".join(fixed))

    def test_orphans_are_documented(self):
        """冻结的孤儿必须在一次性审计清单里点名，否则「保留」就成了无理由堆积。"""
        doc = (ROOT / "docs" / "ccos" / "one-shot-audits.md").read_text(encoding="utf-8")
        missing = sorted(s for s in ORPHANS if s not in doc)
        self.assertEqual([], missing, "一次性审计清单没写这些脚本：" + ", ".join(missing))

    def test_doc_lists_only_frozen_orphans(self):
        """反方向：文档不能多列（第 184 轮）。

        原判据只查「冻结集 ⊆ doc」，于是文档多写一个脚本也不会红。
        多写意味着文档声称某脚本是「一次性审计」，而判据认为它有引用——两边对同一事实表述不同。
        """
        import re

        doc = (ROOT / "docs" / "ccos" / "one-shot-audits.md").read_text(encoding="utf-8")
        listed = set(re.findall(r"scripts/([A-Za-z0-9_]+)\.py", doc))
        extra = sorted(listed - set(ORPHANS))
        self.assertEqual([], extra,
                         "文档多列了这些脚本（它们已有引用，不该在一次性审计清单里）："
                         + ", ".join(extra))

    def test_scan_is_not_vacuous(self):
        self.assertGreaterEqual(len(list((ROOT / "scripts").glob("*.py"))), 70,
                                "脚本太少（判据可能已失效）")
        found = any("sbom" in text for _path, text in self._texts())
        self.assertTrue(found, "全仓文本面里找不到已知脚本（扫描失效）")


if __name__ == "__main__":
    unittest.main()
