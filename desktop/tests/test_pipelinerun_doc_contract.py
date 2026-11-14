#!/usr/bin/env python3
"""docs/pipelinerun.md 契约：管线抽象执行文档必须「114 管线/282 模块/hard 0/advisory 1142」一致。

为什么必须有：这页回答「声明跑得通吗」——管线数、执行模块数、官方核心基座、hard 与 advisory 分列，
任何一项漂移都会让「门禁口径（hard 数）」与读者认知错位。本轮补「§现状对照」「§复现与引用口径」，
把数字与 core/pipelinerun.sweep() 实读双向绑定（不是抄日志）。

范围：只判本文与 pipelinerun 实现/判据事实自洽（不改实现）。
同族判据：test_pipeline.py / test_pipeline_loader.py / test_pipeline_scaffold.py /
test_doc_hygiene.py。
契约：最后更新位 + 复核、114 管线、282 模块、13 基座、hard 0、advisory 1142 三分解、
CLI 两子命令、现状对照 + 复现三命令、hard 判死 advisory 供裁决口径。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import pipelinerun as pr  # noqa: E402

DOC = ROOT / "docs" / "pipelinerun.md"
SECTIONS = ("## 是什么", "## 判决分层（关键）", "## 怎么用", "## 现状对照",
            "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"管线执行文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("管线执行文档为空")
    return text


def stats() -> dict:
    hard, data = pr.sweep(str(ROOT))
    return {"hard": len(hard), **data}


def run_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 管线抽象执行"):
        issues.append("缺标题「# 管线抽象执行（dry-run → GraphSpec）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    s = stats()
    if s["pipelines"] != 114:
        issues.append(f"管线数已变（{s['pipelines']}）")
    if s["modules"] != 282:
        issues.append(f"执行模块数已变（{s['modules']}）")
    if s["core_base"] != 13:
        issues.append(f"官方核心基座数已变（{s['core_base']}）")
    if s["hard"] != 0:
        issues.append(f"出现 hard 缺陷（{s['hard']}）")
    if s["notes"] != 1142:
        issues.append(f"advisory 数已变（{s['notes']}）")
    buckets = s["advisory_buckets"]
    if buckets.get("同层依赖序") != 2 or buckets.get("跨包/外部事件") != 1134:
        issues.append(f"advisory 分解已变：{buckets}")
    for label in ("**114**", "**282**", "**13**", "**0**", "**1142**"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    if "同层序 2" not in text or "跨包事件 1134" not in text:
        issues.append("缺 advisory 三类分解")
    for sub in ("new", "dryrun"):
        if sub not in text:
            issues.append(f"缺 CLI 子命令：{sub}")
    if "**2**：" not in text:
        issues.append("未写 CLI 两个子命令")
    if "hard 判死" not in text and "hard 判" not in text:
        issues.append("缺「hard 判死 / advisory 供裁决」口径")
    if "不调模型" not in text:
        issues.append("缺 dry-run 不调模型口径")
    positions = [text.find(s2) for s2 in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py pipeline dryrun --all",
                "python scripts/nf.py pipeline new",
                "python -m pytest desktop/tests/test_pipeline_loader.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PipelineRunDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pipelinerun_matches_contract(self):
        self.assertEqual([], run_issues(self.text), "管线执行文档不满足契约")

    def test_sweep_live(self):
        s = stats()
        self.assertEqual(114, s["pipelines"])
        self.assertEqual(282, s["modules"])
        self.assertEqual(13, s["core_base"])
        self.assertEqual(0, s["hard"])
        self.assertEqual(1142, s["notes"])

    def test_contract_catches_mutations(self):
        """变异自证：管线数回退 / 模块数回退 / advisory 回退 / 缺子命令 / 缺命令。"""
        old = self.text.replace("**114**", "**100**")
        self.assertTrue(any("114" in i for i in run_issues(old)))
        old_m = self.text.replace("**282**", "**260**")
        self.assertTrue(any("282" in i for i in run_issues(old_m)))
        old_a = self.text.replace("**1142**", "**1100**")
        self.assertTrue(any("1142" in i for i in run_issues(old_a)))
        no_sub = self.text.replace("**2**：", "**1**：")
        self.assertTrue(any("两个子命令" in i for i in run_issues(no_sub)))
        no_cmd = self.text.replace("python scripts/nf.py pipeline new <id>", "派生管线")
        self.assertTrue(any("pipeline new" in i for i in run_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_pipelinerun.md")


if __name__ == "__main__":
    unittest.main()
