"""CCOS ABI 文档一致性判据（文档 ↔ 实装 ↔ 判据三元对账）。

为什么有它：docs/ccos/ 是结果面，abi-v0.md 自定判据「任一调用的实装状态字段与实际能力不符
即视为本文失真」。但此前这些声称没有被门禁判过，已实测出三类漂移：
① 单测项数写旧（37/12/10 对实测 52/18/22）；② abi-v0 声明了 cc.<syscall>.<reason> 错误面，
而 protocol/error_codes.json 是空表；③ 跨文档引用了 docs/layers.md 不存在的 L0–L5 分层。

本测试把「文档与仓库同源」变成可判事实：改文档不改测试/实现，红就是应该的。
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "desktop" / "src"))
sys.path.insert(0, str(_REPO / "desktop"))
sys.path.insert(0, str(_REPO / "desktop" / "tests"))

_DOCS = _REPO / "docs" / "ccos"
_REGISTRY = _REPO / "protocol" / "error_codes.json"

#: ABI 的 7 个调用；少一个/多一个都算文档失真
CALLS = {"cc_label", "cc_check", "cc_attest", "cc_verify", "cc_replay", "cc_diff", "cc_resolve"}
#: 实装状态词表；unimplemented 只用于如实挂账，不允许悄悄使用
STATUSES = {"implemented", "partial", "unimplemented"}
#: docs/layers.md 已明令不复用的旧分层词汇
BANNED_LAYERS = ("L0–L5", "L0-L5")

_CALL_RE = re.compile(r"^### \d+\. `(cc_[a-z_]+)\([^)]*\)`")
_STATUS_RE = re.compile(r"\*\*状态：`([a-z_]+)`")
_CODE_RE = re.compile(r"cc\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")
_COUNT_RE = re.compile(r"test_([a-z0-9_]+)[^\n0-9]{0,80}?(\d+)\s*项")


def _read(path):
    return path.read_text(encoding="utf-8")


def _count_tests(module):
    """→ 该测试模块的用例数；模块不可导入 → None（由调用方判红）。"""
    import importlib
    for name in ("tests.test_" + module, "desktop.tests.test_" + module, "test_" + module):
        try:
            importlib.import_module(name)
        except ImportError:
            continue
        try:
            return unittest.defaultTestLoader.loadTestsFromName(name).countTestCases()
        except Exception:  # 加载失败按「无法核对」处理（不做断言，返回 None）
            return None
    return None


class AbiDocConsistencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.abi = _read(_DOCS / "abi-v0.md")
        cls.registry = json.loads(_read(_REGISTRY))
        cls.codes = {str(e.get("id") or "") for e in (cls.registry.get("codes") or [])}

    def test_seven_calls_have_expected_ids_and_status(self):
        found = {}
        current = None
        for line in self.abi.splitlines():
            m = _CALL_RE.match(line)
            if m:
                current = m.group(1)
                continue
            if current:
                s = _STATUS_RE.search(line)
                if s:
                    found[current] = s.group(1)
                    current = None
        self.assertEqual(sorted(found), sorted(CALLS), "ABI 的 7 个调用节缺失或被改名")
        self.assertEqual(sorted(set(found.values()) - STATUSES), [],
                         "实装状态词表越界（只许 implemented/partial/unimplemented）")
        self.assertEqual(found.get("cc_label"), "partial",
                         "cc_label 状态须如实为 partial（修复指引：先实现载体写入再改状态）")

    def test_every_declared_error_code_is_registered(self):
        declared = set()
        for path in sorted(_DOCS.glob("*.md")):
            declared |= set(_CODE_RE.findall(_read(path)))
        self.assertTrue(declared, "docs/ccos 应声明至少一个 cc.* 错误码")
        self.assertTrue(self.codes, "错误码登记表不得为空（修复指引：登记 ABI 错误面）")
        self.assertEqual(sorted(declared - self.codes), [],
                         "ABI 声明了未登记的错误码（修复指引：在 protocol/error_codes.json 登记）")

    def test_registry_passes_central_validation(self):
        from core import error_codes as E
        self.assertEqual([], E.validate(self.registry))

    def test_documented_unittest_counts_match_reality(self):
        claims = []
        for path in sorted(_DOCS.glob("*.md")):
            for i, line in enumerate(_read(path).splitlines(), 1):
                m = _COUNT_RE.search(line)
                if m:
                    claims.append((path.name, i, m.group(1), int(m.group(2))))
        self.assertTrue(claims, "未从 docs/ccos 解析到任何单测项数声明")
        bad = []
        for name, line_no, module, claimed in claims:
            actual = _count_tests(module)
            if actual is None:
                bad.append(f"{name}:{line_no} {module} 无法找到"
                           "（修复指引：改文档指向真实模块）")
            elif actual != claimed:
                bad.append(f"{name}:{line_no} {module} 写 {claimed} 项，"
                           f"实测 {actual} 项（修复指引：改文档或补测试）")
        self.assertEqual(bad, [])

    def test_no_abolished_layering_vocabulary(self):
        hits = []
        for path in sorted(_DOCS.glob("*.md")):
            for i, line in enumerate(_read(path).splitlines(), 1):
                if any(token in line for token in BANNED_LAYERS):
                    hits.append(f"{path.name}:{i}")
        self.assertEqual(hits, [], "docs/ccos 不得复用已废止的 L0–L5 词汇（修复指引：改用四阶）")


    def test_documented_vector_count_matches_vectors(self):
        """文档写的「N 条向量/固定用例」必须等于向量集实际 count（补向量忘改文档即红）。"""
        vectors = json.loads((_REPO / "results/ccos/evidence_verdict_vectors.json")
                             .read_text(encoding="utf-8"))
        count = int(vectors["count"])
        bad = []
        for path in sorted(_DOCS.glob("*.md")):
            for i, line in enumerate(_read(path).splitlines(), 1):
                if not any(k in line for k in ("向量", "固定用例", "与实现")):
                    continue
                for m in re.finditer(r"(\d+)\s*条", line):
                    if int(m.group(1)) != count:
                        bad.append(f"{path.name}:{i} 写 {m.group(1)} 条，向量集实为 {count}")
        self.assertEqual(bad, [], "向量条数口径漂移（修复指引：改文档数字或补向量）")

    def test_maps_to_commands_are_reachable(self):
        cmds = set(re.findall(r"`nf ([a-z][a-z0-9-]*)", self.abi))
        self.assertTrue(cmds, "未从 abi-v0 解析到任何 nf 命令")
        proc = subprocess.run([sys.executable, str(_REPO / "scripts" / "nf.py"), "--help"],
                              cwd=str(_REPO), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(proc.returncode, 0, "nf --help 跑不通（修复指引：检查 scripts/nf.py）")
        lists = re.findall(r"\{([a-z0-9,\-]+)\}", proc.stdout)
        cmd_list = next((x for x in lists if "cockpit" in x.split(",")), None)
        self.assertIsNotNone(cmd_list,
                             "nf --help 的命令面不可解析（修复指引：保持 usage 花括号列表）")
        top = set(cmd_list.split(","))
        self.assertEqual(sorted(cmds - top), [],
                         "ABI 的 maps_to 指向不存在的顶层命令（修复指引：命令改名或改 maps_to）")
