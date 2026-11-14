#!/usr/bin/env python3
"""M13 实体交互模块契约：outputs == payload == event_registry，且四源同源。

为什么必须有：M13 是实体个体真相源，interaction_update 是其唯一发布面。实测本轮抓到与 M06
同型的**真实契约缺项**：machine_contract.outputs 只写 4 个字段（npc_id/action/result/tick），
§3 正文 payload 只写 5 个（npc_id/type/affinity_delta/context/flags[]），而 event_registry.json
的 interaction_update 登记 8 个字段——三面各说各话。按 01 §1.1「机读块 = 正文契约的结构化投影、
须覆盖全集且不越界」以注册表全集为准补齐，io_types 按「同名事件字段」规则重新推导。

范围：只判本模块文档的结构自洽与跨源同源（不改交互语义）。同族判据：
test_module_m06_contract / test_module_m08_contract / test_module_m12_contract（同模板）/
test_registry_doc_contract（02 §2/§3/§5/§6）/ test_schema_lint（check28）/ check16。
契约：五段结构、引用块与机读块一致、outputs == §3 payload == interaction_update 字段、
io_types 按规则推导、registry 与 02 §2/§3/§5/§6 一致、L2 可证、事件名在册、正文边界句在场。
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

M13 = ROOT / "04_模块库" / "事件类" / "M13_实体交互.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 实体状态机", "## 3. 事件契约",
                     "## 4. 结算流程", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "asset_get", "I3", "I4",
                    "protocol/event_registry.json", "check16", "check28", "不编造",
                    "interaction_update", "M12")


def load_text(path: Path = M13) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M13 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M13 为空")
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
        if item.get("id") == "M13":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M13 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def event_registry() -> dict:
    return json.loads((ROOT / "protocol" / "event_registry.json")
                      .read_text(encoding="utf-8"))["events"]


def subscription_publisher(event: str) -> str:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 3. 订阅关系", 1)[1].split("\n## 4.", 1)[0]
    m = re.search(re.escape(event) + r":[^\n]*\n\s+publisher: (\S+)", body)
    return m.group(1) if m else ""


def p30_default() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    m = re.search(r"^  P30 [^:]+:\s*\{default: \[(.*?)\]", body, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def execution_order_has_m13() -> bool:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return "M13" in body


def payload_fields(text: str) -> list:
    m = re.search(r"payload: \{([^}]+)\}", text)
    return [x.strip().rstrip("[]") for x in m.group(1).split(",") if x.strip()] if m else []


def m13_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    outputs = header.get("outputs") or []
    if header.get("id") != "M13":
        issues.append(f"机读块 id 应为 M13（实测 {header.get('id')!r}）")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    if header.get("publish") != ["interaction_update"]:
        issues.append(f"publish 应为 interaction_update：{header.get('publish')}")
    if set(header.get("subscribe") or []) != {"quest_state", "level_up"}:
        issues.append(f"subscribe 应为 quest_state/level_up：{header.get('subscribe')}")
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
        issues.append("registry.json 缺 M13 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P30" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P30/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M13 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P30" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
    events = event_registry()
    for name in (header.get("publish") or []) + (header.get("subscribe") or []):
        if name not in events:
            issues.append(f"事件未在 event_registry 在册：{name}")
    iu = events.get("interaction_update") or {}
    registry_fields = set((iu.get("fields") or {}).keys())
    if not registry_fields:
        issues.append("event_registry 缺 interaction_update 字段")
    elif set(outputs) != registry_fields:
        issues.append("outputs 与 interaction_update 载荷字段不同集")
    if set(payload_fields(text)) != set(outputs):
        issues.append("§3 payload 与 machine_contract.outputs 不同集")
    if subscription_publisher("interaction_update") != "M13":
        issues.append("02 §3 interaction_update 发布方应为 M13")
    if "M13" not in p30_default():
        issues.append(f"02 §5 P30 default 应含 M13：{p30_default()}")
    if not execution_order_has_m13():
        issues.append("02 §6 执行顺序应含 M13")
    p01 = P01.read_text(encoding="utf-8")
    allowed = re.search(r"id: P30[\s\S]*?default_modules: \[([^\]]*)\]", p01)
    if not allowed or "M13" not in allowed.group(1):
        issues.append("L2 不可证：P01 P30 default_modules 未引用 M13")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM13ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m13_matches_contract(self):
        self.assertEqual([], m13_issues(self.text), "M13 不满足模块契约")

    def test_outputs_match_event_payload_and_registry(self):
        header = mc_fields(self.text)
        iu = event_registry().get("interaction_update") or {}
        self.assertEqual(set(header.get("outputs") or []), set((iu.get("fields") or {}).keys()))
        self.assertEqual(set(payload_fields(self.text)), set(header.get("outputs") or []))

    def test_contract_catches_mutations(self):
        """变异自证：outputs 缺项 / io_types 编造 / payload 漂移 / 发布漂移 / 缺段 / 围栏。"""
        drop = self.text.replace(" flags, type]", " type]", 1)
        self.assertTrue(any("outputs" in i or "payload" in i for i in m13_issues(drop)))
        fake_type = self.text.replace("tick: number", "tick: string", 1)
        self.assertTrue(any("io_types" in i for i in m13_issues(fake_type)))
        bad_payload = self.text.replace("affinity_delta, context", "context", 1)
        self.assertTrue(any("payload" in i for i in m13_issues(bad_payload)))
        bad_publish = self.text.replace("publish: [interaction_update]", "publish: [x_event]", 1)
        self.assertTrue(any("publish" in i or "在册" in i for i in m13_issues(bad_publish)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m13_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m13_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m13.md")


if __name__ == "__main__":
    unittest.main()
