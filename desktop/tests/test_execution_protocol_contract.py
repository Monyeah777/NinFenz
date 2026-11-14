#!/usr/bin/env python3
"""06 Agent 执行协议契约：运行时协议必须「节号可寻址、判据件在场、校验词同源」。

为什么必须有：06 是执行 Agent 的唯一运行时协议（13 节），但此前零结构判据——读法顺序、
「哪节由哪条 check / 哪个测试件守着」都要靠人记；而 verify.sh check4/check5 实际是**按 06
的措辞词表**做跨文档一致性断言的（06 §4 五层名 / §5 gate 三态 + 降级词）。实测本轮补的真缺口：
§10 标题前缺空行、读法与机检映射缺失、RFC Date 与最后更新停留在 2026-09-08。

范围：只判本文件的结构自洽与判据同源（不改执行语义）。同族判据：
test_core_protocol_contract（01）/ test_registry_doc_contract（02）/
test_doc_reachability（全仓路径与 nf 命令）/ verify.sh check4·check5（措辞一致性）。
契约：读法段与十三节按序、11.1–11.4 在场、映射表件逐条存在、check4/check5 词表逐词在场、
§9 红线锚点在场、RFC Date == 最后更新、围栏配平、裸 § 引用可解析。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "06_Agent执行协议.md"
VERIFY = ROOT / "verify.sh"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 读法（本文件怎么用、怎么验）",
                     "## 0. 输入信任边界", "## 1. 角色定位", "## 2. 启动装载",
                     "## 3. 回合执行", "## 4. 可见性强制四层", "## 5. 输出质检门",
                     "## 6. 错误处理", "## 7. 状态持久化", "## 8. 与前端",
                     "## 9. 红线清单", "## 10. 修改规程", "## 11. 判级器与回合状态头",
                     "## 12. 内容安全边界")
SUBSECTIONS = ("### 11.1 判级器", "### 11.2 回合状态头", "### 11.3 引用后执行",
               "### 11.4 中断重入与幂等")
#: check10 对 §9 的两条硬锚点（关系隔离三落点之一）
RED_LINE_ANCHORS = ("v0.7.12", "关系推进权归 M40/M41")
REQUIRED_MARKERS = ("本文件怎么用、怎么验", "引用约定", "协议执行者", "最后更新：")


def load_text(path: Path = PROTOCOL) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"06_Agent执行协议 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("06_Agent执行协议 为空")
    return text


def check_funcs(verify_text: str) -> set:
    return set(re.findall(r"^(check\d+)\(\)\{", verify_text, re.M))


def check_body(verify_text: str, name: str) -> str:
    m = re.search(r"^" + name + r"\(\)\{(.*?)^\}", verify_text, re.S | re.M)
    return m.group(1) if m else ""


def cross_tokens(verify_text: str) -> tuple:
    """check4 / check5 里按 06 措辞做跨文档断言的词（机检真源）。"""
    vis = re.findall(r"token\s+06_Agent执行协议\.md\s+(\S+)",
                     check_body(verify_text, "check4"))
    gate = re.findall(r"token\s+06_Agent执行协议\.md\s+(\S+)",
                      check_body(verify_text, "check5"))
    return vis, gate


def mapping_rows(text: str) -> list:
    if "## 读法" not in text:
        return []
    body = text.split("## 读法", 1)[1].split("\n## ", 1)[0]
    return [ln.strip() for ln in body.splitlines()
            if ln.strip().startswith("| §") and "---" not in ln]


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
            continue
        refs.append(m.group(1))
    return refs


def execution_issues(text: str, verify_text: str = None) -> list:
    if verify_text is None:
        verify_text = VERIFY.read_text(encoding="utf-8")
    issues = []
    positions = [text.find(s) for s in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺节：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("十三节顺序不对")
    for sub in SUBSECTIONS:
        if sub not in text:
            issues.append(f"缺小节：{sub}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for anchor in RED_LINE_ANCHORS:
        if anchor not in text:
            issues.append(f"§9 缺红线锚点：{anchor}")
    funcs = check_funcs(verify_text)
    rows = mapping_rows(text)
    if len(rows) < 13:
        issues.append(f"机检映射表不足 13 行（实测 {len(rows)} 行）")
    for row in rows:
        for num in re.findall(r"check(\d+)", row):
            if "check" + num not in funcs:
                issues.append(f"映射引用了不存在的检查：check{num}")
        for name in re.findall(r"[" + chr(96) + r"](test_[a-z0-9_]+)[" + chr(96) + r"]", row):
            if not (ROOT / "desktop" / "tests" / f"{name}.py").is_file():
                issues.append(f"映射引用了不存在的测试件：{name}.py")
        path_pat = "[" + chr(96) + r"]([A-Za-z0-9_./\-]+\.(?:md|json))[" + chr(96) + r"]"
        for path in re.findall(path_pat, row):
            if not (ROOT / path).is_file():
                issues.append(f"映射引用了不在场的件：{path}")
    vis, gate = cross_tokens(verify_text)
    if len(vis) < 5 or len(gate) < 4:
        issues.append(f"check4/check5 的 06 措辞词表解析失败（vis={len(vis)} gate={len(gate)}）")
    for word in vis + gate:
        if word not in text:
            issues.append(f"06 缺 check 断言词：{word}")
    ids = section_ids(text)
    for ref in sorted(set(bare_refs(text))):
        if ref not in ids:
            issues.append(f"§引用无法解析：§{ref}")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    updated = re.search(r"> 最后更新：(\d{4}-\d{2}-\d{2})", text)
    rfc = re.search(r"\*\*Date\*\*: (\d{4}-\d{2}-\d{2})", text)
    if not updated or not rfc:
        issues.append("缺最后更新 / RFC Date")
    elif updated.group(1) != rfc.group(1):
        issues.append(f"RFC Date 与最后更新不一致：{rfc.group(1)} ≠ {updated.group(1)}")
    if "---\n---" in text:
        issues.append("出现重复分隔线")
    return issues


class ExecutionProtocolContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_execution_protocol_matches_contract(self):
        self.assertEqual([], execution_issues(self.text), "06 不满足执行协议契约")

    def test_sections_and_checks_resolve(self):
        positions = [self.text.find(s) for s in REQUIRED_SECTIONS]
        self.assertTrue(all(p >= 0 for p in positions), "十三节不全")
        self.assertEqual(sorted(positions), positions, "十三节顺序不对")
        funcs = check_funcs(VERIFY.read_text(encoding="utf-8"))
        for row in mapping_rows(self.text):
            for num in re.findall(r"check(\d+)", row):
                self.assertIn("check" + num, funcs)

    def test_cross_doc_tokens_are_same_source(self):
        vis, gate = cross_tokens(VERIFY.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(vis), 5, "check4 05 06 措辞词表解析失败")
        for word in vis + gate:
            self.assertIn(word, self.text, f"06 缺 check 断言词：{word}")

    def test_contract_catches_mutations(self):
        """变异自证：读法 / 可见性词 / gate 词 / 日期 / 测试件 / §引用 / 围栏 七类漂移。"""
        no_readme = self.text.replace("## 读法（本文件怎么用、怎么验）", "## 前言")
        self.assertTrue(any("读法" in i for i in execution_issues(no_readme)))
        no_vis = self.text.replace("事实管线", "事实流")
        self.assertTrue(any("断言词：事实管线" in i for i in execution_issues(no_vis)))
        no_gate = self.text.replace("最小可读", "降级输出")
        self.assertTrue(any("断言词：最小可读" in i for i in execution_issues(no_gate)))
        bad_date = self.text.replace("> 最后更新：2026-11-12", "> 最后更新：2026-10-01")
        self.assertTrue(any("更新" in i for i in execution_issues(bad_date)))
        bad_test = self.text.replace("`test_round_header`", "`test_round_missing`", 1)
        self.assertTrue(any("测试件" in i for i in execution_issues(bad_test)))
        dangling = self.text + "\n见 §13.1 说明。\n"
        self.assertTrue(any("§13.1" in i for i in execution_issues(dangling)))
        odd_fence = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in execution_issues(odd_fence)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_execution_protocol.md")


if __name__ == "__main__":
    unittest.main()
