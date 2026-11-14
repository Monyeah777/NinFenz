#!/usr/bin/env python3
"""M20 知识条目库模块契约：零事件 + query 接口 + 双挂载必须四源同源。

为什么必须有：M20 是零事件只读知识库（publish/subscribe 双空），按 01 §1.1 须以 interfaces
补全联动面——它已声明 [query]，本轮判据把这条规则与「双挂载（P70 active 主挂载 + P00 available
常识装载槽）」一起立成可核断言。实测本轮无契约缺项，但补上判据防止两类回退：interfaces 被清空
（重演 M12 的旧问题）、双挂载在文档/registry/02 §5 三处漂移。

范围：只判本模块文档的结构自洽与跨源同源（不改知识语义）。同族判据：
test_module_m12_contract（零事件模板）/ test_module_m06·m08·m13（事件面模板）/
test_registry_doc_contract（02 §2/§5/§6）/ test_schema_lint（check28）/ check16。
契约：五段结构、零事件 + interfaces [query]、引用块与机读块一致、registry 双挂载与 02 §2 一致、
02 §5 P00 available / P70 default 含 M20、§6 执行顺序含 M20、io_types 按规则推导、L2 可证。
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

M20 = ROOT / "04_模块库" / "事件类" / "M20_知识条目库.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
PROTOCOL = ROOT / "01_核心协议.md"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 知识条目结构", "## 3. 供给与查询",
                     "## 4. 与各模块的配合", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "asset_get", "I3", "I4",
                    "check16", "check28", "不编造", "interfaces", "query")


def load_text(path: Path = M20) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M20 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M20 为空")
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
        if item.get("id") == "M20":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M20 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def mount_defaults() -> dict:
    """02 §5 的层 id → (default, available)。"""
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    out = {}
    for line in body.splitlines():
        m = re.match(r"^  (P\d\d) [^:]+:\s*"
                     r"\{default: \[(.*?)\], available: \[(.*?)\]\}", line)
        if m:
            out[m.group(1)] = ([x.strip() for x in m.group(2).split(",") if x.strip()],
                               [x.strip() for x in m.group(3).split(",") if x.strip()])
    return out


def execution_mentions_m20() -> int:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return body.count("M20")


def m20_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    if header.get("id") != "M20":
        issues.append(f"机读块 id 应为 M20（实测 {header.get('id')!r}）")
    quote = quote_fields(text)
    if quote.get("类别") != header.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {header.get('category')!r}")
    mount_text = quote.get("挂载点") or ""
    if "P70" not in mount_text or "active" not in mount_text:
        issues.append(f"引用块缺 P70/active 挂载：{mount_text!r}")
    if "P00" not in mount_text or "available" not in mount_text:
        issues.append(f"引用块缺 P00/available 挂载：{mount_text!r}")
    if (header.get("publish") or []) != [] or (header.get("subscribe") or []) != []:
        issues.append("零事件模块应显式双空")
    interfaces = header.get("interfaces") or []
    if interfaces != ["query"]:
        issues.append(f"interfaces 应为 [query]（实测 {interfaces}）")
    if (header.get("outputs") or []) != []:
        issues.append(f"零事件且纯接口供给的模块 outputs 应为空：{header.get('outputs')}")
    if header.get("inputs") != ["M00"]:
        issues.append(f"inputs 应为 M00：{header.get('inputs')}")
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
        issues.append("registry.json 缺 M20 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = {(m.get("layer"), m.get("status")) for m in (reg.get("mounts") or [])}
        if mounts != {("P70", "active"), ("P00", "available")}:
            issues.append(f"registry.json 双挂载应为 P70/active + P00/available：{mounts}")
        if header.get("layer") != "P70":
            issues.append(f"机读层字段应登记主挂载层 P70（实测 {header.get('layer')!r}）")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M20 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P70" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 缺 P70/active 挂载：{row[4]}")
        if "P00" not in row[4] or "available" not in row[4]:
            issues.append(f"02 §2 缺 P00/available 挂载：{row[4]}")
    mounts5 = mount_defaults()
    if "M20" not in mounts5.get("P00", ([], []))[1]:
        issues.append("02 §5 P00 available 应含 M20")
    if "M20" not in mounts5.get("P70", ([], []))[0]:
        issues.append("02 §5 P70 default 应含 M20")
    if execution_mentions_m20() < 2:
        issues.append("02 §6 执行顺序应两处提及 M20（常识装载 + 素材层）")
    if "query(domain, key, viewer)" not in text:
        issues.append("§3 缺 query(domain, key, viewer) 接口签名")
    p01 = P01.read_text(encoding="utf-8")
    allowed = re.search(r"id: P70[\s\S]*?default_modules: \[([^\]]*)\]", p01)
    if not allowed or "M20" not in allowed.group(1):
        issues.append("L2 不可证：P01 P70 default_modules 未引用 M20")
    basis = PROTOCOL.read_text(encoding="utf-8")
    if not ("M20" in basis and "interfaces" in basis):
        issues.append("01 缺零事件模块 interfaces 规则依据（§1.1）")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM20ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m20_matches_contract(self):
        self.assertEqual([], m20_issues(self.text), "M20 不满足模块契约")

    def test_zero_event_and_dual_mount_are_same_source(self):
        header = mc_fields(self.text)
        self.assertEqual([], header.get("publish"))
        self.assertEqual([], header.get("subscribe"))
        self.assertEqual(["query"], header.get("interfaces"))
        mounts = {(m.get("layer"), m.get("status"))
                  for m in (registry_module().get("mounts") or [])}
        self.assertEqual({("P70", "active"), ("P00", "available")}, mounts)

    def test_contract_catches_mutations(self):
        """变异自证：interfaces 清空 / outputs 非空 / 双挂载漂移 / 签名缺失 / 缺段 / 围栏。"""
        no_iface = self.text.replace("  interfaces: [query]", "  interfaces: []", 1)
        self.assertTrue(any("interfaces" in i for i in m20_issues(no_iface)))
        bad_outputs = self.text.replace("  outputs: []", "  outputs: [x]", 1)
        self.assertTrue(any("outputs" in i for i in m20_issues(bad_outputs)))
        bad_quote = self.text.replace("P70 素材（active）/ P00 装载（available）",
                                      "P70 素材（active）/ P00 装载（active）", 1)
        self.assertTrue(any("P00" in i for i in m20_issues(bad_quote)))
        no_sig = self.text.replace("query(domain, key, viewer)", "query()", 1)
        self.assertTrue(any("签名" in i for i in m20_issues(no_sig)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m20_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m20_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m20.md")


if __name__ == "__main__":
    unittest.main()
