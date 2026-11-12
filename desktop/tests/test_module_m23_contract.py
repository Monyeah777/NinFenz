#!/usr/bin/env python3
"""M23 可见性边界模块契约：零事件 + cognition.filter 接口面，且依赖面与 02 §4 对账。

为什么必须有：M23 是「消费方可知」原则的系统侧保障，零事件、仅经 cognition.filter 接口面
对外裁剪素材。此前无判据保证：零事件模块没有退回空契约、接口名与 01 §1.1 示例一致、
inputs 依赖面与 02 §4 depends 逐项一致、P20 挂载与 P01 default 对账。本轮无字段缺项，
价值在把「可见性接口面 + 依赖对账 + 引用块被依赖对账」立成机检断言。

范围：只判本模块文档结构自洽与跨源同源（不改可见性语义）。同族判据：
test_module_m12/m20_contract（零事件模板）/ test_module_m00/m10_contract（通用类模板）/
test_registry_doc_contract（02 §2/§4/§5/§6）/ test_schema_lint（check28）/ check16。
契约：五段结构、零事件 + interfaces [cognition.filter]、io_types 规则推导、registry 与 02 §2 一致、
02 §4 depends/depended_by 与引用块对账、02 §5/§6 在册、L2 可证、接口签名与 Phase 2 迁移口径在场。
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

M23 = ROOT / "04_模块库" / "通用类" / "M23_可见性边界.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
PROTOCOL = ROOT / "01_核心协议.md"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 可见性模型", "## 3. 多重真相支持",
                     "## 4. 联动", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "I3", "I4",
                    "check16", "check28", "零事件模块", "cognition.filter", "visibility.filter")


def load_text(path: Path = M23) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M23 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M23 为空")
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
        if item.get("id") == "M23":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M23 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def dependency_lists() -> dict:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 4. 依赖关系", 1)[1].split("\n## 5.", 1)[0]
    m = re.search(r"  M23:\n    depends: \[(.*?)\]\n    depended_by: \[(.*?)\]", body)
    if not m:
        return {}
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    return {"depends": split(m.group(1)), "depended_by": split(m.group(2))}


def p20_default() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    m = re.search(r"^  P20 [^:]+:\s*\{default: \[(.*?)\]", body, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def execution_mentions_m23() -> int:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return body.count("M23")


def m23_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    if header.get("id") != "M23":
        issues.append(f"机读块 id 应为 M23（实测 {header.get('id')!r}）")
    if (header.get("publish") or []) != [] or (header.get("subscribe") or []) != []:
        issues.append("零事件模块应显式双空")
    if (header.get("interfaces") or []) != ["cognition.filter"]:
        issues.append(f"interfaces 应为 [cognition.filter]（实测 {header.get('interfaces')}）")
    if (header.get("outputs") or []) != []:
        issues.append(f"outputs 应为空（只裁剪不产出槽）：{header.get('outputs')}")
    parsed_io = io_types.parse_io_types(text)
    if parsed_io is None:
        issues.append("缺 io_types 类型面")
    else:
        ev_types = io_types.event_field_types(str(ROOT))
        expected = io_types.derive(header.get("outputs") or [],
                                   header.get("inputs") or [], ev_types)
        if parsed_io != expected:
            issues.append("io_types 未按「同名事件字段」规则推导")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    if quote.get("发布") not in (None, "无"):
        issues.append(f"零事件模块引用块发布应为「无」：{quote.get('发布')!r}")
    reg = registry_module()
    if not reg:
        issues.append("registry.json 缺 M23 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P20" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P20/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M23 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P20" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
    deps = dependency_lists()
    if not deps:
        issues.append("02 §4 缺 M23 依赖关系段")
    else:
        if deps.get("depends") != header.get("inputs"):
            issues.append("02 §4 depends 与机读 inputs 不一致："
                           f"{deps.get('depends')} ≠ {header.get('inputs')}")
        quote_dep = quote.get("被依赖") or ""
        quote_ids = [x.strip().split("（")[0].strip() for x in quote_dep.split("、") if x.strip()]
        if quote_ids != deps.get("depended_by"):
            issues.append(f"引用块被依赖与 02 §4 不一致：{quote_ids} ≠ {deps.get('depended_by')}")
    if "M23" not in p20_default():
        issues.append(f"02 §5 P20 default 应含 M23：{p20_default()}")
    if execution_mentions_m23() < 1:
        issues.append("02 §6 执行顺序应含 M23")
    if "cognition.filter(consumer, material)" not in text:
        issues.append("§4 缺 cognition.filter(consumer, material) 接口签名")
    if "visibility.filter" not in text:
        issues.append("§4 缺 Phase 2 迁移目标 visibility.filter")
    p01 = P01.read_text(encoding="utf-8")
    default = re.search(r"id: P20[\s\S]*?default_modules: \[([^\]]*)\]", p01)
    if not default or "M23" not in default.group(1):
        issues.append("L2 不可证：P01 P20 default_modules 未引用 M23")
    basis = PROTOCOL.read_text(encoding="utf-8")
    if "cognition.filter" not in basis:
        issues.append("01 §1.1 缺 cognition.filter 接口面依据")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM23ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m23_matches_contract(self):
        self.assertEqual([], m23_issues(self.text), "M23 不满足模块契约")

    def test_zero_event_interface_and_dependencies(self):
        header = mc_fields(self.text)
        self.assertEqual([], header.get("publish"))
        self.assertEqual([], header.get("subscribe"))
        self.assertEqual(["cognition.filter"], header.get("interfaces"))
        self.assertEqual(dependency_lists().get("depends"), header.get("inputs"))

    def test_contract_catches_mutations(self):
        """变异自证：interfaces 清空 / 依赖漂移 / 接口名漂移 / 被依赖漂移 / 缺段 / 围栏。"""
        no_iface = self.text.replace("  interfaces: [cognition.filter]", "  interfaces: []", 1)
        self.assertTrue(any("interfaces" in i for i in m23_issues(no_iface)))
        drift = self.text.replace("  inputs: [M00]", "  inputs: [M00, M13]", 1)
        self.assertTrue(any("depends" in i for i in m23_issues(drift)))
        bad_iface = self.text.replace("  interfaces: [cognition.filter]",
                                      "  interfaces: [visibility.filter]", 1)
        self.assertTrue(any("interfaces" in i for i in m23_issues(bad_iface)))
        bad_dep = self.text.replace("｜被依赖：M13、事件:M22｜", "｜被依赖：M13｜", 1)
        self.assertTrue(any("被依赖" in i for i in m23_issues(bad_dep)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m23_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m23_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m23.md")


if __name__ == "__main__":
    unittest.main()
