#!/usr/bin/env python3
"""M90 结构装配模块契约：机读块 ⇄ §2 Module 声明 ⇄ registry/02 ⇄ P90 管线 四源同源。

为什么必须有：M90 是「无损接入非叙事领域模块」的实证件——它同时以 machine_contract（九键投影）
与 §2 Module 声明（01 §1 模块协议全集）两种形态描述同一契约，并挂在 P90 的 P00–P70 八层。
此前没有判据保证两种声明逐项一致、也没有判据保证 P90 管线文件与 02 §7.1 的挂载对账。
实测本轮无字段缺项（三事件均在册、io_types 与规则推导一致），价值在把「双声明同源 + 八层挂载」
立成机检断言，防止 M90 与 P90/02 三方漂移。

范围：只判本模块文档的结构自洽与跨源同源（不改装配语义）。同族判据：
test_module_m06/m08/m12/m13/m20/m22_contract（同模板）/ test_pipeline_p90_contract（管线侧）/
test_registry_doc_contract（02 §2/§7.1）/ test_schema_lint（check28）/ check16。
契约：七段结构、机读块与 §2 Module 逐项一致、registry/02 §2 一致、02 §7.1 八层挂载对账、
P90 管线文件九层 default 模块对账、io_types 按规则推导、三事件在册、引用块一致。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import io_types, pipeline_loader  # noqa: E402

M90 = ROOT / "04_模块库" / "技术文档类" / "M90_结构装配.md"
P90 = ROOT / "03_管线库" / "P90_结构装配管线.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 协议声明", "## 3. 数据槽契约",
                     "## 4. 事件联动", "## 5. 核心逻辑", "## 6. 不变式遵守",
                     "## 7. 与装配管线的关系")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "四形态", "asset_get", "I3", "I4", "I5",
                    "protocol/event_registry.json", "check16", "check28", "不编造",
                    "DocState", "doc_structure_ready", "intent_received")
PUBLISH = ["doc_delta_committed", "doc_structure_ready"]


def load_text(path: Path = M90) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M90 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M90 为空")
    return text


def mc_block(text: str) -> str:
    m = re.search(FENCE + "yaml\n(machine_contract:.*?)\n" + FENCE, text, re.S)
    return m.group(1) if m else ""


def mc_fields(text: str) -> dict:
    block = mc_block(text)
    out = {}
    for key in ("id", "name", "category", "layer"):
        m = re.search(r"^  " + key + r": (.+)$", block, re.M)
        if m:
            out[key] = m.group(1).strip().strip('"')
    for key in ("publish", "subscribe", "inputs", "outputs", "interfaces"):
        m = re.search(r"^\s+" + key + r": \[(.*?)\]", block, re.M)
        if m:
            out[key] = [x.strip() for x in m.group(1).split(",") if x.strip()]
    return out


def module_decl(text: str) -> dict:
    """§2 的 01 §1 Module 声明（人读全集）。"""
    m = re.search(r"## 2\. 协议声明[\s\S]*?" + FENCE + "yaml\n(Module:.*?)\n" + FENCE,
                  text, re.S)
    if not m:
        return {}
    block = m.group(1)
    out = {}
    for key in ("id", "name", "layer"):
        mm = re.search(r"^  " + key + r": (.+)$", block, re.M)
        if mm:
            out[key] = mm.group(1).strip().strip('"')
    for key in ("publish", "subscribe", "inputs", "outputs"):
        mm = re.search(r"^\s+" + key + r": \[(.*?)\]", block, re.M)
        if mm:
            out[key] = [x.strip() for x in mm.group(1).split(",") if x.strip()]
    return out


def quote_fields(text: str) -> dict:
    line = next((ln for ln in text.splitlines() if ln.startswith("> 类别：")), "")
    out = {}
    for key in ("类别", "来源", "挂载点", "依赖", "被依赖", "发布"):
        m = re.search(key + r"：([^｜|]+)", line)
        if m:
            out[key] = m.group(1).strip()
    return out


def registry_module() -> dict:
    data = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    for item in data["modules"]:
        if item.get("id") == "M90":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M90 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def event_registry() -> dict:
    return json.loads((ROOT / "protocol" / "event_registry.json")
                      .read_text(encoding="utf-8"))["events"]


def p90_mounts() -> dict:
    """02 §7.1 的层 id → (active, available)。"""
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("### 7.1 P90 挂载", 1)[1].split("\n### 7.2", 1)[0]
    out = {}
    for line in body.splitlines():
        m = re.match(r"^  (P\d\d) [^:]+:\s*\{active: \[(.*?)\], available: \[(.*?)\]\}", line)
        if m:
            out[m.group(1)] = ([x.strip() for x in m.group(2).split(",") if x.strip()],
                               [x.strip() for x in m.group(3).split(",") if x.strip()])
    return out


def m90_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    decl = module_decl(text)
    if header.get("id") != "M90":
        issues.append(f"机读块 id 应为 M90（实测 {header.get('id')!r}）")
    if not decl:
        issues.append("§2 缺 Module 声明块")
    else:
        for key in ("id", "name", "layer", "inputs", "outputs", "publish", "subscribe"):
            if header.get(key) != decl.get(key):
                issues.append("机读块与 §2 Module 不一致："
                               f"{key} {header.get(key)!r} ≠ {decl.get(key)!r}")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    if sorted(header.get("publish") or []) != PUBLISH:
        issues.append(f"publish 应为结构事件两件：{header.get('publish')}")
    if header.get("subscribe") != ["intent_received"]:
        issues.append(f"subscribe 应为 intent_received：{header.get('subscribe')}")
    parsed_io = io_types.parse_io_types(text)
    if parsed_io is None:
        issues.append("缺 io_types 类型面")
    else:
        ev_types = io_types.event_field_types(str(ROOT))
        expected = io_types.derive(header.get("outputs") or [],
                                   header.get("inputs") or [], ev_types)
        if parsed_io != expected:
            issues.append("io_types 未按「同名事件字段」规则推导")
    reg = registry_module()
    if not reg:
        issues.append("registry.json 缺 M90 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P90" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P90/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M90 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P90" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
    events = event_registry()
    for name in (header.get("publish") or []) + (header.get("subscribe") or []):
        if name not in events:
            issues.append(f"事件未在 event_registry 在册：{name}")
    mounts = p90_mounts()
    if len(mounts) != 9:
        issues.append(f"02 §7.1 P90 挂载解析失败（{len(mounts)} 层）")
    for layer_id in ("P00", "P10", "P20", "P30", "P40", "P50", "P60", "P70"):
        active, available = mounts.get(layer_id, ([], []))
        if "M90" not in active or "M90" not in available:
            issues.append(f"02 §7.1 {layer_id} 的 active/available 应含 M90：{active}/{available}")
    p80 = mounts.get("P80", ([], []))
    if p80[0] != ["M80"] or "M90" in p80[0]:
        issues.append(f"02 §7.1 P80 应为 M80 唯一门：{p80}")
    parsed_p90 = pipeline_loader.parse_pipeline_md(P90.read_text(encoding="utf-8"))
    if parsed_p90 is None:
        issues.append("P90 管线不可解析")
    else:
        for layer in parsed_p90.layers:
            want = ["M90"] if layer.id != "P80" else ["M80"]
            if list(layer.default_modules) != want:
                issues.append(f"P90 {layer.id} default 应为 {want}：{list(layer.default_modules)}")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM90ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m90_matches_contract(self):
        self.assertEqual([], m90_issues(self.text), "M90 不满足模块契约")

    def test_machine_block_and_module_decl_are_same_source(self):
        header = mc_fields(self.text)
        decl = module_decl(self.text)
        self.assertTrue(decl, "缺 §2 Module 声明块")
        for key in ("id", "name", "layer", "inputs", "outputs", "publish", "subscribe"):
            self.assertEqual(header.get(key), decl.get(key), key)

    def test_p90_mounts_cover_eight_layers(self):
        mounts = p90_mounts()
        for layer_id in ("P00", "P10", "P20", "P30", "P40", "P50", "P60", "P70"):
            self.assertIn("M90", mounts[layer_id][0], layer_id)
        self.assertEqual(["M80"], mounts["P80"][0])

    def test_contract_catches_mutations(self):
        """变异自证：§2 漂移 / publish 漂移 / 未知事件 / io_types 编造 / 缺段 / 围栏。"""
        drift = self.text.replace("  outputs: [DocState, doc_delta] # 结构状态 + 章节增量",
                                  "  outputs: [DocState] # 结构状态 + 章节增量", 1)
        self.assertTrue(any("§2 Module" in i for i in m90_issues(drift)))
        bad_publish = self.text.replace("    publish: [doc_structure_ready, doc_delta_committed]",
                                        "    publish: [doc_structure_ready, x_event]", 1)
        self.assertTrue(any("§2 Module" in i or "在册" in i for i in m90_issues(bad_publish)))
        fake_type = self.text.replace("DocState: untyped", "DocState: string", 1)
        self.assertTrue(any("io_types" in i for i in m90_issues(fake_type)))
        no_section = self.text.replace("## 7. 与装配管线的关系", "## 7. 管线关系")
        self.assertTrue(any("缺段" in i for i in m90_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m90_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m90.md")


if __name__ == "__main__":
    unittest.main()
