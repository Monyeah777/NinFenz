#!/usr/bin/env python3
"""M80 输出质检门模块契约：唯一输出闸 + 声明式 gate_action + 零事件固定节点豁免理由。

为什么必须有：M80 是唯一输出闸（I2 核心固定），所有域（含文档线经 M90）产出都不可绕过它；
它也是零事件模块（events 双空、interfaces []）——按 01 §1.1 零事件模块须以 interfaces 补全
联动面或显式 []（纯内部模块），M80 既非纯内部也不宜虚构查询接口，故必须以**显式理由**说明
「不属以空契约脱离联动面」。实测本轮无字段缺项，价值在把「豁免理由在场 / gate_action 唯一真源 /
8 段判定记录格式 / 结构门硬门不可关」立成机检断言。

范围：只判本模块文档结构自洽与跨源同源（不改门禁语义）。同族判据：
test_module_m00_contract（基座豁免模板）/ test_module_m50_contract（固定节点模板）/
test_pipeline_p90_contract（gate_action 引用方）/ test_registry_doc_contract（02 §2/§4/§5/§6）/
test_schema_lint（check28）/ check16。
契约：五段结构（含 2.1/2.2 双门）、零事件 + interfaces [] + 豁免理由在场、registry 与 02 §2 一致、
02 §4 depends/depended_by 对账、02 §5/§6 在册、L2 可证、gate_action 三档 action 与失败语义在场、
8 段判定记录格式、结构门五项与 M23 前置校验在场。
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

M80 = ROOT / "04_模块库" / "通用类" / "M80_输出质检门.md"
P01 = ROOT / "03_管线库" / "P01_标准管线.md"
P90 = ROOT / "03_管线库" / "P90_结构装配管线.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
REGISTRY_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 1. 职责", "## 2. 质检双门", "### 2.1 结构门", "### 2.2 质量门",
                     "## 3. 质检门", "## 4. 输出格式", "## 5. 违例与边界")
REQUIRED_MARKERS = ("machine_contract", "机读投影", "三形态", "零事件固定节点口径",
                    "不对外提供查询接口", "I2", "I4", "I5", "M23",
                    "gate_action", "fallback: minimal")
STRUCTURE_CHECKS = ("编号合法", "引用可寻址", "结构完整", "术语一致", "无越层直写")


def load_text(path: Path = M80) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M80 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M80 为空")
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
        if item.get("id") == "M80":
            return item
    return {}


def doc_row() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| M80 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def dependency_lists() -> dict:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 4. 依赖关系", 1)[1].split("\n## 5.", 1)[0]
    m = re.search(r"  M80:\n    depends: \[(.*?)\]\n    depended_by: \[(.*?)\]", body)
    if not m:
        return {}
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    return {"depends": split(m.group(1)), "depended_by": split(m.group(2))}


def p80_default() -> list:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 5. 挂载点", 1)[1].split("\n## 6.", 1)[0]
    m = re.search(r"^  P80 [^:]+:\s*\{default: \[(.*?)\]", body, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def execution_mentions_m80() -> int:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 6. 当前执行顺序", 1)[1].split("\n## 7.", 1)[0]
    return body.count("M80")


def gate_section(text: str) -> str:
    m = re.search(r"## 3\. 质检门[\s\S]*?## 4\.", text)
    return m.group(0) if m else ""


def decision_segments(text: str) -> list:
    line = next((ln for ln in text.splitlines() if "gate|" in ln and "<流水号>" in ln), "")
    return [seg.strip() for seg in line.split("|") if seg.strip()]


def m80_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    header = mc_fields(text)
    if header.get("id") != "M80":
        issues.append(f"机读块 id 应为 M80（实测 {header.get('id')!r}）")
    if (header.get("publish") or []) != [] or (header.get("subscribe") or []) != []:
        issues.append("零事件模块应显式双空")
    interfaces = header.get("interfaces") or []
    if interfaces == []:
        if "零事件固定节点口径" not in text or "不对外提供查询接口" not in text:
            issues.append("interfaces [] 缺显式豁免理由（零事件固定节点口径）")
    else:
        for name in interfaces:
            if name + "(" not in text:
                issues.append(f"interfaces 非空但缺正文接口签名：{name}")
    if (header.get("outputs") or []) != []:
        issues.append(f"outputs 应为空（门禁不产出数据槽字段）：{header.get('outputs')}")
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
        issues.append("registry.json 缺 M80 模块条目")
    else:
        if reg.get("name") != header.get("name") or reg.get("category") != header.get("category"):
            issues.append("registry.json 模块名/类别与机读块不一致")
        mounts = reg.get("mounts") or []
        if not any(m.get("layer") == "P80" and m.get("status") == "active" for m in mounts):
            issues.append(f"registry.json 挂载应为 P80/active：{mounts}")
    row = doc_row()
    if not row or len(row) < 5:
        issues.append("02 §2 缺 M80 模块表行")
    else:
        if row[1] != header.get("name") or row[2] != header.get("category"):
            issues.append(f"02 §2 行与机读块不一致：{row}")
        if "P80" not in row[4] or "active" not in row[4]:
            issues.append(f"02 §2 挂载与 registry 不一致：{row[4]}")
        if "输出" not in row[4]:
            issues.append(f"02 §2 应使用 P80 层名「输出」：{row[4]}")
    deps = dependency_lists()
    if not deps:
        issues.append("02 §4 缺 M80 依赖关系段")
    else:
        if deps.get("depends") != header.get("inputs"):
            issues.append(f"02 §4 depends 与机读 inputs 不一致：{deps.get('depends')}")
        quote_dep = quote.get("被依赖") or ""
        quote_ids = [x.strip() for x in quote_dep.split("、") if x.strip() and x.strip() != "无"]
        if quote_ids != deps.get("depended_by"):
            issues.append(f"引用块被依赖与 02 §4 不一致：{quote_ids} ≠ {deps.get('depended_by')}")
    if "M80" not in p80_default():
        issues.append(f"02 §5 P80 default 应含 M80：{p80_default()}")
    if execution_mentions_m80() < 1:
        issues.append("02 §6 执行顺序应含 M80")
    gate = gate_section(text)
    if not gate:
        issues.append("§3 质检门段不可解析")
    else:
        for action in ("pass:", "warn:", "fail:"):
            if action not in gate:
                issues.append(f"gate_action 缺档：{action}")
        if "retry_limit: 3" not in gate:
            issues.append("gate_action fail 档缺 retry_limit: 3")
        if "fallback: minimal" not in gate:
            issues.append("gate_action fail 档缺 fallback: minimal")
        for behavior in ("direct", "self_correct", "log_revision", "rewrite"):
            if behavior not in gate:
                issues.append(f"gate_action 缺 action：{behavior}")
    segments = decision_segments(text)
    if len(segments) != 8:
        issues.append(f"gate_decision_record 格式应为 8 段（实测 {len(segments)}）：{segments}")
    for check in STRUCTURE_CHECKS:
        if check not in text:
            issues.append(f"§2.1 结构门缺项：{check}")
    if "M23" not in text:
        issues.append("§3 缺 M23 可见性前置校验")
    for other in (P90,):
        body = other.read_text(encoding="utf-8")
        if "M80" not in body:
            issues.append(f"{other.name} 未引用 M80 唯一出口")
    p01 = P01.read_text(encoding="utf-8")
    default = re.search(r"id: P80[\s\S]*?default_modules: \[([^\]]*)\]", p01)
    if not default or "M80" not in default.group(1):
        issues.append("L2 不可证：P01 P80 default_modules 未引用 M80")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class ModuleM80ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m80_matches_contract(self):
        self.assertEqual([], m80_issues(self.text), "M80 不满足模块契约")

    def test_unique_gate_and_zero_event_waiver(self):
        header = mc_fields(self.text)
        self.assertEqual([], header.get("publish"))
        self.assertEqual([], header.get("subscribe"))
        self.assertIn("零事件固定节点口径", self.text)
        self.assertIn("不对外提供查询接口", self.text)

    def test_gate_action_is_single_source(self):
        gate = gate_section(self.text)
        for token in ("pass: [direct]", "warn: [self_correct, log_revision]",
                      "fail: [rewrite, retry_limit: 3, fallback: minimal]"):
            self.assertIn(token, gate)
        self.assertEqual(8, len(decision_segments(self.text)))

    def test_contract_catches_mutations(self):
        """变异自证：豁免理由缺失 / gate 档缺失 / 记录段数漂移 / 硬门缺失 / 缺段 / 围栏。"""
        no_waiver = self.text.replace("零事件固定节点口径",
                                      "固定节点口径", 1)
        self.assertTrue(any("豁免理由" in i for i in m80_issues(no_waiver)))
        no_retry = self.text.replace("fail: [rewrite, retry_limit: 3, fallback: minimal]",
                                     "fail: [rewrite, fallback: minimal]", 1)
        self.assertTrue(any("retry_limit" in i for i in m80_issues(no_retry)))
        short_record = self.text.replace(
            "格式: gate|<流水号>|tick|判定(pass/warn/fail)|命中项|修订点|重写次数|fallback",
            "格式: gate|<流水号>|tick|判定|命中项", 1)
        self.assertTrue(any("8 段" in i for i in m80_issues(short_record)))
        no_check = self.text.replace("- 编号合法", "- 编号检查", 1)
        self.assertTrue(any("结构门" in i for i in m80_issues(no_check)))
        no_section = self.text.replace("## 5. 违例与边界", "## 5. 边界")
        self.assertTrue(any("缺段" in i for i in m80_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in m80_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m80.md")


if __name__ == "__main__":
    unittest.main()
