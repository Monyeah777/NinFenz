#!/usr/bin/env python3
"""通用:M10 节拍推进模块契约：双事件载荷并集 == outputs，且 tick_day 发布面与订阅面对账。

为什么必须有：M10 是时间唯一来源（tick/day/season 三轨时钟），发布两个事件（tick_day 常驻、
minute_tick 仅在启用子刻时）。实测本轮抓到**真实契约缺项**：machine_contract.outputs 只写
3 个字段（tick/day/season），§4 正文两个 payload 并集是 5 个（tick/day/is_new_day/season_ctx/
minute），且 io_types 把 season 当 string 而正文用 season_ctx——三面不一致。按 01 §1.1
「机读块 = 正文契约的结构化投影、须覆盖全集且不越界」以正文 payload 并集为准补齐（含 season，
与 §1 三轨时钟一致；weather_state 属 M08 的发布面，不并入 M10 outputs），io_types 按规则重推。

范围：只判本模块文档结构自洽与跨源同源（不改时间语义）。同族判据：
test_module_m00/m06/m08/m12/m13/m20/m22/m90_contract（同模板）/
test_registry_doc_contract（02 §2/§3/§5/§6）/ test_schema_lint（check28）/ check16。
契约：五段结构、outputs == 两事件 payload 并集、io_types 按规则推导、registry 与 02 §2 一致、
02 §3 tick_day 发布方/订阅方对账、02 §5/§6 在册、L2 可证、字段全部在 event_registry 在册、
tool_face 对接字段与 outputs 同步。
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

M10 = ROOT / "04_模块库" / "通用类" / "M10_节拍推进.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 时间尺度", "## 3. 推进流程",
                     "## 4. 事件契约", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "I3", "I4",
                    "protocol/event_registry.json", "check16", "check28",
                    "tick_day", "minute_tick", "season_ctx")


def load_text(path: Path = M10) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M10 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M10 为空")
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
        if item.get("id") == "通用:M10":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| 通用:M10 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def event_registry() -> dict:
    return json.loads((ROOT / "protocol" / "event_registry.json")
                      .read_text(encoding="utf-8"))["events"]


def subscription(event: str) -> dict:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 3. 订阅关系", 1)[1].split("\n## 4.", 1)[0]
    m = re.search(re.escape(event) + r":[^\n]*\n((?:    [^\n]*\n)+)", body)
    out = {}
    if not m:
        return out
    seg = m.group(1)
    mp = re.search(r"publisher: (\S+)", seg)
    ms = re.search(r"subscribers: \[(.*?)\]", seg)
    if mp:
        out["publisher"] = mp.group(1)
    if ms:
        out["subscribers"] = [x.strip() for x in ms.group(1).split(",") if x.strip()]
    return out


def p10_default() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    m = re.search(r"^  P10 [^:]+:\s*\{default: \[(.*?)\]", body, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def execution_mentions_m10() -> int:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return body.count("通用:M10")


def payload_union(text: str) -> list:
    fields = []
    for m in re.finditer(r"payload: \{([^}]+)\}", text):
        for item in m.group(1).split(","):
            token = item.strip().split(":")[0].strip()
            if token and token not in fields:
                fields.append(token)
    return fields


def toolface_outputs_line(text: str) -> str:
    m = re.search(r"对接字段: outputs=\[([^\]]*)\]", text)
    return m.group(1) if m else ""


def m10_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    outputs = header.get("outputs") or []
    if header.get("id") != "通用:M10":
        issues.append(f"机读块 id 应为 通用:M10（实测 {header.get('id')!r}）")
    if set(header.get("publish") or []) != {"tick_day", "minute_tick"}:
        issues.append(f"publish 应为 tick_day/minute_tick：{header.get('publish')}")
    if (header.get("subscribe") or []) != []:
        issues.append(f"subscribe 应为空：{header.get('subscribe')}")
    union = payload_union(text)
    if sorted(outputs) != sorted(union):
        issues.append(f"outputs 与两事件 payload 并集不同集：{outputs} ≠ {union}")
    parsed_io = io_types.parse_io_types(text)
    if parsed_io is None:
        issues.append("缺 io_types 类型面")
    else:
        ev_types = io_types.event_field_types(str(ROOT))
        expected = io_types.derive(outputs, header.get("inputs") or [], ev_types)
        if parsed_io != expected:
            issues.append("io_types 未按「同名事件字段」规则推导")
    quoted = toolface_outputs_line(text)
    expected_line = ", ".join(outputs)
    if quoted.replace(" ", "") != expected_line.replace(" ", ""):
        issues.append(f"tool_face 对接字段与 outputs 不同步：{quoted!r}")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    reg = registry_module()
    if not reg:
        issues.append("registry.json 缺 通用:M10 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P10" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P10/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 通用:M10 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P10" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
    events = event_registry()
    for name in (header.get("publish") or []) + (header.get("subscribe") or []):
        if name not in events:
            issues.append(f"事件未在 event_registry 在册：{name}")
    registered = set()
    for name in ("tick_day", "minute_tick"):
        registered |= set(((events.get(name) or {}).get("fields") or {}).keys())
    for field in union:
        if field not in registered:
            issues.append(f"payload 字段未在 event_registry 在册：{field}")
    sub = subscription("tick_day")
    if sub.get("publisher") != "通用:M10":
        issues.append(f"02 §3 tick_day 发布方应为 通用:M10：{sub.get('publisher')}")
    if "M08" not in (sub.get("subscribers") or []):
        issues.append(f"02 §3 tick_day 订阅方应含 M08：{sub.get('subscribers')}")
    if "通用:M10" not in p10_default():
        issues.append(f"02 §5 P10 default 应含 通用:M10：{p10_default()}")
    if execution_mentions_m10() < 1:
        issues.append("02 §6 执行顺序应含 通用:M10")
    p01 = P01.read_text(encoding="utf-8")
    allowed = re.search(r"id: P10[\s\S]*?default_modules: \[([^\]]*)\]", p01)
    if not allowed or "通用:M10" not in allowed.group(1):
        issues.append("L2 不可证：P01 P10 default_modules 未引用 通用:M10")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM10ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m10_matches_contract(self):
        self.assertEqual([], m10_issues(self.text), "M10 不满足模块契约")

    def test_outputs_equal_payload_union(self):
        header = mc_fields(self.text)
        self.assertEqual(sorted(header.get("outputs") or []), sorted(payload_union(self.text)))

    def test_io_types_are_evidence_based(self):
        header = mc_fields(self.text)
        parsed = io_types.parse_io_types(self.text)
        self.assertIsNotNone(parsed, "缺 io_types")
        expected = io_types.derive(header.get("outputs") or [], header.get("inputs") or [],
                                   io_types.event_field_types(str(ROOT)))
        self.assertEqual(expected, parsed)

    def test_contract_catches_mutations(self):
        """变异自证：outputs 缺项 / io_types 编造 / 未在册字段 / publish 漂移 / 缺段 / 围栏。"""
        drop = self.text.replace("  outputs: [tick, day, is_new_day, season, season_ctx, minute]",
                                 "  outputs: [tick, day, season]", 1)
        self.assertTrue(any("outputs" in i for i in m10_issues(drop)))
        fake_type = self.text.replace("minute: number", "minute: string", 1)
        self.assertTrue(any("io_types" in i for i in m10_issues(fake_type)))
        fake_field = self.text.replace("payload: {tick, minute}",
                                       "payload: {tick, minute, x_field}", 1)
        self.assertTrue(any("在册" in i for i in m10_issues(fake_field)))
        bad_publish = self.text.replace("    publish: [tick_day, minute_tick]",
                                        "    publish: [tick_day]", 1)
        self.assertTrue(any("publish" in i for i in m10_issues(bad_publish)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m10_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m10_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m10.md")


if __name__ == "__main__":
    unittest.main()
