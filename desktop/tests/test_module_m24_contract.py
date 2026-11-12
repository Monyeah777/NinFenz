#!/usr/bin/env python3
"""M24 规则组合模块契约：零事件 + resolve 接口面，依赖面与 02 §4 对账，且不虚构输出 token。

为什么必须有：M24 是「组合/推导规则」的唯一结算入口，零事件、仅经 resolve 接口对外判定；
按 01 §1.1「未显式声明的数据槽字段写 []」，其 outputs 保持 []（槽位字段名待域包声明后再登记，
不虚构 token）。此前无判据保证：零事件模块没有退回空契约、接口名与 01 §1.1 示例一致、
inputs/depended_by 与 02 §4 逐项一致、P70 挂载与 P01 default 对账、规则表结构键在场。

范围：只判本模块文档结构自洽与跨源同源（不改规则语义）。同族判据：
test_module_m23/m12/m20_contract（零事件模板）/ test_module_m00/m10_contract（通用类模板）/
test_registry_doc_contract（02 §2/§4/§5/§6）/ test_schema_lint（check28）/ check16。
契约：五段结构、零事件 + interfaces [resolve] + outputs 空、io_types 规则推导、
registry 与 02 §2 一致、
02 §4 depends/depended_by 与引用块对账、02 §5/§6 在册、L2 可证、resolve 签名与规则表结构键在场。
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

M24 = ROOT / "04_模块库" / "通用类" / "M24_规则组合.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
PROTOCOL = ROOT / "01_核心协议.md"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 规则注册表", "## 3. 判定流程",
                     "## 4. 扩展约定", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "I4", "asset_get",
                    "check16", "check28", "零事件模块", "resolve", "不虚构")
RULE_KEYS = ("input:", "output:", "conditions:", "source:")


def load_text(path: Path = M24) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M24 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M24 为空")
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
        if item.get("id") == "M24":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M24 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def dependency_lists() -> dict:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 4. 依赖关系", 1)[1].split("\n## 5.", 1)[0]
    m = re.search(r"  M24:\n    depends: \[(.*?)\]\n    depended_by: \[(.*?)\]", body)
    if not m:
        return {}
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    return {"depends": split(m.group(1)), "depended_by": split(m.group(2))}


def p70_default() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    m = re.search(r"^  P70 [^:]+:\s*\{default: \[(.*?)\]", body, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def execution_mentions_m24() -> int:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return body.count("M24")


def m24_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    if header.get("id") != "M24":
        issues.append(f"机读块 id 应为 M24（实测 {header.get('id')!r}）")
    if (header.get("publish") or []) != [] or (header.get("subscribe") or []) != []:
        issues.append("零事件模块应显式双空")
    if (header.get("interfaces") or []) != ["resolve"]:
        issues.append(f"interfaces 应为 [resolve]（实测 {header.get('interfaces')}）")
    if (header.get("outputs") or []) != []:
        issues.append(f"outputs 应为空（未显式声明槽字段不虚构 token）：{header.get('outputs')}")
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
        issues.append("registry.json 缺 M24 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P70" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P70/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M24 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P70" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
    deps = dependency_lists()
    if not deps:
        issues.append("02 §4 缺 M24 依赖关系段")
    else:
        if deps.get("depends") != header.get("inputs"):
            issues.append("02 §4 depends 与机读 inputs 不一致")
        quote_dep = quote.get("被依赖") or ""
        quote_ids = [x.strip() for x in quote_dep.split("、")
                     if x.strip() and x.strip() != "无"]
        if quote_ids != deps.get("depended_by"):
            issues.append(f"引用块被依赖与 02 §4 不一致：{quote_ids} ≠ {deps.get('depended_by')}")
    if "M24" not in p70_default():
        issues.append(f"02 §5 P70 default 应含 M24：{p70_default()}")
    if execution_mentions_m24() < 1:
        issues.append("02 §6 执行顺序应含 M24")
    if "resolve(inputA, inputB)" not in text:
        issues.append("§3 缺 resolve(inputA, inputB) 接口签名")
    for key in RULE_KEYS:
        if key not in text:
            issues.append(f"§2 规则表缺结构键：{key}")
    for behavior in ("返回 null", "blocked"):
        if behavior not in text:
            issues.append(f"§3 缺判定行为：{behavior}")
    p01 = P01.read_text(encoding="utf-8")
    default = re.search(r"id: P70[\s\S]*?default_modules: \[([^\]]*)\]", p01)
    if not default or "M24" not in default.group(1):
        issues.append("L2 不可证：P01 P70 default_modules 未引用 M24")
    basis = PROTOCOL.read_text(encoding="utf-8")
    if "resolve" not in basis:
        issues.append("01 §1.1 缺 resolve 接口面依据")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM24ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m24_matches_contract(self):
        self.assertEqual([], m24_issues(self.text), "M24 不满足模块契约")

    def test_zero_event_resolve_interface_and_dependencies(self):
        header = mc_fields(self.text)
        self.assertEqual([], header.get("publish"))
        self.assertEqual([], header.get("subscribe"))
        self.assertEqual(["resolve"], header.get("interfaces"))
        self.assertEqual([], header.get("outputs"))
        self.assertEqual(dependency_lists().get("depends"), header.get("inputs"))

    def test_contract_catches_mutations(self):
        """变异自证：interfaces 清空 / 依赖漂移 / 虚构 outputs / 被依赖漂移 / 缺签名 / 围栏。"""
        no_iface = self.text.replace("  interfaces: [resolve]", "  interfaces: []", 1)
        self.assertTrue(any("interfaces" in i for i in m24_issues(no_iface)))
        drift = self.text.replace("  inputs: [M00]", "  inputs: [M00, M13]", 1)
        self.assertTrue(any("depends" in i for i in m24_issues(drift)))
        fake_out = self.text.replace("  outputs: []", "  outputs: [combination_result]", 1)
        self.assertTrue(any("outputs" in i for i in m24_issues(fake_out)))
        bad_dep = self.text.replace("｜被依赖：无｜", "｜被依赖：M13｜", 1)
        self.assertTrue(any("被依赖" in i for i in m24_issues(bad_dep)))
        no_sig = self.text.replace("resolve(inputA, inputB)", "resolve()", 1)
        self.assertTrue(any("签名" in i for i in m24_issues(no_sig)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m24_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m24_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m24.md")


if __name__ == "__main__":
    unittest.main()
