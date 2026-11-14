#!/usr/bin/env python3
"""docs/fde-stack.md 契约：栈位契约必须「载体引用真实存在 + 五条达标线 + 互操作面清点一致」。

为什么必须有：这份文档给客户侧决策人判断「NF 到底在下层/上层之间承担什么」——它引用的每件载体都必须
真实存在。本轮修的是失效引用：原文把 MCP 传输面写成 results/interop/mcp.json，但该文件不在仓内
（MCP 是 nf run --fmt mcp 的运行期产物），而仓里实际提交 12 件互操作面（含 a2a，不含 mcp）。
若不清点，客户按文档去取 mcp.json 会扑空。本判据把 12 件面、标准规模、入口件、
基线件、五条达标线全部活绑定。

范围：只判本文与 interop/standards/入口件事实自洽（不改产物）。
同族判据：test_interop*.py（12 面导出）/ test_standards*.py / test_doc_hygiene.py /
test_doc_examples.py。契约：最后更新位 + 复核、12 件面逐名在文且文件在场、
mcp.json 不再被当仓内件、370/1200、llms.txt + AGENT_START + quality_baseline +
schema-validation 在场、五条达标线、现状对照 + 复现三命令。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "fde-stack.md"
INTEROP = ROOT / "results" / "interop"
CATALOG = ROOT / "protocol" / "standards_catalog.json"
BINDING = ROOT / "protocol" / "standards_binding.json"
SECTIONS = ("## 一、栈位", "## 二、边界契约", "## 三、中游标准的五条达标线",
            "## 现状对照", "## 复现与引用口径", "## 四、与其它出口的关系", "## 五、非目标")
LINES = ("可装载", "可质检", "可复现", "零编造", "白盒")
REQUIRED = ("llms.txt", "docs/agent/AGENT_START.md", "results/interop-schema-validation.md",
            "desktop/src/core/quality_baseline.py", "docs/interop-thirdparty.md",
            "results/interop-thirdparty-status.md", "docs/fde-sample/")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"FDE 栈位文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("FDE 栈位文档为空")
    return text


def stack_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 在 FDE AI infra 中的中游位置"):
        issues.append("缺标题「# NF 在 FDE AI infra 中的中游位置（栈位契约）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    faces = sorted(p.stem for p in INTEROP.glob("*.json"))
    if len(faces) != 12:
        issues.append(f"互操作面数已变（{len(faces)}）")
    for f in faces:
        if f not in text:
            issues.append(f"正文缺互操作面：{f}")
    table_hits = [ln for ln in text.splitlines()
                  if ln.startswith("|") and "results/interop/mcp.json" in ln
                  and "原写" not in ln and "失效引用" not in ln]
    if table_hits:
        issues.append("仍把 results/interop/mcp.json 当仓内件引用（表内行）")
    if "运行期产物" not in text:
        issues.append("缺「MCP 为运行期产物」口径")
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    n_std = len(cat.get("standards") or [])
    if n_std != 370:
        issues.append(f"标准条数已变（{n_std}）")
    if "370" not in text:
        issues.append("正文缺 370 条标准")
    b = json.loads(BINDING.read_text(encoding="utf-8"))
    if int(b.get("bindings_total") or 0) != 1200:
        issues.append(f"绑定条数已变（{b.get('bindings_total')}）")
    if "1200" not in text:
        issues.append("正文缺 1200 条绑定")
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            issues.append(f"载体不存在：{rel}")
        if rel not in text:
            issues.append(f"正文未点名载体：{rel}")
    for line in LINES:
        if line not in text:
            issues.append(f"达标线缺：{line}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py stats --check",
                "python scripts/geo_export.py --check",
                "python scripts/fde_sample_run.py --check"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "换模型" not in text:
        issues.append("缺「换模型不改中层」口径")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class FdeStackDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_stack_matches_contract(self):
        self.assertEqual([], stack_issues(self.text), "FDE 栈位文档不满足契约")

    def test_faces_live(self):
        faces = sorted(p.stem for p in INTEROP.glob("*.json"))
        self.assertEqual(12, len(faces))
        self.assertIn("a2a", faces)
        self.assertNotIn("mcp", faces)
        self.assertEqual(370, len(json.loads(CATALOG.read_text(encoding="utf-8"))["standards"]))
        self.assertEqual(1200,
                         int(json.loads(BINDING.read_text(encoding="utf-8"))["bindings_total"]))

    def test_contract_catches_mutations(self):
        """变异自证：缺面 / 回退 mcp.json 引用 / 缺标准数 / 缺达标线 / 缺命令。"""
        no_face = self.text.replace("cyclonedx", "cbor")
        self.assertTrue(any("cyclonedx" in i for i in stack_issues(no_face)))
        back = self.text.replace("A2A：", "results/interop/mcp.json / A2A：")
        self.assertTrue(any("mcp" in i for i in stack_issues(back)))
        old_n = self.text.replace("370", "360")
        self.assertTrue(any("370" in i for i in stack_issues(old_n)))
        no_line = self.text.replace("白盒", "白箱")
        self.assertTrue(any("白盒" in i for i in stack_issues(no_line)))
        no_cmd = self.text.replace("python scripts/geo_export.py --check", "geo 检查")
        self.assertTrue(any("geo_export" in i for i in stack_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_stack.md")


if __name__ == "__main__":
    unittest.main()
