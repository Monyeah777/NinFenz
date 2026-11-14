#!/usr/bin/env python3
"""docs/meta/ROADMAP.md 契约：路标文档必须「版本三处一致 / 基线不手写 / check39 在门禁」。

为什么必须有：这页是结果导向的路标——它刻意**不手写版本与 PASS 数**（防漂移），但因此更需要
把「数字从哪读」写死。本轮补：版本三处一致（pyproject / npm / mcp_package）、门禁基线在
repo_stats、端壳零回潮由 check39 判，并加「§现状对照」「§复现与引用口径」。
本判据把三条真源、check39、L3_FROZEN / terminal 入口、治理边界全部活绑定。

范围：只判本文与版本真源/repo_stats/verify.sh/相关文档事实自洽（不改实现）。
同族判据：test_verifier_version.py / test_ci_supply_chain.py（版本对账）/ test_doc_hygiene.py。
契约：最后更新位 + 复核、版本三处一致、repo_stats 两键在盘、check39 在 verify.sh、
「不手写」纪律、三长期路标、三治理边界、现状对照 + 复现两命令。
"""
import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "meta" / "ROADMAP.md"
PYPROJECT = ROOT / "pyproject.toml"
NPM = ROOT / "packaging" / "npm" / "package.json"
MCP = ROOT / "protocol" / "mcp_package.json"
STATS = ROOT / "protocol" / "repo_stats.json"
VERIFY = ROOT / "verify.sh"
SECTIONS = ("## 当前状态", "## 现状对照", "## 复现与引用口径", "## 版本真源",
            "## 长期路标", "## 治理边界")
LONG = ("可机检、可执行、模型无关", "质量唯一论", "一次性补测外部互操作证据")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"路标文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("路标文档为空")
    return text


def versions() -> dict:
    with open(PYPROJECT, "rb") as fh:
        py = tomllib.load(fh)["project"]["version"]
    npm = json.loads(NPM.read_text(encoding="utf-8"))["version"]
    mcp = json.loads(MCP.read_text(encoding="utf-8"))["version"]
    return {"pyproject": py, "npm": npm, "mcp": mcp}


def roadmap_issues(text: str) -> list:
    issues = []
    if not text.startswith("# Roadmap"):
        issues.append("缺标题「# Roadmap」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    v = versions()
    if len(set(v.values())) != 1:
        issues.append(f"版本三处不一致：{v}")
    if "**1.0.5**" not in text and v["pyproject"] not in text:
        issues.append("未写当前版本（应注明三处一致）")
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    for key in ("baseline_checks", "baseline_pass"):
        if key not in stats:
            issues.append(f"repo_stats 缺键：{key}")
        if key not in text:
            issues.append(f"正文未点名：{key}")
    verify = VERIFY.read_text(encoding="utf-8")
    if "check39" not in verify:
        issues.append("verify.sh 缺 check39")
    if "check39" not in text:
        issues.append("正文缺 check39")
    for marker in ("L3_FROZEN.md", "docs/terminal.md", "nf shell"):
        if marker not in text:
            issues.append(f"缺端壳/入口口径：{marker}")
    for lane in LONG:
        if lane not in text:
            issues.append(f"长期路标缺：{lane}")
    if "只承载方向" not in text and "只承载方向/结果/状态" not in text:
        issues.append("缺「公开仓只承载方向/结果/状态」治理边界")
    if "不是质量顶尖的宣称" not in text:
        issues.append("缺「门禁绿 ≠ 质量顶尖」口径")
    if "不手写" not in text:
        issues.append("缺「版本/数字不手写」纪律")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py stats --check",
                "bash verify.sh --checks-only"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class RoadmapDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_roadmap_matches_contract(self):
        self.assertEqual([], roadmap_issues(self.text), "路标文档不满足契约")

    def test_versions_live(self):
        v = versions()
        self.assertEqual(1, len(set(v.values())))
        stats = json.loads(STATS.read_text(encoding="utf-8"))
        self.assertIn("baseline_checks", stats)
        self.assertIn("baseline_pass", stats)

    def test_contract_catches_mutations(self):
        """变异自证：版本回退 / 缺基线键 / 缺 check39 / 缺长期路标 / 缺命令。"""
        old = self.text.replace("**1.0.5**", "**0.9.0**")
        self.assertTrue(any("版本" in i for i in roadmap_issues(old)))
        no_s = self.text.replace("baseline_pass", "pass_count")
        self.assertTrue(any("baseline_pass" in i for i in roadmap_issues(no_s)))
        no_c = self.text.replace("check39", "check38")
        self.assertTrue(any("check39" in i for i in roadmap_issues(no_c)))
        no_l = self.text.replace("质量唯一论", "质量优先")
        self.assertTrue(any("长期路标" in i for i in roadmap_issues(no_l)))
        no_cmd = self.text.replace("bash verify.sh --checks-only", "跑门禁")
        self.assertTrue(any("checks-only" in i for i in roadmap_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_roadmap.md")


if __name__ == "__main__":
    unittest.main()
