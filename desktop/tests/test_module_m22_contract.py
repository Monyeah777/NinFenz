#!/usr/bin/env python3
"""M22 事件编排模块契约：outputs == payload == narrative_event 全集，且订阅面全部在册。

为什么必须有：事件:M22 是编排者（唯一发布 narrative_event，M80 唯一内容输入），契约三面必须
一致。实测本轮抓到与 M06/M13 同型的**真实契约缺项**：machine_contract.outputs 只写 3 个字段
（type/payload/tick），§3 正文 payload 只写 5 个（seq_no/type/beats/pov/causal_chain），而
event_registry.json 的 narrative_event 登记 7 个字段——三面各说各话。按 01 §1.1「机读块 =
正文契约的结构化投影、须覆盖全集且不越界」以注册表全集为准补齐，io_types 按「同名事件字段」
规则重新推导。另把「inputs 为空 = 显式声明、输入面 = 订阅事件总线」与七事件订阅在册立成断言。

范围：只判本模块文档的结构自洽与跨源同源（不改编排语义）。同族判据：
test_module_m06/m08/m12/m13/m20_contract（同模板）/ test_registry_doc_contract（02 §2/§3/§5/§6）/
test_schema_lint（check28）/ check16。
契约：五段结构、引用块与机读块一致、outputs == §3 payload == narrative_event 字段、
io_types 按规则推导、registry 与 02 §2 一致、02 §3 publisher/subscribers 对账、
02 §5/§6 在册、L2 可证、七个订阅事件全部在 event_registry 在册、正文边界句在场。
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

M22 = ROOT / "04_模块库" / "事件类" / "M22_事件编排.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
FENCE = chr(96) * 3

SUBSCRIBE = {"death_trigger", "relationship_change", "chaos_event", "ghost_event",
             "market_event", "production_output", "interaction_update"}
REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 事件编排规则", "## 3. 事件契约",
                     "## 4. 编排流程", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "I3", "I4",
                    "protocol/event_registry.json", "check16", "check28", "不编造",
                    "narrative_event", "seq_no", "causal_chain")


def load_text(path: Path = M22) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M22 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M22 为空")
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
        if item.get("id") == "事件:M22":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| 事件:M22 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def event_registry() -> dict:
    return json.loads((ROOT / "protocol" / "event_registry.json")
                      .read_text(encoding="utf-8"))["events"]


def narrative_block() -> str:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 3. 订阅关系", 1)[1].split("\n## 4.", 1)[0]
    m = re.search(r"narrative_event:[^\n]*\n([\s\S]*?)(?=\n  \w)", body)
    return m.group(1) if m else ""


def p30_default() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    m = re.search(r"^  P30 [^:]+:\s*\{default: \[(.*?)\]", body, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def execution_order_has_m22() -> bool:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return "M22" in body


def payload_fields(text: str) -> list:
    m = re.search(r"payload: \{([^}]+)\}", text)
    return [x.strip().rstrip("[]") for x in m.group(1).split(",") if x.strip()] if m else []


def m22_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    outputs = header.get("outputs") or []
    if header.get("id") != "事件:M22":
        issues.append(f"机读块 id 应为 事件:M22（实测 {header.get('id')!r}）")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    if header.get("publish") != ["narrative_event"]:
        issues.append(f"publish 应为 narrative_event：{header.get('publish')}")
    if set(header.get("subscribe") or []) != SUBSCRIBE:
        issues.append(f"subscribe 应为七事件全集：{header.get('subscribe')}")
    if (header.get("inputs") or []) != []:
        issues.append(f"inputs 应为空（显式声明）：{header.get('inputs')}")
    parsed_io = io_types.parse_io_types(text)
    if parsed_io is None:
        issues.append("缺 io_types 类型面")
    else:
        ev_types = io_types.event_field_types(str(ROOT))
        expected = io_types.derive(outputs, header.get("inputs") or [], ev_types)
        if parsed_io != expected:
            issues.append("io_types 未按「同名事件字段」规则推导")
    reg = registry_module()
    if not reg:
        issues.append("registry.json 缺 事件:M22 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P30" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P30/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 事件:M22 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P30" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
    events = event_registry()
    for name in (header.get("publish") or []) + sorted(header.get("subscribe") or []):
        if name not in events:
            issues.append(f"事件未在 event_registry 在册：{name}")
    ne = events.get("narrative_event") or {}
    registry_fields = set((ne.get("fields") or {}).keys())
    if not registry_fields:
        issues.append("event_registry 缺 narrative_event 字段")
    elif set(outputs) != registry_fields:
        issues.append("outputs 与 narrative_event 载荷字段不同集")
    if set(payload_fields(text)) != set(outputs):
        issues.append("§3 payload 与 machine_contract.outputs 不同集")
    block = narrative_block()
    if "publisher: 事件:M22" not in block:
        issues.append("02 §3 narrative_event 发布方应为 事件:M22")
    if "subscribers: [M80]" not in block:
        issues.append("02 §3 narrative_event 订阅方应含 M80")
    if "事件:M22" not in p30_default():
        issues.append(f"02 §5 P30 default 应含 事件:M22：{p30_default()}")
    if not execution_order_has_m22():
        issues.append("02 §6 执行顺序应含 M22")
    p01 = P01.read_text(encoding="utf-8")
    allowed = re.search(r"id: P30[\s\S]*?default_modules: \[([^\]]*)\]", p01)
    if not allowed or "事件:M22" not in allowed.group(1):
        issues.append("L2 不可证：P01 P30 default_modules 未引用 事件:M22")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM22ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m22_matches_contract(self):
        self.assertEqual([], m22_issues(self.text), "M22 不满足模块契约")

    def test_outputs_match_event_payload_and_registry(self):
        header = mc_fields(self.text)
        ne = event_registry().get("narrative_event") or {}
        self.assertEqual(set(header.get("outputs") or []), set((ne.get("fields") or {}).keys()))
        self.assertEqual(set(payload_fields(self.text)), set(header.get("outputs") or []))

    def test_contract_catches_mutations(self):
        """变异自证：outputs 缺项 / io_types 编造 / payload 漂移 / 未知订阅 / 缺段 / 围栏。"""
        drop = self.text.replace(" causal_chain, payload", " payload", 1)
        self.assertTrue(any("outputs" in i or "payload" in i for i in m22_issues(drop)))
        fake_type = self.text.replace("beats: array", "beats: string", 1)
        self.assertTrue(any("io_types" in i for i in m22_issues(fake_type)))
        bad_payload = self.text.replace("pov, causal_chain", "causal_chain", 1)
        self.assertTrue(any("payload" in i for i in m22_issues(bad_payload)))
        bad_sub = self.text.replace("market_event, production_output",
                                    "market_event, x_event, production_output", 1)
        self.assertTrue(any("在册" in i for i in m22_issues(bad_sub)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m22_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m22_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m22.md")


if __name__ == "__main__":
    unittest.main()
