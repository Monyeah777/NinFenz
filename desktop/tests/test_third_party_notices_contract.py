#!/usr/bin/env python3
"""第三方声明契约判据：notices 须与锁文件双向一致、许可可机读、生成器 fail-closed（2026-11-10）。

为什么必须有：THIRD-PARTY-NOTICES.md 随 npm 包分发，但它由生成器写、没有判据——实测曾把
「（查询失败：URLError）」写进 34/44 行并提交（降级当结果），且 pin 版本与文档版本漂移。
本件把「一份能用的第三方声明」钉成契约：结构、双向一致、新鲜度、许可可机读、fail-closed。

范围：只判 THIRD-PARTY-NOTICES.md；生成器逻辑复用 scripts/gen_third_party_notices.py 的
pins()/lock_digest()（单一真源，不在判据里重写一份）。
"""
import contextlib
import io
import json
import re
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"
PYPROJECT = ROOT / "pyproject.toml"
NPM_PKG = ROOT / "packaging" / "npm" / "package.json"
BT = chr(96)

sys.path.insert(0, str(ROOT / "scripts"))
import gen_third_party_notices as gen  # noqa: E402  （判据复用生成器的锁与 pin 真源）

#: 生成降级时才会出现的占位串（出现即说明「失败被当成结果」）
FAILURE_TOKENS = ("查询失败", "URLError", "IncompleteRead", "HTTPError", "Traceback")
#: 清单行：| `name` | version | **license** | 主页 |
ROW = re.compile(r"^\| " + BT + r"([^" + BT + r"]+)" + BT
                   + r" \| ([^|]+) \| \*\*(.+?)\*\* \| (.+?) \|$")
#: SPDX 词法：id / AND / OR / WITH / 括号
SPDX_ID = re.compile(r"^[A-Za-z0-9.+-]+$")


def load_text(path: Path = NOTICES) -> str:
    """读 notices（缺失 / 空件显式报错）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"第三方声明不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("第三方声明为空")
    return text


def parse_rows(text: str) -> list:
    """清单表 → [(name, version, license, home)]。"""
    rows = []
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            rows.append((m.group(1).strip(), m.group(2).strip(),
                         m.group(3).strip(), m.group(4).strip()))
    return rows


def spdx_ok(lic: str) -> bool:
    """许可是否可机读（SPDX id / 表达式；LicenseRef 也按 id 词法收）。"""
    tokens = lic.replace("(", " ").replace(")", " ").split()
    return bool(tokens) and all(t in ("AND", "OR", "WITH") or SPDX_ID.match(t) for t in tokens)


def notices_issues(text: str, root: Path = ROOT) -> list:
    """第三方声明契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    for section in ("## 归属声明", "## 范围说明", "## 清单", "## 许可注意项", "## 更新方式"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    for marker in ("gen_third_party_notices.py", "results/ccos/sbom.json", "fail-closed",
                   "Local Modifications", "sha256:"):
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    # 只查清单行：文件头有一句「不会把『查询失败』写进本文件」的**否定**说明，不能误报
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        for token in FAILURE_TOKENS:
            if token in line:
                issues.append(f"清单行出现生成降级占位：{token}（失败必须不写盘）")
    rows = parse_rows(text)
    if not rows:
        return issues + ["清单为空或表格格式不符"]
    names = [name.lower() for name, _v, _l, _h in rows]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    if duplicated:
        issues.append(f"组件重复：{duplicated}")
    pins = {n.lower(): v for n, v in gen.pins()}
    doc = {name.lower(): (version, lic) for name, version, lic, _h in rows}
    missing = sorted(set(pins) - set(doc))
    extra = sorted(set(doc) - set(pins))
    if missing:
        issues.append(f"锁文件里的依赖未列入 notices：{missing[:5]}")
    if extra:
        issues.append(f"notices 列了锁文件里没有的组件：{extra[:5]}")
    for name, version in sorted(pins.items()):
        if name in doc and doc[name][0] != version:
            issues.append(f"版本与 pin 不一致：{name} {doc[name][0]!r} ≠ {version!r}")
    digest = re.search(r"sha256:([0-9a-f]{16})", text)
    if not digest:
        issues.append("缺锁文件摘要（新鲜度锚）")
    elif digest.group(1) != gen.lock_digest():
        issues.append("锁文件摘要过期：pin 变了但 notices 未重生成")
    manual = text.split("需人工核对上游 LICENSE", 1)[1] if "需人工核对上游 LICENSE" in text else ""
    dual = text.split("双许可选择", 1)[1] if "双许可选择" in text else ""
    for name, _version, lic, _home in rows:
        if lic.endswith("（上游 classifier 原文）"):
            if lic not in manual:
                issues.append(f"{name} 的许可未在「需人工核对」段点名：{lic}")
        elif not spdx_ok(lic):
            issues.append(f"{name} 的许可不可机读（非 SPDX）：{lic}")
        if " OR " in lic.upper() and lic not in dual:
            issues.append(f"{name} 的双许可未在「双许可选择」段表态：{lic}")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")) or {}
    runtime_deps = (project.get("project") or {}).get("dependencies") or []
    if runtime_deps:
        issues.append("文档声称运行时零依赖，但 pyproject.dependencies 非空")
    npm = json.loads((root / "packaging" / "npm" / "package.json").read_text(encoding="utf-8"))
    if npm.get("dependencies"):
        issues.append("文档声称 npm 包零依赖，但 package.json 有 dependencies")
    return issues


class ThirdPartyNoticesContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_notices_matches_contract(self):
        self.assertEqual([], notices_issues(self.text), "第三方声明不满足契约")

    def test_pins_two_way(self):
        """双向一致：锁文件 pin 集合 ⇄ notices 组件集合，版本逐字相等。"""
        pins = {name.lower(): version for name, version in gen.pins()}
        rows = parse_rows(self.text)
        doc = {name.lower(): version for name, version, _l, _h in rows}
        self.assertEqual(set(pins), set(doc), "组件集合与锁文件不一致")
        for name in pins:
            self.assertEqual(pins[name], doc[name], f"{name} 版本与 pin 不一致")

    def test_freshness_digest(self):
        """文件头锁摘要必须等于现算摘要（pin 一变即红）。"""
        m = re.search(r"sha256:([0-9a-f]{16})", self.text)
        self.assertIsNotNone(m, "缺锁文件摘要")
        self.assertEqual(gen.lock_digest(), m.group(1), "锁文件摘要过期")

    def test_licenses_machine_readable(self):
        """每行许可要么 SPDX 可读，要么显式标「上游原文」并被点名人工核对。"""
        manual = self.text.split("需人工核对上游 LICENSE", 1)[1] \
            if "需人工核对上游 LICENSE" in self.text else ""
        for name, _v, lic, _h in parse_rows(self.text):
            if lic.endswith("（上游 classifier 原文）"):
                self.assertIn(lic, manual, f"{name} 的许可未点名人工核对")
            else:
                self.assertTrue(spdx_ok(lic), f"{name} 的许可不可机读：{lic}")

    def test_generator_fails_closed(self):
        """生成器任一查询失败：不写盘且返回非零（降级结果不许落盘）。"""
        original_pypi, original_out = gen.pypi, gen.OUT
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "notices.md"
            gen.OUT = out
            gen.pypi = lambda name: (_ for _ in ()).throw(RuntimeError("simulated"))
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    rc = gen.main(["--write"])
            finally:
                gen.pypi, gen.OUT = original_pypi, original_out
            self.assertNotEqual(0, rc, "查询失败时生成器必须返回非零")
            self.assertFalse(out.exists(), "查询失败时生成器不得写盘")

    def test_contract_catches_broken_notices(self):
        """变异自证：失败占位 / 删组件 / 版本漂移 / 摘要过期 / 删生成器标识——都必须报。"""
        first = parse_rows(self.text)[0]
        row = f"| {BT}{first[0]}{BT} | {first[1]} | **{first[2]}** | {first[3]} |"
        self.assertIn(row, self.text, "表格行格式与解析器不一致")
        broken_license = self.text.replace(row, f"| {BT}{first[0]}{BT} | {first[1]} | "
                                            f"**（查询失败：URLError）** | {first[3]} |")
        self.assertTrue(any("降级占位" in i for i in notices_issues(broken_license)),
                        "降级占位必须报")
        dropped = self.text.replace(row + "\n", "")
        self.assertTrue(any("未列入" in i for i in notices_issues(dropped)),
                        "删掉组件必须报")
        drift = self.text.replace(f"| {BT}{first[0]}{BT} | {first[1]} |",
                                  f"| {BT}{first[0]}{BT} | 0.0.0 |")
        self.assertTrue(any("版本" in i for i in notices_issues(drift)),
                        "版本漂移必须报")
        stale = self.text.replace("sha256:", "sha256:0000000000000000", 1)
        self.assertTrue(any("摘要过期" in i for i in notices_issues(stale)),
                        "摘要过期必须报")
        no_gen = self.text.replace("gen_third_party_notices.py", "某脚本")
        self.assertTrue(any("生成器" in i or "缺要素" in i for i in notices_issues(no_gen)),
                        "删掉生成器标识必须报")
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_notices.md")


if __name__ == "__main__":
    unittest.main()
