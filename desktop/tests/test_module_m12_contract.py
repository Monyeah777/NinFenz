#!/usr/bin/env python3
"""M12 模板检索库模块契约：零事件模块必须以 interfaces 补全联动面，且四源同源。

为什么必须有：M12 是零事件模块（publish/subscribe 双空），01 §1.6.11 明文要求这类模块
「显式 publish: []/subscribe: [] 并以 interfaces 补全接口面，M00 纯数据槽基座写 interfaces: []」。
实测本轮抓到**真实契约缺项**：M12 的 interfaces 仍是 []——它被 M13 检索消费，不是纯内部模块，
却把自己登记成纯内部，等于「以空契约隐式脱离联动面」（01 §1.1 明令禁止）。按正文 §3 的检索
职责补为 [search]，并在 §3/§5 写明接口只读边界。

范围：只判本模块文档的结构自洽与跨源同源（不改检索语义）。同族判据：
test_module_m06_contract / test_module_m08_contract（同模板）/ test_core_protocol_contract
（01 §1.1/§1.6.11）/ test_registry_doc_contract（02 §2/§5/§6）/ check16 / check28。
契约：五段结构、零事件 + interfaces 非空、引用块与机读块一致、registry 与 02 §2 一致、
P01 P50 default 引用（L2 可证）、io_types 按规则推导、正文接口边界句在场。
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

M12 = ROOT / "04_模块库" / "事件类" / "M12_模板检索库.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
PROTOCOL = ROOT / "01_核心协议.md"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 模板规则", "## 3. 模板-状态互查",
                     "## 4. 事件契约", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "asset_get", "I3", "I4",
                    "check16", "check28", "不编造", "interfaces", "search")


def load_text(path: Path = M12) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M12 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M12 为空")
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
        if item.get("id") == "M12":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M12 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def p50_default() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    m = re.search(r"^  P50 [^:]+:\s*\{default: \[(.*?)\]", body, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def execution_order_has_m12() -> bool:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return "M12" in body


def m12_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    if header.get("id") != "M12":
        issues.append(f"机读块 id 应为 M12（实测 {header.get('id')!r}）")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    if (header.get("publish") or []) != [] or (header.get("subscribe") or []) != []:
        issues.append(f"零事件模块应显式双空：{header.get('publish')} / {header.get('subscribe')}")
    interfaces = header.get("interfaces")
    if not interfaces:
        issues.append("零事件模块 interfaces 为空（01 §1.1：须以 interfaces 补全联动面）")
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
        issues.append("registry.json 缺 M12 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P50" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P50/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M12 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P50" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
    if "M12" not in p50_default():
        issues.append(f"02 §5 P50 default 应含 M12：{p50_default()}")
    if not execution_order_has_m12():
        issues.append("02 §6 执行顺序应含 M12")
    p01 = P01.read_text(encoding="utf-8")
    allowed = re.search(r"id: P50[\s\S]*?default_modules: \[([^\]]*)\]", p01)
    if not allowed or "M12" not in allowed.group(1):
        issues.append("L2 不可证：P01 P50 default_modules 未引用 M12")
    basis = PROTOCOL.read_text(encoding="utf-8")
    if not ("M12/M20/M23/M24/M50" in basis and "interfaces" in basis):
        issues.append("01 缺「零事件模块以 interfaces 补全」规则依据（§1.6.11）")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM12ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m12_matches_contract(self):
        self.assertEqual([], m12_issues(self.text), "M12 不满足模块契约")

    def test_zero_event_rule_is_satisfied(self):
        header = mc_fields(self.text)
        self.assertEqual([], header.get("publish"))
        self.assertEqual([], header.get("subscribe"))
        self.assertTrue(header.get("interfaces"), "零事件模块必须有 interfaces")

    def test_io_types_are_evidence_based(self):
        header = mc_fields(self.text)
        parsed = io_types.parse_io_types(self.text)
        self.assertIsNotNone(parsed, "缺 io_types")
        expected = io_types.derive(header.get("outputs") or [], header.get("inputs") or [],
                                   io_types.event_field_types(str(ROOT)))
        self.assertEqual(expected, parsed)

    def test_contract_catches_mutations(self):
        """变异自证：interfaces 清空 / id 漂移 / 假事件 / io_types 编造 / 缺段 / 围栏。"""
        no_iface = self.text.replace("  interfaces: [search]", "  interfaces: []", 1)
        self.assertTrue(any("interfaces" in i for i in m12_issues(no_iface)))
        bad_id = self.text.replace("  id: M12", "  id: M99", 1)
        self.assertTrue(any("id" in i for i in m12_issues(bad_id)))
        fake_event = self.text.replace("  events:" + chr(10) + "    publish: []",
                                     "  events:" + chr(10) + "    publish: [x_event]", 1)
        self.assertTrue(any("双空" in i for i in m12_issues(fake_event)))
        fake_type = self.text.replace("      M20: untyped", "      M20: string", 1)
        self.assertTrue(any("io_types" in i for i in m12_issues(fake_type)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m12_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m12_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m12.md")


if __name__ == "__main__":
    unittest.main()
