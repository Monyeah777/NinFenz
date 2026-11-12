#!/usr/bin/env python3
"""P00 管线骨架契约：元管线必须「声明可解析、九槽稳定、派生实例在场、机检可指」。

为什么必须有：P00 是全部管线的派生模板（112 行：YAML 机读声明 + 运行规则），但此前零专属判据——
九槽层名是否稳定、flow 是否闭合成环、dependencies 是否仍是四条、P01/P90 两个在册实例是否还
引用本骨架，全靠人眼。实测本轮补的真缺口：无「读法/机检验」段、运行规则标题后缺空行、
派生三步没有「派生后怎么验」的出口。

范围：只判本文件的结构自洽与派生面同源（不改管线声明语义）。同族判据：
test_core_protocol_contract（01 §2 管线规范）/ test_registry_doc_contract（02 §5 层名）/
test_navigation_doc_contract（07 出厂）/ check28（IDL schema）/ conformance pipeline-dryrun。
契约：YAML 可解析且九槽名与 02 §5 一致、flow 九边闭环、dependencies 四边、P01/P90 实例在场且
回指 P00、机检映射 check 真实、读法段与运行规则在场、围栏配平。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import pipeline_loader  # noqa: E402

P00 = ROOT / "03_管线库" / "P00_通用文档生成管线.md"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
P90 = ROOT / "03_管线库" / "P90_结构装配管线.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
VERIFY = ROOT / "verify.sh"
SCHEMA = ROOT / "protocol" / "schema" / "pipeline.schema.json"
FENCE = chr(96) * 3

#: 九槽层名（层位 id 与层名的稳定契约；层名可被实例特化，但骨架本身必须稳定）
NINE_LAYERS = (("P00", "装载"), ("P10", "语境推进"), ("P20", "实体状态"),
               ("P30", "内容生产"), ("P40", "决策"), ("P50", "装配"),
               ("P60", "一致性"), ("P70", "素材"), ("P80", "输出"))
REQUIRED_MARKERS = ("## 读法（本文件怎么用、怎么验）", "## 运行规则", "派生后验收",
                    "check28", "check14", "pipeline-dryrun",
                    "protocol/schema/pipeline.schema.json", "02_联动注册表.md")


def load_text(path: Path = P00) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"P00 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("P00 为空")
    return text


def yaml_block(text: str) -> str:
    m = re.search(FENCE + r"ya?ml\s*\n(.*?)\n" + FENCE, text, re.S)
    return m.group(1) if m else ""


def layer_names_from_registry() -> list:
    """02 §5 挂载层的（层位 id, 层名）。"""
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    return re.findall(r"^  (P\d\d) (\S+?):", body, re.M)


def check_funcs(verify_text: str) -> set:
    return set(re.findall(r"^(check\d+)\(\)\{", verify_text, re.M))


def p00_issues(text: str) -> list:
    issues = []
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    parsed = pipeline_loader.parse_pipeline_md(text)
    if parsed is None:
        issues.append("管线 YAML 无法解析（frontmatter / 围栏 / 子集语法）")
    else:
        if parsed.id != "P00":
            issues.append(f"管线 id 应为 P00（实测 {parsed.id!r}）")
        if parsed.structure_type != "linear":
            issues.append(f"structure.type 应为 linear（实测 {parsed.structure_type!r}）")
        pairs = [(layer.id, layer.name) for layer in parsed.layers]
        if pairs != list(NINE_LAYERS):
            issues.append(f"九槽（id/层名）与骨架契约不一致：{pairs}")
        optional = {layer.id: bool(layer.optional) for layer in parsed.layers}
        for layer_id in ("P60", "P70"):
            if not optional.get(layer_id):
                issues.append(f"{layer_id} 应为 optional:true")
        if len(parsed.dependencies) != 4:
            issues.append(f"dependencies 应为 4 条（实测 {len(parsed.dependencies)}）")
        if sorted(parsed.tags) != sorted(["领域无关", "骨架", "元管线"]):
            issues.append(f"tags 不符合骨架契约：{parsed.tags}")
    block = yaml_block(text)
    if not block:
        issues.append("缺 Pipeline YAML 围栏")
    else:
        flow_part = block.split("\n  layers:", 1)[0]
        flow_edges = re.findall(r"- from: (P\d\d)\n\s+to: (P\d\d)", flow_part)
        if len(flow_edges) != 9:
            issues.append(f"flow 应为 9 条边（实测 {len(flow_edges)}）")
        expected_chain = [(NINE_LAYERS[i][0], NINE_LAYERS[i + 1][0]) for i in range(8)]
        expected_chain.append(("P80", "P00"))
        if flow_edges != expected_chain:
            issues.append(f"flow 未按九槽顺序闭环：{flow_edges}")
        if 'condition: =data_bus.round.phase == "roll"' not in block:
            issues.append("缺 P80→P00 回卷 condition（NFA-L 命令层）")
    registry_layers = layer_names_from_registry()
    if registry_layers != list(NINE_LAYERS):
        issues.append(f"02 §5 挂载层名与骨架不一致：{registry_layers}")
    for instance in (P01, P90):
        if not instance.is_file():
            issues.append(f"官方在册实例不在场：{instance.name}")
            continue
        body = instance.read_text(encoding="utf-8")
        if "P00_通用文档生成管线.md" not in body:
            issues.append(f"{instance.name} 未回指 P00 骨架")
    funcs = check_funcs(VERIFY.read_text(encoding="utf-8"))
    for num in ("28", "14"):
        if "check" + num not in funcs:
            issues.append(f"机检映射引用了不存在的检查：check{num}")
    if "pipeline-dryrun" not in text:
        issues.append("缺 pipeline-dryrun 机检映射")
    if not SCHEMA.is_file():
        issues.append("缺管线 schema：protocol/schema/pipeline.schema.json")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    if "## 运行规则\n\n" not in text:
        issues.append("运行规则标题后缺空行")
    return issues


class PipelineP00ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_p00_matches_contract(self):
        self.assertEqual([], p00_issues(self.text), "P00 不满足管线骨架契约")

    def test_nine_layers_match_registry(self):
        self.assertEqual(list(NINE_LAYERS), layer_names_from_registry(), "02 §5 层名漂移")
        parsed = pipeline_loader.parse_pipeline_md(self.text)
        self.assertIsNotNone(parsed, "P00 YAML 不可解析")
        self.assertEqual([(layer.id, layer.name) for layer in parsed.layers],
                         list(NINE_LAYERS))

    def test_contract_catches_mutations(self):
        """变异自证：层名漂移 / flow 缺边 / id 漂移 / 假 check / 删读法 / 围栏不配平 / 缺空行。"""
        rename = self.text.replace("name: 实体状态", "name: 状态", 1)
        self.assertTrue(any("九槽" in i for i in p00_issues(rename)))
        drop_edge = self.text.replace("      - from: P50\n        to: P60\n", "", 1)
        self.assertTrue(any("flow" in i for i in p00_issues(drop_edge)))
        bad_id = self.text.replace("  id: P00\n", "  id: P99\n", 1)
        self.assertTrue(any("id" in i for i in p00_issues(bad_id)))
        fake_check = self.text.replace("check28", "check99")
        self.assertTrue(any("check99" in i or "check28" in i
                            for i in p00_issues(fake_check)))
        no_guide = self.text.replace("## 读法（本文件怎么用、怎么验）", "## 前言")
        self.assertTrue(any("读法" in i for i in p00_issues(no_guide)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in p00_issues(odd)))
        no_blank = self.text.replace("## 运行规则\n\n- 本管线是", "## 运行规则\n- 本管线是", 1)
        self.assertTrue(any("空行" in i for i in p00_issues(no_blank)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_p00.md")


if __name__ == "__main__":
    unittest.main()
