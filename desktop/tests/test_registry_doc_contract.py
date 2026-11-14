#!/usr/bin/env python3
"""02 联动注册表契约：注册真相源必须「文档 ↔ 机读投影同源、引用可解析、格式可渲染」。

为什么必须有：02 是运行状态的唯一真相源（I5），但 1160 行文档此前零结构判据——§2 模块表 /
§3 订阅 / §5 挂载点与 registry.json 是否逐条一致、9 个一级节与 9.x 迁移记录是否齐全、
裸 § 引用是否悬空、围栏是否配平，全靠人眼。实测本轮补的真缺口：7 个一级标题前缺空行
（渲染面不干净）、两处裸 § 引用跨文件未标注来源、§7 下 12.5–12.7 的源文切片引用写成 § 形态。

范围：只判本文件的结构自洽与投影同源（不改任何注册语义）。同族判据：
test_core_protocol_contract（01）/ test_doc_reachability（全仓路径与 nf 命令）/
test_conformance_scan（规范件扫描）/ verify.sh check13（文档 ↔ json 一致性）。
契约：读法段与九节按序、9.x 迁移记录在场、机检映射表 check 真实、§2/§3/§5 与 registry.json
逐列表一致、头部版本号同源、RFC Date == 最后更新、围栏配平、裸 § 引用可解析。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG_DOC = ROOT / "02_联动注册表.md"
REG_JSON = ROOT / "desktop" / "src" / "core" / "registry.json"
VERIFY = ROOT / "verify.sh"

REQUIRED_SECTIONS = ("## 读法（本文件怎么用、怎么验）", "## 1. 当前活跃管线",
                     "## 2. 官方核心模块表", "## 3. 订阅关系", "## 4. 依赖关系",
                     "## 5. 挂载点", "## 6. 当前执行顺序", "## 7. 领域实例登记",
                     "## 8. 社区领域包登记表", "## 9. 机读投影 registry.json")
#: §9 迁移记录（外部按 §9.x 寻址）
SUBSECTIONS = tuple(f"### 9.{i} 迁移记录" for i in range(3, 7))
REQUIRED_MARKERS = ("唯一真相源（I5）", "机读投影", "引用约定", "registry_schema_version",
                    "最后更新：", "本文件怎么用、怎么验")
#: 投影同源：§2 / §3 / §5 与 registry.json 的对账口径（§9.1 字段映射）
FENCE = chr(96) * 3


def load_text(path: Path = REG_DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"02_联动注册表 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("02_联动注册表 为空")
    return text


def registry() -> dict:
    return json.loads(REG_JSON.read_text(encoding="utf-8"))


def section_body(text: str, heading: str, nxt: str) -> str:
    if heading not in text:
        return ""
    return text.split(heading, 1)[1].split(nxt, 1)[0]


def table_ids(text: str) -> list:
    """§2 模块表第一列（跳过表头与分隔行）。"""
    body = section_body(text, "## 2. 官方核心模块表", "\n## 3.")
    ids = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0] in ("模块ID", "") or set(cells[0]) <= {"-"}:
            continue
        ids.append(cells[0])
    return ids


def nested_keys(text: str, heading: str, nxt: str) -> list:
    body = section_body(text, heading, nxt)
    return re.findall(r"^  ([a-z][a-z0-9_]*):", body, re.M)


def mount_layers(text: str) -> list:
    body = section_body(text, "## 5. 挂载点", "\n## 6.")
    return re.findall(r"^  (P\d\d)", body, re.M)


def check_funcs(verify_text: str) -> set:
    return set(re.findall(r"^(check\d+)\(\)\{", verify_text, re.M))


def section_ids(text: str) -> set:
    ids = set()
    for line in text.splitlines():
        m = re.match(r"^#{2,3} (\d+(?:\.\d+)*)", line.strip())
        if m:
            ids.add(m.group(1))
    return ids


def bare_refs(text: str) -> list:
    refs = []
    for m in re.finditer(r"§(\d+(?:\.\d+)*)", text):
        before = text[max(0, m.start() - 24):m.start()]
        if re.search(r"[A-Za-z0-9_.]+ +$", before):
            continue            # 跨文件引用（01 §6 / CONTRIBUTING §4.4 等）
        refs.append(m.group(1))
    return refs


def mapping_rows(text: str) -> list:
    body = section_body(text, "## 读法", "\n## ")
    return [ln.strip() for ln in body.splitlines()
            if ln.strip().startswith("| §") and "---" not in ln]


def registry_issues(text: str, data: dict, verify_text: str = None) -> list:
    if verify_text is None:
        verify_text = VERIFY.read_text(encoding="utf-8")
    issues = []
    positions = [text.find(s) for s in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺节：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("九节顺序不对")
    for sub in SUBSECTIONS:
        if sub not in text:
            issues.append(f"缺迁移记录：{sub}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    version_match = re.search(r'registry_schema_version: "(\d+)"', text)
    doc_version = version_match.group(1) if version_match else ""
    json_version = str(data.get("registry_schema_version"))
    if doc_version != json_version:
        issues.append(f"头部版本号与 registry.json 不一致：{doc_version!r} ≠ {json_version!r}")
    json_ids = [str(m.get("id")) for m in (data.get("modules") or [])]
    if table_ids(text) != json_ids:
        issues.append(f"§2 模块表与 registry.json modules 不一致：{table_ids(text)} ≠ {json_ids}")
    json_subs = list((data.get("subscriptions") or {}).keys())
    if nested_keys(text, "## 3. 订阅关系", "\n## 4.") != json_subs:
        issues.append("§3 订阅键与 registry.json subscriptions 不一致")
    json_mounts = list((data.get("mount_points") or {}).keys())
    if mount_layers(text) != json_mounts:
        issues.append("§5 挂载层与 registry.json mount_points 不一致："
                       f"{mount_layers(text)} ≠ {json_mounts}")
    ids = section_ids(text)
    for ref in sorted(set(bare_refs(text))):
        if ref not in ids:
            issues.append(f"§引用无法解析：§{ref}")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平（围栏标记为奇数）")
    funcs = check_funcs(verify_text)
    rows = mapping_rows(text)
    if len(rows) < 9:
        issues.append(f"机检映射表不足 9 行（实测 {len(rows)} 行）")
    for row in rows:
        for num in re.findall(r"check(\d+)", row):
            if "check" + num not in funcs:
                issues.append(f"机检映射引用了不存在的检查：check{num}")
    updated = re.search(r"> 最后更新：(\d{4}-\d{2}-\d{2})", text)
    rfc_date = re.search(r"\*\*Date\*\*: (\d{4}-\d{2}-\d{2})", text)
    if not updated or not rfc_date:
        issues.append("缺最后更新 / RFC Date")
    elif updated.group(1) != rfc_date.group(1):
        issues.append(f"RFC Date 与最后更新不一致：{rfc_date.group(1)} ≠ {updated.group(1)}")
    if "---\n---" in text:
        issues.append("出现重复分隔线")
    return issues


class RegistryDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()
        self.data = registry()

    def test_registry_doc_matches_contract(self):
        self.assertEqual([], registry_issues(self.text, self.data), "02 不满足注册表契约")

    def test_projection_is_same_source(self):
        self.assertEqual([], registry_issues(self.text, self.data))

    def test_sections_and_checks_resolve(self):
        positions = [self.text.find(s) for s in REQUIRED_SECTIONS]
        self.assertTrue(all(p >= 0 for p in positions), "九节不全")
        self.assertEqual(sorted(positions), positions, "九节顺序不对")
        funcs = check_funcs(VERIFY.read_text(encoding="utf-8"))
        for row in mapping_rows(self.text):
            for num in re.findall(r"check(\d+)", row):
                self.assertIn("check" + num, funcs)

    def test_contract_catches_mutations(self):
        """变异自证：模块表 / 版本 / 读法 / check / §引用 / 围栏 / 日期 七类漂移。"""
        drift = self.text.replace("| M00 |", "| M99 |", 1)
        self.assertTrue(any("§2" in i for i in registry_issues(drift, self.data)))
        claim = 'registry_schema_version: "2"'
        bad_version = self.text.replace(claim, 'registry_schema_version: "3"', 1)
        self.assertTrue(any("版本号" in i for i in registry_issues(bad_version, self.data)))
        no_readme = self.text.replace("## 读法（本文件怎么用、怎么验）", "## 前言")
        self.assertTrue(any("读法" in i for i in registry_issues(no_readme, self.data)))
        fake = self.text.replace("check13 · check14", "check99 · check14", 1)
        self.assertTrue(any("check99" in i for i in registry_issues(fake, self.data)))
        dangling = self.text + "\n见 §7.9 说明。\n"
        self.assertTrue(any("§7.9" in i for i in registry_issues(dangling, self.data)))
        odd_fence = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in registry_issues(odd_fence, self.data)))
        bad_date = self.text.replace("> 最后更新：2026-11-12", "> 最后更新：2026-10-01")
        self.assertTrue(any("更新" in i for i in registry_issues(bad_date, self.data)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_registry_doc.md")


if __name__ == "__main__":
    unittest.main()
