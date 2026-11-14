#!/usr/bin/env python3
"""M00 数据槽总线模块契约：纯内部基座豁免 + 冻结槽位面必须与 world_slots.json 同源。

为什么必须有：M00 是唯一「合法 interfaces: []」的纯数据槽基座（01 §1.1 明文豁免），同时它的
§4 冻结兼容槽位是 community 107 包与管线 condition 的寻址面（在 protocol/world_slots.json 在册）。
此前没有判据保证：豁免声明没有被误改成空壳接口、冻结路径与 world_slots.json 逐项一致、
被依赖清单与 02 §4 依赖关系对账。本轮无字段缺项，价值在把「豁免依据 + 冻结面 + 依赖对账」
立成机检断言。

范围：只判本模块文档的结构自洽与跨源同源（不改总线语义）。同族判据：
test_module_m90/m22/m20/m12_contract（同模板）/ test_registry_doc_contract（02 §2/§4/§5/§6）/
test_schema_lint（check28）/ check16 / check24（world_slots 面）。
契约：五段结构、零事件+零接口豁免依据在场、registry 与 02 §2 一致、02 §4 被依赖清单对账、
冻结槽位四组与 world_slots.json 逐项在场、io_types 空推导、schema_version 与 phase 枚举在场。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import io_types  # noqa: E402

M00 = ROOT / "04_模块库" / "通用类" / "M00_数据槽总线.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
PROTOCOL = ROOT / "01_核心协议.md"
WORLD_SLOTS = ROOT / "protocol" / "world_slots.json"
FENCE = chr(96) * 3

FROZEN_PATHS = ("data_bus.active_pipeline", "data_bus.round.phase",
                "data_bus.round.phase_trace", "WorldState.time", "PlayerState.memories")
REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 总线", "## 3. 槽位模型",
                     "## 4. 冻结兼容槽位", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "纯内部基座豁免", "I3", "I4",
                    "check16", "check28", "world_slots.json", "data_bus", "schema_version")


def load_text(path: Path = M00) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M00 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M00 为空")
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
        if item.get("id") == "M00":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M00 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def dependency_lists() -> dict:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 4. 依赖关系", 1)[1].split("\n## 5.", 1)[0]
    m = re.search(r"  M00:\n    depends: \[(.*?)\]\n    depended_by: \[(.*?)\]", body)
    if not m:
        return {}
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    return {"depends": split(m.group(1)), "depended_by": split(m.group(2))}


def p00_default() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    m = re.search(r"^  P00 [^:]+:\s*\{default: \[(.*?)\]", body, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def execution_mentions_m00() -> int:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return body.count("M00")


def world_slots_text() -> str:
    return WORLD_SLOTS.read_text(encoding="utf-8")


def m00_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    if header.get("id") != "M00":
        issues.append(f"机读块 id 应为 M00（实测 {header.get('id')!r}）")
    if (header.get("publish") or []) != [] or (header.get("subscribe") or []) != []:
        issues.append("纯内部基座应显式双空事件面")
    if (header.get("interfaces") or []) != []:
        issues.append(f"纯内部基座 interfaces 应为 []（01 §1.1 豁免）：{header.get('interfaces')}")
    if (header.get("inputs") or []) != [] or (header.get("outputs") or []) != []:
        issues.append("inputs/outputs 应为空（总线基座不声明收发）")
    parsed_io = io_types.parse_io_types(text)
    if parsed_io is None:
        issues.append("缺 io_types 类型面")
    elif parsed_io != {"outputs": {}, "inputs": {}}:
        issues.append(f"io_types 应为空推导：{parsed_io}")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    reg = registry_module()
    if not reg:
        issues.append("registry.json 缺 M00 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P00" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P00/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M00 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P00" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
        if "装载" not in row[4]:
            issues.append(f"02 §2 应使用 P00 层名「装载」：{row[4]}")
    deps = dependency_lists()
    if not deps:
        issues.append("02 §4 缺 M00 依赖关系段")
    else:
        if deps.get("depends") != []:
            issues.append(f"02 §4 M00 depends 应为空：{deps.get('depends')}")
        quote_dep = quote.get("被依赖") or ""
        quote_ids = [x.strip().split("（")[0].strip() for x in quote_dep.split("、") if x.strip()]
        if quote_ids != deps.get("depended_by"):
            issues.append(f"引用块被依赖与 02 §4 不一致：{quote_ids} ≠ {deps.get('depended_by')}")
    if "M00" not in p00_default():
        issues.append(f"02 §5 P00 default 应含 M00：{p00_default()}")
    if execution_mentions_m00() < 1:
        issues.append("02 §6 执行顺序应含 M00")
    ws = world_slots_text()
    for path in FROZEN_PATHS:
        if path not in text:
            issues.append(f"§4 冻结槽位缺路径：{path}")
        if path not in ws:
            issues.append(f"world_slots.json 缺冻结路径：{path}")
    if '"schema_version"' not in ws and "schema_version" not in ws:
        issues.append("world_slots.json 缺 schema_version")
    if "data_bus.round.phase" in text:
        for phase in ("begin", "run", "end", "archive", "roll"):
            if phase not in text:
                issues.append(f"round.phase 相位枚举缺 {phase}")
    basis = PROTOCOL.read_text(encoding="utf-8")
    if "M00 纯数据槽基座" not in basis:
        issues.append("01 缺纯内部基座豁免依据（§1.6.11 迁移说明）")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM00ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m00_matches_contract(self):
        self.assertEqual([], m00_issues(self.text), "M00 不满足模块契约")

    def test_frozen_slots_match_world_slots(self):
        ws = world_slots_text()
        for path in FROZEN_PATHS:
            self.assertIn(path, self.text, path)
            self.assertIn(path, ws, path)

    def test_dependency_lists_match_registry_section_4(self):
        deps = dependency_lists()
        self.assertTrue(deps, "02 §4 缺 M00 依赖段")
        self.assertEqual([], deps["depends"])
        quote_dep = quote_fields(self.text).get("被依赖") or ""
        quote_ids = [x.strip().split("（")[0].strip() for x in quote_dep.split("、") if x.strip()]
        self.assertEqual(deps["depended_by"], quote_ids)

    def test_contract_catches_mutations(self):
        """变异自证：interfaces 非空 / id 漂移 / 被依赖漂移 / 冻结路径缺失 / 相位缺失 / 围栏。"""
        bad_iface = self.text.replace("  interfaces: []", "  interfaces: [bus]", 1)
        self.assertTrue(any("interfaces" in i for i in m00_issues(bad_iface)))
        bad_id = self.text.replace("  id: M00", "  id: M99", 1)
        self.assertTrue(any("id" in i for i in m00_issues(bad_id)))
        bad_dep = self.text.replace("通用:M10、M50、M23、M24、M20、M90（核心",
                                 "通用:M10、M50、M23、M24、M20（核心", 1)
        self.assertTrue(any("被依赖" in i for i in m00_issues(bad_dep)))
        no_path = self.text.replace("PlayerState.memories",
                                  "PlayerState.memory")
        self.assertTrue(any("冻结槽位" in i or "world_slots" in i for i in m00_issues(no_path)))
        no_phase = self.text.replace("begin/run/end/archive/roll", "begin/run/end", 1)
        self.assertTrue(any("相位" in i for i in m00_issues(no_phase)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m00_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m00.md")


if __name__ == "__main__":
    unittest.main()
