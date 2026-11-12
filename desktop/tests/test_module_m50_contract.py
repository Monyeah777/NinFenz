#!/usr/bin/env python3
"""M50 调度器模块契约：全局调度器（layer=调度器/mounts 空）+ world_model 槽面必须全在册。

为什么必须有：M50 是唯一在用的 world_model 抽象世界模型实例（首战），也是唯一 layer 写「调度器」
而不入任何层挂载的模块。实测本轮抓到**真实漂移**：machine_contract.world_model.transition 的
writes 写目标是 memory.working / memories.memory.episodic.items / memories.memory.semantic.facts，
而 protocol/world_slots.json 在册的是 PlayerState.memories.working / .episodic / .semantic——
写路径没走冻结寻址面（Phase 1 逐字保持的标识符）。已按在册槽路径改正 writes，并把「抽象状态
slot 与迁移写目标都必须在 world_slots.json 在册」立成机检断言。

范围：只判本模块文档结构自洽与跨源同源（不改调度语义）。同族判据：
test_module_m00_contract（冻结槽位面）/ test_module_m10/m23/m24_contract（通用类模板）/
test_registry_doc_contract（02 §2/§4/§6）/ test_schema_lint（check28）/ check16 / check24。
契约：六段结构、全局调度器 layer/mounts 约定、registry 与 02 §2/§4 对账、intent_received 在册、
world_model 四变量 slot 与全部 writes 在 world_slots.json 在册、相位迁移图闭合、io_types 规则推导、
P01/P90 层挂载不含 M50（不入 layers）。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import conformance_scan, io_types, pipeline_loader  # noqa: E402

M50 = ROOT / "04_模块库" / "通用类" / "M50_调度器.md"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
P90 = ROOT / "03_管线库" / "P90_结构装配管线.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
WORLD_SLOTS = ROOT / "protocol" / "world_slots.json"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 执行顺序", "## 3. 调度规则",
                     "## 4. 回合生命周期", "## 5. 违例与边界", "## 6. 事件契约")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "全球调度器".replace("球", "局"),
                    "world_model", "protocol/event_registry.json", "check16", "check28",
                    "intent_received", "PlayerState.memories", "调度器")


def load_text(path: Path = M50) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M50 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M50 为空")
    return text


def mc_block(text: str) -> str:
    m = re.search(FENCE + "yaml\n(machine_contract:.*?)\n" + FENCE, text, re.S)
    return m.group(1) if m else ""


def mc_dict(text: str) -> dict:
    block = mc_block(text)
    if not block or conformance_scan.yaml is None:
        return {}
    try:
        data = conformance_scan.yaml.safe_load(block)
    except Exception:  # YAML 坏件按缺块处理
        return {}
    return (data or {}).get("machine_contract") or {}


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
        if item.get("id") == "M50":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M50 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def dependency_lists() -> dict:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 4. 依赖关系", 1)[1].split("\n## 5.", 1)[0]
    m = re.search(r"  M50:\n    depends: \[(.*?)\]\n    depended_by: \[(.*?)\]", body)
    if not m:
        return {}
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    return {"depends": split(m.group(1)), "depended_by": split(m.group(2))}


def event_registry() -> dict:
    return json.loads((ROOT / "protocol" / "event_registry.json")
                      .read_text(encoding="utf-8"))["events"]


def world_slot_paths() -> set:
    data = json.loads(WORLD_SLOTS.read_text(encoding="utf-8"))
    return set(data.get("slots") or {})


def execution_mentions_m50() -> int:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return body.count("M50")


def layer_members() -> set:
    members = set()
    for doc in (P01, P90):
        parsed = pipeline_loader.parse_pipeline_md(doc.read_text(encoding="utf-8"))
        if parsed is None:
            continue
        for layer in parsed.layers:
            members |= set(layer.default_modules)
            members |= set(layer.allowed_modules)
    return members


def m50_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    mc = mc_dict(text)
    if mc.get("id") != "M50":
        issues.append(f"机读块 id 应为 M50（实测 {mc.get('id')!r}）")
    if mc.get("layer") != "调度器":
        issues.append(f"layer 应写「调度器」（全局调度器约定）：{mc.get('layer')!r}")
    events_block = mc.get("events") or {}
    if (events_block.get("publish") or []) != ["intent_received"]:
        issues.append(f"publish 应为 intent_received：{events_block.get('publish')}")
    if (events_block.get("subscribe") or []) != []:
        issues.append(f"subscribe 应为空：{events_block.get('subscribe')}")
    if (mc.get("interfaces") or []) != []:
        issues.append(f"有事件面的调度器 interfaces 应为 []：{mc.get('interfaces')}")
    outputs = [str(x) for x in (mc.get("outputs") or [])]
    parsed_io = io_types.parse_io_types(text)
    if parsed_io is None:
        issues.append("缺 io_types 类型面")
    else:
        ev_types = io_types.event_field_types(str(ROOT))
        expected = io_types.derive(outputs, [str(x) for x in (mc.get("inputs") or [])], ev_types)
        if parsed_io != expected:
            issues.append("io_types 未按「同名事件字段」规则推导")
    quote = quote_fields(text)
    if quote.get("类别") != mc.get("category"):
        issues.append(f"引用块类别 {quote.get('类别')!r} ≠ 机读块 {mc.get('category')!r}")
    reg = registry_module()
    if not reg:
        issues.append("registry.json 缺 M50 模块条目")
    else:
        if reg.get("name") != mc.get("name") or reg.get("category") != mc.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        if not reg.get("scheduler"):
            issues.append("registry.json M50 应标记 scheduler:true")
        if reg.get("mounts"):
            issues.append("registry.json M50 mounts 应为空（全局调度器不入 layers）："
                           f"{reg.get('mounts')}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M50 模块表行")
    else:
        if row[1] != mc.get("name") or row[2] != mc.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "调度器" not in row[4]:
            issues.append(f"02 §2 挂载点应写「调度器（全局）」：{row[4]}")
    deps = dependency_lists()
    if not deps:
        issues.append("02 §4 缺 M50 依赖关系段")
    else:
        if deps.get("depends") != [str(x) for x in (mc.get("inputs") or [])]:
            issues.append(f"02 §4 depends 与机读 inputs 不一致：{deps.get('depends')}")
        quote_dep = quote.get("被依赖") or ""
        quote_ids = [x.strip() for x in quote_dep.split("、") if x.strip() and x.strip() != "无"]
        if quote_ids != deps.get("depended_by"):
            issues.append(f"引用块被依赖与 02 §4 不一致：{quote_ids} ≠ {deps.get('depended_by')}")
    wm = mc.get("world_model") or {}
    variables = (wm.get("abstract_state") or {}).get("variables") or []
    if len(variables) < 4:
        issues.append(f"world_model 抽象状态变量不足四个：{len(variables)}")
    registered = world_slot_paths()
    for var in variables:
        slot = var.get("slot") if isinstance(var, dict) else None
        if slot not in registered:
            issues.append(f"抽象状态 slot 未在 world_slots.json 在册：{slot}")
    phases = [p.get("phase") for p in ((wm.get("transition") or {}).get("phases") or [])]
    if phases != ["begin", "run", "end", "archive", "roll"]:
        issues.append(f"相位图应为 begin/run/end/archive/roll：{phases}")
    for step in ((wm.get("transition") or {}).get("phases") or []):
        for write in (step.get("writes") or []):
            if write not in registered:
                issues.append(f"transition.writes 未在 world_slots.json 在册：{write}")
    checks = wm.get("checks") or []
    check_values = set()
    for check in checks:
        for value in (check.get("values") or []):
            check_values.add(value)
    if check_values and check_values != set(phases):
        issues.append(f"finite_phase 值域与相位图不一致：{sorted(check_values)}")
    if not (wm.get("invariants") or []):
        issues.append("world_model 缺 invariants")
    events = event_registry()
    if "intent_received" not in events:
        issues.append("intent_received 未在 event_registry 在册")
    else:
        registry_fields = set(((events.get("intent_received") or {}).get("fields") or {}).keys())
        if set(outputs) != registry_fields:
            issues.append("outputs 与 intent_received 载荷字段不同集："
                           f"{outputs} ≠ {sorted(registry_fields)}")
    if execution_mentions_m50() < 3:
        issues.append("02 §6 执行顺序应三处提及 M50（初始化/调度开始/回卷）")
    if "M50" in layer_members():
        issues.append("M50 不应出现在 P01/P90 任何层的 default/allowed 中（不入 layers）")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM50ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()
        self.mc = mc_dict(self.text)

    def test_m50_matches_contract(self):
        self.assertEqual([], m50_issues(self.text), "M50 不满足模块契约")

    def test_world_model_paths_are_registered(self):
        registered = world_slot_paths()
        wm = self.mc.get("world_model") or {}
        for var in ((wm.get("abstract_state") or {}).get("variables") or []):
            self.assertIn(var.get("slot"), registered, var.get("name"))
        for step in ((wm.get("transition") or {}).get("phases") or []):
            for write in (step.get("writes") or []):
                self.assertIn(write, registered, step.get("phase"))

    def test_global_scheduler_is_not_layer_mounted(self):
        self.assertTrue(registry_module().get("scheduler"))
        self.assertEqual([], registry_module().get("mounts"))
        self.assertNotIn("M50", layer_members())

    def test_contract_catches_mutations(self):
        """变异自证：slot 漂移 / writes 漂移 / publish 漂移 / layer 漂移 / 缺段 / 围栏。"""
        bad_slot = self.text.replace("slot: data_bus.active_pipeline",
                                     "slot: data_bus.pipeline", 1)
        self.assertTrue(any("slot" in i for i in m50_issues(bad_slot)))
        bad_write = self.text.replace("writes: [PlayerState.memories.working]",
                                      "writes: [memory.working]", 1)
        self.assertTrue(any("writes" in i for i in m50_issues(bad_write)))
        bad_publish = self.text.replace("    publish: [intent_received]",
                                        "    publish: [x_event]", 1)
        self.assertTrue(any("publish" in i or "在册" in i for i in m50_issues(bad_publish)))
        bad_layer = self.text.replace("  layer: 调度器", "  layer: P30", 1)
        self.assertTrue(any("layer" in i for i in m50_issues(bad_layer)))
        no_section = self.text.replace("## 6. 事件契约", "## 6. 事件")
        self.assertTrue(any("缺段" in i for i in m50_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m50_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m50.md")


if __name__ == "__main__":
    unittest.main()
