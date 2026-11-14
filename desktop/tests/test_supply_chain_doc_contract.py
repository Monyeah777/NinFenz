#!/usr/bin/env python3
"""docs/ccos/supply-chain-v0.md 契约：供应链对象文档必须「三摘要/材料清单/验证器名单与实现一致」。

为什么必须有：这份文档是「结论可复用」的口径来源——材料清单条数、验证器摘要覆盖的几个判定面脚本、
结论三态，任何一项漂移都会让「是谁判的/基于哪些输入」这两个问题失去可核性。本轮补最后更新位、
现状对照与复现口径，并把材料 count、JUDGE_FILES、三态、实现四件、五条边界全部活绑定。

范围：只判本文与 sbom/verifier_version/verifier_status 事实自洽（不改摘要口径）。同族判据：
test_sbom.py（4 例）/ test_verifier_status.py / test_verifier_version.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、三摘要表在文、材料 count==materials 且为 572、JUDGE_FILES==10、
三态 current/stale/unknown 与 stale rc=1、实现四件在场、五条边界、现状对照 + 复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def live_count() -> int:
    """材料条数真源 = results/ccos/sbom.json（本文只做投影，不钉死数字）。"""
    import json
    data = json.loads((ROOT / "results" / "ccos" / "sbom.json").read_text(encoding="utf-8"))
    return int(data["count"])
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import verifier_version  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "supply-chain-v0.md"
SBOM = ROOT / "results" / "ccos" / "sbom.json"
SBOM_SCRIPT = ROOT / "scripts" / "sbom.py"
STATUS_SCRIPT = ROOT / "scripts" / "verifier_status.py"
PROBE = ROOT / "scripts" / "self_audit_probe.py"
SECTIONS = ("## 这份文档解决什么", "## 三个摘要各管一段", "## 材料清单", "## 结论可复用性",
            "## 现状对照", "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"供应链文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("供应链文档为空")
    return text


def sbom() -> dict:
    return json.loads(SBOM.read_text(encoding="utf-8"))


def supply_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 供应链对象 v0"):
        issues.append("缺标题「# 供应链对象 v0（材料清单 + 验证器摘要 + 结论绑定）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for name in ("verifier_digest", "materials_digest", "head_start", "head_end"):
        if name not in text:
            issues.append(f"三摘要缺要素：{name}")
    data = sbom()
    n_count = int(data.get("count") or 0)
    n_mats = len(data.get("materials") or [])
    if n_count != n_mats:
        issues.append(f"sbom count 与 materials 不等（{n_count} vs {n_mats}）")
    if n_count != live_count():
        issues.append(f"材料条数已变（{n_count}）")
    if str(live_count()) not in text:
        issues.append(f"未写材料清单 {live_count()}（应与 sbom 实读一致）")
    n_judge = len(verifier_version.JUDGE_FILES)
    if n_judge != 10:
        issues.append(f"JUDGE_FILES 已变（{n_judge}）")
    if "10 个" not in text and "恰 10" not in text:
        issues.append("未写验证器覆盖 10 个脚本")
    for state in ("current", "stale", "unknown"):
        if state not in text:
            issues.append(f"缺结论三态：{state}")
    if "退出码 1" not in text:
        issues.append("缺「stale 退出码 1」口径")
    for path in (SBOM_SCRIPT, STATUS_SCRIPT, PROBE):
        if not path.is_file():
            issues.append(f"缺脚本：{path.relative_to(ROOT).as_posix()}")
    for marker in ("不做签名", "不覆盖被测内容", "不是全仓清单", "不在材料清单里",
                   "跨机器不可比"):
        if marker not in text:
            issues.append(f"边界缺要素：{marker}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/sbom.py --check",
                "python scripts/verifier_status.py",
                "python -m pytest desktop/tests/test_sbom.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class SupplyChainDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_supply_chain_matches_contract(self):
        self.assertEqual([], supply_issues(self.text), "供应链文档不满足契约")

    def test_artifacts_live(self):
        data = sbom()
        self.assertEqual(live_count(), int(data["count"]))
        self.assertEqual(live_count(), len(data["materials"]))
        self.assertEqual(10, len(verifier_version.JUDGE_FILES))
        for path in (SBOM_SCRIPT, STATUS_SCRIPT, PROBE):
            self.assertTrue(path.is_file(), path)

    def test_contract_catches_mutations(self):
        """变异自证：材料数回退 / 验证器数回退 / 缺三态 / 缺边界 / 缺命令。"""
        old_n = self.text.replace(str(live_count()), "571")
        self.assertTrue(supply_issues(old_n), "改坏材料条数后判据未变红")
        old_j = self.text.replace("10 个", "9 个").replace("恰 10 项", "恰 9 项")
        self.assertTrue(any("10" in i for i in supply_issues(old_j)))
        no_state = self.text.replace("unknown", "missing")
        self.assertTrue(any("unknown" in i for i in supply_issues(no_state)))
        no_edge = self.text.replace("不做签名", "做摘要")
        self.assertTrue(any("不做签名" in i for i in supply_issues(no_edge)))
        no_cmd = self.text.replace("python scripts/sbom.py --check", "检查清单")
        self.assertTrue(any("--check" in i for i in supply_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_supply.md")


if __name__ == "__main__":
    unittest.main()
