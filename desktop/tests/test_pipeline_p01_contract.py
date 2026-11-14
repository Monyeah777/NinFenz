#!/usr/bin/env python3
"""P01 标准管线契约：官方默认装配实例必须「声明可解析、九层挂载三处同源、P00 骨架回指」。

为什么必须有：P01 是官方默认活跃管线（YAML 机读声明 + 运行规则），层内 default/available 是官方
核心 13 件的装配事实，同时被 02 §5 挂载点与 registry.json mount_points 双源引用——三处任一处
漂移，Runtime 与文档就会各读各的。此前零专属判据。实测本轮补的真缺口：无读法/机检段、
运行规则标题前后缺空行、运行规则没写「三处同源」判据。

范围：只判本文件的结构自洽与挂载面同源（不改管线声明语义）。同族判据：
test_pipeline_p00_contract（骨架）/ test_registry_doc_contract（02 §5）/
test_navigation_doc_contract（07 出厂）/ check13（文档 ↔ json）/ conformance pipeline-dryrun。
契约：YAML 可解析、九层 (id,name,optional,default,allowed) 与 registry.json mount_points 逐层一致、
与 02 §5 文本逐层一致、flow 九边闭环、dependencies 四条、回指 P00 骨架、围栏与空行规整。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import pipeline_loader  # noqa: E402

P01 = ROOT / "03_管线库" / "P01_标准管线.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
VERIFY = ROOT / "verify.sh"
FENCE = chr(96) * 3

NINE_LAYERS = (("P00", "装载"), ("P10", "语境推进"), ("P20", "实体状态"),
               ("P30", "内容生产"), ("P40", "决策"), ("P50", "装配"),
               ("P60", "一致性"), ("P70", "素材"), ("P80", "输出"))
REQUIRED_MARKERS = ("## 读法（本文件怎么用、怎么验）", "## 运行规则", "同源判据",
                    "02_联动注册表.md", "registry.json", "check13", "check28",
                    "pipeline-dryrun", "P00_通用文档生成管线.md")


def load_text(path: Path = P01) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"P01 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("P01 为空")
    return text


def yaml_block(text: str) -> str:
    m = re.search(FENCE + r"ya?ml\s*\n(.*?)\n" + FENCE, text, re.S)
    return m.group(1) if m else ""


def registry_mounts() -> dict:
    return json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))["mount_points"]


def doc_mounts() -> dict:
    """02 §5 的 id → (层名, default, available)。"""
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    out = {}
    for line in body.splitlines():
        m = re.match(r"^  (P\d\d) (\S+?):\s*\{default: \[(.*?)\], available: \[(.*?)\]\}", line)
        if not m:
            continue
        out[m.group(1)] = (m.group(2), [x.strip() for x in m.group(3).split(",") if x.strip()],
                           [x.strip() for x in m.group(4).split(",") if x.strip()])
    return out


def check_funcs(verify_text: str) -> set:
    return set(re.findall(r"^(check\d+)\(\)\{", verify_text, re.M))


def p01_issues(text: str, verify_text: str = None) -> list:
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
    if parsed.id != "P01":
        issues.append(f"管线 id 应为 P01（实测 {parsed.id!r}）")
    if parsed.structure_type != "linear":
        issues.append(f"structure.type 应为 linear（实测 {parsed.structure_type!r}）")
    pairs = [(layer.id, layer.name) for layer in parsed.layers]
    if pairs != list(NINE_LAYERS):
        issues.append(f"九层（id/层名）与骨架契约不一致：{pairs}")
    if len(parsed.dependencies) != 4:
        issues.append(f"dependencies 应为 4 条（实测 {len(parsed.dependencies)}）")
    if sorted(parsed.tags) != sorted(["官方核心", "标准装配", "线性"]):
        issues.append(f"tags 不符合实例契约：{parsed.tags}")
    mounts = registry_mounts()
    for layer in parsed.layers:
        got = mounts.get(layer.id)
        if not got:
            issues.append(f"registry.json mount_points 缺层：{layer.id}")
            continue
        if (got.get("name") != layer.name
                or list(got.get("default") or []) != list(layer.default_modules)
                or list(got.get("available") or []) != list(layer.allowed_modules)
                or bool(got.get("optional")) != bool(layer.optional)):
            issues.append(f"{layer.id} 与 registry.json mount_points 不一致")
    doc = doc_mounts()
    if len(doc) != 9:
        issues.append(f"02 §5 挂载点解析失败（{len(doc)} 层）")
    for layer in parsed.layers:
        got = doc.get(layer.id)
        if not got:
            issues.append(f"02 §5 缺层：{layer.id}")
            continue
        if got != (layer.name, list(layer.default_modules), list(layer.allowed_modules)):
            issues.append(f"{layer.id} 与 02 §5 文本不一致")
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
    for num in ("13", "28"):
        if "check" + num not in funcs:
            issues.append(f"机检映射引用了不存在的检查：check{num}")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    if FENCE + "\n## 运行规则" in text:
        issues.append("运行规则标题前缺空行")
    if "## 运行规则\n\n" not in text:
        issues.append("运行规则标题后缺空行")
    return issues


class PipelineP01ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()
        self.parsed = pipeline_loader.parse_pipeline_md(self.text)

    def test_p01_matches_contract(self):
        self.assertEqual([], p01_issues(self.text), "P01 不满足标准管线契约")

    def test_mounts_are_three_way_consistent(self):
        mounts = registry_mounts()
        doc = doc_mounts()
        self.assertGreaterEqual(len(doc), 9, "02 §5 解析失败")
        self.assertIsNotNone(self.parsed, "P01 YAML 不可解析")
        for layer in self.parsed.layers:
            got = mounts[layer.id]
            self.assertEqual(got["name"], layer.name, layer.id)
            self.assertEqual(list(got["default"]), list(layer.default_modules), layer.id)
            self.assertEqual(list(got["available"]), list(layer.allowed_modules), layer.id)
            self.assertEqual(doc[layer.id],
                             (layer.name, list(layer.default_modules),
                              list(layer.allowed_modules)), layer.id)

    def test_contract_catches_mutations(self):
        """变异自证：默认模块漂移 / 层名漂移 / 假 check / 围栏不配平 / 缺空行。"""
        drift = self.text.replace("default_modules: [M00]", "default_modules: [M99]", 1)
        self.assertTrue(any("registry" in i or "02 §5" in i for i in p01_issues(drift)))
        rename = self.text.replace("name: 实体状态", "name: 状态", 1)
        self.assertTrue(any("九层" in i for i in p01_issues(rename)))
        fake = self.text.replace("check13", "check99")
        self.assertTrue(any("check99" in i or "check13" in i
                            for i in p01_issues(fake)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in p01_issues(odd)))
        no_blank = self.text.replace(FENCE + "\n\n## 运行规则",
                                     FENCE + "\n## 运行规则", 1)
        self.assertTrue(any("空行" in i for i in p01_issues(no_blank)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_p01.md")


if __name__ == "__main__":
    unittest.main()
