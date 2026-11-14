#!/usr/bin/env python3
"""P90 结构装配管线契约：技术文档实例必须「techdoc 结构可解析、九层挂载与 02 §7.1 同源」。

为什么必须有：P90 是「扩展新领域三步」的闭环样例（P00 的 techdoc 派生实例），也是唯一用
`structure.type: techdoc` 的管线；02 §7 明写它是 P90 挂载与执行顺序的**真相源（I5）**。
此前零专属判据——九层层名/默认模块与 02 §7.1 是否逐层一致、techdoc 值域是否仍被 01 §2 承认，
全靠人眼。实测本轮补的真缺口：无读法/机检段、「## 全局挂载」「## 运行规则」前缺空行、
运行规则没写「与 02 §7.1 同源」判据。

范围：只判本文件的结构自洽与实例挂载同源（不改管线声明语义）。同族判据：
test_pipeline_p00_contract（骨架）/ test_pipeline_p01_contract（叙事实例）/
test_registry_doc_contract（02 §7）/ check28 / conformance pipeline-dryrun。
契约：YAML 可解析且 type=techdoc、九层 (id,name,optional,default,allowed) 与 02 §7.1 逐层一致、
flow 九边闭环、dependencies 四条、回指 P00 骨架、围栏与空行规整。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import pipeline_loader  # noqa: E402

P90 = ROOT / "03_管线库" / "P90_结构装配管线.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
PROTOCOL = ROOT / "01_核心协议.md"
VERIFY = ROOT / "verify.sh"
FENCE = chr(96) * 3

NINE_LAYERS = (("P00", "文档装载"), ("P10", "语境推进"), ("P20", "章节状态"),
               ("P30", "片段生产"), ("P40", "结构决策"), ("P50", "章节装配"),
               ("P60", "一致性"), ("P70", "规范素材"), ("P80", "文档输出"))
REQUIRED_MARKERS = ("## 读法（本文件怎么用、怎么验）", "## 全局挂载", "## 运行规则",
                    "同源判据", "02_联动注册表.md", "check28", "pipeline-dryrun",
                    "P00_通用文档生成管线.md", "techdoc", "M80", "M50", "M00")


def load_text(path: Path = P90) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"P90 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("P90 为空")
    return text


def yaml_block(text: str) -> str:
    m = re.search(FENCE + r"ya?ml\s*\n(.*?)\n" + FENCE, text, re.S)
    return m.group(1) if m else ""


def doc_mounts() -> dict:
    """02 §7.1 的 id → (层名, active, available)。"""
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("### 7.1 P90 挂载", 1)[1].split("\n### 7.2", 1)[0]
    out = {}
    for line in body.splitlines():
        m = re.match(r"^  (P\d\d) (\S+?):\s*\{active: \[(.*?)\], available: \[(.*?)\]\}", line)
        if not m:
            continue
        out[m.group(1)] = (m.group(2), [x.strip() for x in m.group(3).split(",") if x.strip()],
                           [x.strip() for x in m.group(4).split(",") if x.strip()])
    return out


def check_funcs(verify_text: str) -> set:
    return set(re.findall(r"^(check\d+)\(\)\{", verify_text, re.M))


def p90_issues(text: str, verify_text: str = None) -> list:
    if verify_text is None:
        verify_text = VERIFY.read_text(encoding="utf-8")
    issues = []
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    parsed = pipeline_loader.parse_pipeline_md(text)
    if parsed is None:
        issues.append("管线 YAML 无法解析")
        return issues
    if parsed.id != "P90":
        issues.append(f"管线 id 应为 P90（实测 {parsed.id!r}）")
    if parsed.structure_type != "techdoc":
        issues.append(f"structure.type 应为 techdoc（实测 {parsed.structure_type!r}）")
    pairs = [(layer.id, layer.name) for layer in parsed.layers]
    if pairs != list(NINE_LAYERS):
        issues.append(f"九层（id/层名）与 P90 实例契约不一致：{pairs}")
    optional = {layer.id: bool(layer.optional) for layer in parsed.layers}
    if optional.get("P60") is not True or optional.get("P70") is not True:
        issues.append("P60/P70 应为 optional:true（本实例的空/素材层）")
    if len(parsed.dependencies) != 4:
        issues.append(f"dependencies 应为 4 条（实测 {len(parsed.dependencies)}）")
    if "结构化装配" not in parsed.tags:
        issues.append(f"tags 缺「结构化装配」：{parsed.tags}")
    doc = doc_mounts()
    if len(doc) != 9:
        issues.append(f"02 §7.1 P90 挂载解析失败（{len(doc)} 层）")
    for layer in parsed.layers:
        got = doc.get(layer.id)
        if not got:
            issues.append(f"02 §7.1 缺层：{layer.id}")
            continue
        if got != (layer.name, list(layer.default_modules), list(layer.allowed_modules)):
            issues.append(f"{layer.id} 与 02 §7.1 文本不一致")
    if "techdoc" not in PROTOCOL.read_text(encoding="utf-8"):
        issues.append("01 §2 structure.type 值域未承认 techdoc（值域真源漂移）")
    block = yaml_block(text)
    if not block:
        issues.append("缺 Pipeline YAML 围栏")
    else:
        flow_part = block.split("\n  layers:", 1)[0]
        edges = re.findall(r"- from: (P\d\d)\n\s+to: (P\d\d)", flow_part)
        expected = [(NINE_LAYERS[i][0], NINE_LAYERS[i + 1][0]) for i in range(8)]
        expected.append(("P80", "P00"))
        if edges != expected:
            issues.append(f"flow 未按九层顺序闭环：{edges}")
        if 'condition: =data_bus.round.phase == "roll"' not in block:
            issues.append("缺 P80→P00 回卷 condition（NFA-L 命令层）")
    funcs = check_funcs(verify_text)
    if "check28" not in funcs:
        issues.append("机检映射引用了不存在的检查：check28")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    if FENCE + "\n## 全局挂载" in text or FENCE + "\n\n## 全局挂载" not in text:
        issues.append("全局挂载标题前缺空行")
    if "## 运行规则\n\n" not in text:
        issues.append("运行规则标题后缺空行")
    return issues


class PipelineP90ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()
        self.parsed = pipeline_loader.parse_pipeline_md(self.text)

    def test_p90_matches_contract(self):
        self.assertEqual([], p90_issues(self.text), "P90 不满足结构装配实例契约")

    def test_mounts_match_registry_section_7(self):
        doc = doc_mounts()
        self.assertGreaterEqual(len(doc), 9, "02 §7.1 解析失败")
        self.assertIsNotNone(self.parsed, "P90 YAML 不可解析")
        for layer in self.parsed.layers:
            self.assertEqual(doc[layer.id],
                             (layer.name, list(layer.default_modules),
                              list(layer.allowed_modules)), layer.id)

    def test_contract_catches_mutations(self):
        """变异自证：层名漂移 / 类型漂移 / 默认模块漂移 / 假 check / 围栏不配平 / 缺空行。"""
        rename = self.text.replace("name: 章节状态", "name: 状态", 1)
        self.assertTrue(any("九层" in i for i in p90_issues(rename)))
        wrong_type = self.text.replace("    type: techdoc", "    type: linear", 1)
        self.assertTrue(any("type" in i for i in p90_issues(wrong_type)))
        drift = self.text.replace("default_modules: [M90]", "default_modules: [M99]", 1)
        self.assertTrue(any("02 §7.1" in i for i in p90_issues(drift)))
        fake = self.text.replace("check28", "check99")
        self.assertTrue(any("check99" in i or "check28" in i
                            for i in p90_issues(fake)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in p90_issues(odd)))
        no_blank = self.text.replace(FENCE + "\n\n## 全局挂载",
                                     FENCE + "\n## 全局挂载", 1)
        self.assertTrue(any("空行" in i for i in p90_issues(no_blank)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_p90.md")


if __name__ == "__main__":
    unittest.main()
