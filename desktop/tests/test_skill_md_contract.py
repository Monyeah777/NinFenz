#!/usr/bin/env python3
"""skills/ninfenz/SKILL.md 契约：外部 agent 装载面必须「命令面真实 + 契约数不漂移 + 红线在场」。

为什么必须有：这是给外部 AI/用户装载的 skill——它一旦写了过期数字或死命令，外部 agent 会照错
执行，而仓库门禁（prose_lint 扫描面不含 skills/**）不一定报红。实测本轮抓到**真实漂移**：
SKILL 两处仍写「16 契约」，而一致性报告实际是 **27 条**契约。本轮修正数字并加「常见失败模式」
「本 skill 自身怎么验」两段，把契约数、命令面、快照红线、references 在场立成机检断言。

范围：只判本文件与其引用事实的自洽（不改技能功能）。同族判据：
test_doc_truth.TestSkillCommandFace（skills/** 的 nf 子命令须在 CLI 注册表）/
test_doc_truth.TestServeEntryNeedsNoSnapshot（无需快照红线）/ test_doc_examples（示例可运行）。
契约：frontmatter（name/description/license）合法、七段按序、契约数 == conformance_report 实况
且无「16 契约」残留、无需快照红线、references 三件与 agents 配置在场、常见失败模式与维护者
校验段要素齐、停止条件保留。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import conformance_report as cr  # noqa: E402

SKILL = ROOT / "skills" / "ninfenz" / "SKILL.md"
REFS = ROOT / "skills" / "ninfenz" / "references"
AGENT_CFG = ROOT / "skills" / "ninfenz" / "agents" / "openai.yaml"
SECTIONS = ("## 快速选路", "## 核心能力总览", "## 使用铁律", "## 阅读顺序",
            "## 常见失败模式", "## 本 skill 自身怎么验", "## 停止条件")
FAILURE_MARKERS = ("命令不存在", "无需快照", "零编造", "license: 未声明", "不是指令")
VERIFY_MARKERS = ("test_doc_truth", "test_doc_examples", "verify.sh --checks-only",
                  "nf conformance", "nf library verify")


def load_text(path: Path = SKILL) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"SKILL.md 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("SKILL.md 为空")
    return text


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def table_rows(text: str) -> list:
    body = text.split("## 快速选路", 1)[1].split("\n## ", 1)[0]
    return [ln for ln in body.splitlines() if ln.strip().startswith("|")]


def skill_issues(text: str) -> list:
    issues = []
    fm = frontmatter(text)
    if fm.get("name") != "ninfenz":
        issues.append(f"frontmatter name 应为 ninfenz：{fm.get('name')!r}")
    if "NinFenz" not in str(fm.get("description") or ""):
        issues.append("frontmatter description 缺 NinFenz 说明")
    if fm.get("license") != "MIT":
        issues.append(f"frontmatter license 应为 MIT：{fm.get('license')!r}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("七段顺序不对")
    if "16 契约" in text:
        issues.append("残留过期契约数「16 契约」（现为一致报告实况）")
    count = len(cr.CONTRACTS)
    has_count = (str(count) + " 契约") in text or (str(count) + " 条契约") in text
    if not has_count:
        issues.append(f"未写当前契约数（{count}）：以 nf conformance 实跑为准")
    if "无需快照" not in text:
        issues.append("缺「nf serve 无需快照」红线")
    for name in ("quickstart.md", "commands.md", "assembly.md"):
        if not (REFS / name).is_file():
            issues.append(f"references 缺件：{name}")
        if name not in text:
            issues.append(f"正文未引用 references/{name}")
    if not AGENT_CFG.is_file():
        issues.append("缺 agents/openai.yaml（技能装载配置）")
    for marker in FAILURE_MARKERS:
        if marker not in text:
            issues.append(f"常见失败模式缺要素：{marker}")
    for marker in VERIFY_MARKERS:
        if marker not in text:
            issues.append(f"维护者校验段缺要素：{marker}")
    rows = table_rows(text)
    if len(rows) < 16:
        issues.append(f"快速选路表行数过少（表头 + ≥16 行，实测 {len(rows)}）")
    for cmd in ("assemble", "nf library search", "nf conformance", "nf serve"):
        if cmd not in text:
            issues.append(f"快速选路缺核心命令：{cmd}")
    if "停止条件" in text and "等待用户确认" not in text:
        issues.append("停止条件缺「破坏性操作先确认」")
    return issues


class SkillMdContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_skill_md_matches_contract(self):
        self.assertEqual([], skill_issues(self.text), "skills/ninfenz/SKILL.md 不满足契约")

    def test_contract_count_is_live(self):
        self.assertIn(str(len(cr.CONTRACTS)) + " 契约", self.text)
        self.assertNotIn("16 契约", self.text)

    def test_references_and_agent_config_exist(self):
        for name in ("quickstart.md", "commands.md", "assembly.md"):
            self.assertTrue((REFS / name).is_file(), name)
        self.assertTrue(AGENT_CFG.is_file())

    def test_contract_catches_mutations(self):
        """变异自证：契约数回退 / 缺快照 / 缺段 / 缺失败模式 / 坏 frontmatter / 缺 references。"""
        stale = self.text.replace("27 契约", "16 契约", 1)
        self.assertTrue(any("16 契约" in i or "契约数" in i for i in skill_issues(stale)))
        no_snap = self.text.replace("无需快照", "可离线")
        self.assertTrue(any("快照" in i for i in skill_issues(no_snap)))
        no_section = self.text.replace("## 使用铁律", "## 铁律")
        self.assertTrue(any("缺段" in i for i in skill_issues(no_section)))
        no_fail = self.text.replace("## 常见失败模式（先自查）", "## 常见问题")
        self.assertTrue(any("缺段" in i or "失败模式" in i
                            for i in skill_issues(no_fail)))
        bad_fm = self.text.replace("name: ninfenz", "name: nf-skill", 1)
        self.assertTrue(any("name" in i for i in skill_issues(bad_fm)))
        no_ref = self.text.replace("quickstart.md", "qs.md")
        self.assertTrue(any("quickstart" in i for i in skill_issues(no_ref)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_skill.md")


if __name__ == "__main__":
    unittest.main()
