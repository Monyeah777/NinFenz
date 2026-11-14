#!/usr/bin/env python3
"""M08 环境状态模块契约：模块文档必须「机读块 ⇄ 引用块 ⇄ 注册表 ⇄ 事件注册表」同源。

为什么必须有：04 模块文档是 check16 契约仲裁与 check28 IDL 的读取对象，但此前没有「单模块文档
自洽」的判据——引用块写的类别/挂载/依赖/发布是否与 machine_contract 一致、outputs 是否与
event_registry 的载荷字段同集、io_types 是否真按「同名事件字段」规则推导，全靠全局扫描兜底。
实测本轮补的真缺口：§1 没写清「引用块/机读块/正文」三形态关系、§2/§4/§5 没有 I3/I4 与
「不编造维度」的边界句、§3 没写机读投影口径。

范围：只判本模块文档的结构自洽与跨源同源（不改 machine_contract 语义）。同族判据：
test_core_protocol_contract（01 §1.1）/ test_registry_doc_contract（02 §2/§3）/
test_navigation_doc_contract（07 §1）/ test_schema_lint（check28）/ check16。
契约：五段结构、引用块与机读块逐字段一致、注册表 module 条目一致、
outputs == weather_state 载荷字段、
io_types == 按规则从事件注册表推导的结果、L2 可证、事件名在册、正文边界句在场。
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

M08 = ROOT / "04_模块库" / "世界类" / "M08_环境状态.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 周期与环境规则", "## 3. 事件契约",
                     "## 4. 结算流程", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "asset_get", "I3", "I4",
                    "protocol/event_registry.json", "check16", "check28", "不编造",
                    "tick_day", "weather_state")


def load_text(path: Path = M08) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M08 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M08 为空")
    return text


def ys(items) -> list:
    return [str(x) for x in (items or [])]


def mc_block(text: str) -> str:
    m = re.search(FENCE + "yaml\n(machine_contract:.*?)\n" + FENCE, text, re.S)
    return m.group(1) if m else ""


def mc_fields(text: str) -> dict:
    """机读块字段（直接解析 machine_contract 围栏，不经人读头推断）。"""
    block = mc_block(text)
    out = {}
    for key in ("id", "name", "category", "layer"):
        m = re.search(r"^  " + key + r": (.+)$", block, re.M)
        if m:
            out[key] = m.group(1).strip().strip('"')
    for key in ("publish", "subscribe", "inputs"):
        m = re.search(r"^\s+" + key + r": \[(.*?)\]", block, re.M)
        if m:
            out[key] = [x.strip() for x in m.group(1).split(",") if x.strip()]
    return out


def contract_outputs(text: str) -> list:
    m = re.search(r"^  outputs: \[(.*?)\]", text, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def contract_inputs(text: str) -> list:
    m = re.search(r"^  inputs: \[(.*?)\]", text, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def quote_fields(text: str) -> dict:
    """引用块：类别 / 来源 / 挂载点 / 依赖 / 发布。"""
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
        if item.get("id") == "M08":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M08 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def event_registry() -> dict:
    return json.loads((ROOT / "protocol" / "event_registry.json")
                      .read_text(encoding="utf-8"))["events"]


def tick_day_publisher() -> str:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 3. 订阅关系", 1)[1].split("\n## 4.", 1)[0]
    m = re.search(r"tick_day:[^\n]*\n\s+publisher: (\S+)", body)
    return m.group(1) if m else ""


def payload_fields(text: str) -> list:
    m = re.search(r"payload: \{([^}]+)\}", text)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def m08_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    if header.get("id") != "M08":
        issues.append(f"机读块 id 应为 M08（实测 {header.get('id')!r}）")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    if ys(header.get("publish")) != ["weather_state"]:
        issues.append(f"publish 应为 weather_state：{header.get('publish')}")
    if ys(header.get("subscribe")) != ["tick_day"]:
        issues.append(f"subscribe 应为 tick_day：{header.get('subscribe')}")
    if ys(header.get("inputs")) != ["通用:M10"]:
        issues.append(f"inputs 应为 通用:M10：{header.get('inputs')}")
    outputs = contract_outputs(text)
    parsed_io = io_types.parse_io_types(text)
    if parsed_io is None:
        issues.append("缺 io_types 类型面")
    else:
        ev_types = io_types.event_field_types(str(ROOT))
        expected = io_types.derive(outputs, contract_inputs(text), ev_types)
        if parsed_io != expected:
            issues.append(f"io_types 未按「同名事件字段」规则推导：{parsed_io} ≠ {expected}")
    reg = registry_module()
    if not reg:
        issues.append("registry.json 缺 M08 模块条目")
    else:
        if reg.get("name") != header.get("name"):
            issues.append("registry.json 模块名与机读块不一致")
        if reg.get("category") != header.get("category"):
            issues.append("registry.json 类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P10" and m.get("status") == "available" for m in mounts):
            issues.append(f"registry.json 挂载应为 P10/available：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M08 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P10" not in row[4] or "available" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
    events = event_registry()
    for name in ys(header.get("publish")) + ys(header.get("subscribe")):
        if name not in events:
            issues.append(f"事件未在 event_registry 在册：{name}")
    ws = events.get("weather_state") or {}
    if set((ws.get("fields") or {}).keys()) != set(outputs):
        issues.append("machine_contract.outputs 与 weather_state 载荷字段不同集")
    if set(payload_fields(text)) != set(outputs):
        issues.append("§3 payload 与 machine_contract.outputs 不同集")
    if tick_day_publisher() != "通用:M10":
        issues.append(f"02 §3 tick_day 发布方应为 通用:M10（实测 {tick_day_publisher()!r}）")
    p01 = P01.read_text(encoding="utf-8")
    allowed = re.search(r"id: P10[\s\S]*?allowed_modules: \[([^\]]*)\]", p01)
    if not allowed or "M08" not in allowed.group(1):
        issues.append("L2 不可证：P01 P10 allowed_modules 未引用 M08")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM08ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m08_matches_contract(self):
        self.assertEqual([], m08_issues(self.text), "M08 不满足模块契约")

    def test_machine_block_and_quote_are_same_source(self):
        header = mc_fields(self.text)
        self.assertEqual("M08", header.get("id"))
        self.assertEqual("环境状态", header.get("name"))
        self.assertEqual(quote_fields(self.text).get("类别"), header.get("category"))
        self.assertEqual(ys(header.get("publish")), ["weather_state"])
        self.assertEqual(ys(header.get("subscribe")), ["tick_day"])

    def test_io_types_are_evidence_based(self):
        parsed = io_types.parse_io_types(self.text)
        self.assertIsNotNone(parsed, "缺 io_types")
        expected = io_types.derive(contract_outputs(self.text), contract_inputs(self.text),
                                   io_types.event_field_types(str(ROOT)))
        self.assertEqual(expected, parsed, "io_types 与事件注册表证据不一致")

    def test_contract_catches_mutations(self):
        """变异自证：id / io_types / publish / 缺段 / 引用块 / 围栏 六类漂移。"""
        bad_id = self.text.replace("  id: M08", "  id: M99", 1)
        self.assertTrue(any("id" in i for i in m08_issues(bad_id)))
        fake_type = self.text.replace("season: string", "season: integer", 1)
        self.assertTrue(any("io_types" in i for i in m08_issues(fake_type)))
        bad_publish = self.text.replace("publish: [weather_state]", "publish: [weather_x]", 1)
        self.assertTrue(any("publish" in i or "在册" in i for i in m08_issues(bad_publish)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m08_issues(no_section)))
        bad_quote = self.text.replace("> 类别：世界", "> 类别：事件", 1)
        self.assertTrue(any("类别" in i for i in m08_issues(bad_quote)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m08_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m08.md")


if __name__ == "__main__":
    unittest.main()
