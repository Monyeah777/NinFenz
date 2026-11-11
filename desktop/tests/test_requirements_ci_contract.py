#!/usr/bin/env python3
"""requirements-ci 契约判据：哈希完备、直钉镜像、可复现生成命令、ASCII（2026-11-11）。

为什么必须有：requirements-ci.txt 是 CI 工具链唯一版本真源，也是 --require-hashes 与审计输入。
它此前只有「精确钉版 + ASCII」两项机检，缺三处关键约束：①**每行 hash 完备**（缺 hash 的钉版会被
--require-hashes 拒绝，或在某些调用方退化成无哈希安装）；②**直钉与 pyproject ci extra 镜像一致**
（两处版本漂移会让 `pip install -e .[dev]` 与 `-r requirements-ci.txt` 装出不同环境）；
③**生成命令可复现**（原头部引用不存在的 direct-pins.in，照着跑必然失败）。

范围：只判 .github/requirements-ci.txt 与 pyproject.toml 的 ci extra。
同族判据：test_ci_supply_chain（精确钉版 / ASCII）、test_dependabot_contract（跟进面）。
"""
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQ = ROOT / ".github" / "requirements-ci.txt"
PYPROJECT = ROOT / "pyproject.toml"
PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?==([^\\;\s]+)\s*\\?$")
HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})\s*\\?$")
INCLUDE_PREFIXES = ("-r ", "-c ", "-e ", "--index-url", "--extra-index-url")


def parse(text: str):
    """→ (pins, includes)：pins[name] = {version, extras, hashes, count}。"""
    pins = {}
    includes = []
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(INCLUDE_PREFIXES):
            includes.append(line)
            continue
        m = HASH_RE.search(line)
        if m and cur is not None:
            cur["hashes"].append(m.group(1))
            continue
        m = PIN_RE.match(line)
        if m:
            name = m.group(1).lower()
            cur = pins.get(name)
            if cur is None:
                cur = {"version": m.group(3), "extras": m.group(2) or "",
                       "hashes": [], "count": 0}
                pins[name] = cur
            cur["count"] += 1
            cur["version"] = m.group(3)
    return pins, includes


def ci_extra_pins(pyproject_text: str) -> dict:
    """pyproject [project.optional-dependencies].ci → {name: version}。"""
    doc = tomllib.loads(pyproject_text)
    deps = (doc.get("project") or {}).get("optional-dependencies") or {}
    out = {}
    for dep in deps.get("ci") or []:
        m = PIN_RE.match(str(dep))
        if m:
            out[m.group(1).lower()] = m.group(3)
    return out


def file_issues(text: str, pyproject_text: str) -> list:
    """requirements-ci 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        issues.append("必须 ASCII-only（pip 按 locale 解析；非 ASCII 注释会 UnicodeDecodeError）")
    if not text.endswith("\n"):
        issues.append("文件必须以换行结尾")
    if "\r\n" in text:
        issues.append("不得使用 CRLF（pip/locale 与编码卫生判据都会假红）")
    header = text.splitlines()[0] if text else ""
    if "pip-compile" not in header:
        issues.append("首行必须是 pip-compile 生成标记（禁止手改）")
    head = "\n".join(text.splitlines()[:8])
    for needle, why in (("--generate-hashes", "生成命令必须带 --generate-hashes"),
                        ("--strip-extras", "生成命令必须带 --strip-extras"),
                        ("pyproject.toml", "生成命令的输入必须是仓库内的 pyproject.toml")):
        if needle not in head:
            issues.append(f"生成头缺要素：{why}")
    if "direct-pins.in" in head:
        issues.append("生成头不得引用不存在的外部输入文件（照抄跑不起来）")
    pins, includes = parse(text)
    if includes:
        issues.append(f"固定集必须自包含（不许 -r/-c/-e/index 行）：{includes[:2]}")
    if not pins:
        issues.append("解析不到任何钉版行")
    for name, info in sorted(pins.items()):
        if info["count"] > 1:
            issues.append(f"重复钉版：{name}（出现 {info['count']} 次）")
        if info["extras"]:
            issues.append(f"不得带 extras（--strip-extras）：{name}{info['extras']}")
        if not info["hashes"]:
            issues.append(f"钉版缺 hash（--require-hashes 会拒绝/退化）：{name}")
        elif len(set(info["hashes"])) != len(info["hashes"]):
            issues.append(f"同一钉版出现重复 hash：{name}")
    direct = ci_extra_pins(pyproject_text)
    if not direct:
        issues.append("pyproject [project.optional-dependencies].ci 解析不到直钉")
    for name, version in sorted(direct.items()):
        got = pins.get(name)
        if got is None:
            issues.append(f"缺直钉（pyproject ci extra 声明了但固定集没有）：{name}=={version}")
        elif got["version"] != version:
            issues.append(f"直钉版本漂移：{name} {got['version']} != pyproject {version}")
    return issues


class RequirementsCiContractTest(unittest.TestCase):
    def setUp(self):
        self.text = REQ.read_text(encoding="utf-8")
        self.pyproject = PYPROJECT.read_text(encoding="utf-8")

    def test_file_matches_contract(self):
        self.assertEqual([], file_issues(self.text, self.pyproject),
                         "requirements-ci.txt 不满足契约")

    def test_every_pin_has_hashes(self):
        pins, _ = parse(self.text)
        self.assertGreaterEqual(len(pins), 10, "固定集过小（解析异常？）")
        for name, info in pins.items():
            self.assertTrue(info["hashes"], f"{name} 缺 hash")

    def test_direct_pins_mirror_pyproject(self):
        pins, _ = parse(self.text)
        for name, version in ci_extra_pins(self.pyproject).items():
            self.assertIn(name, pins)
            self.assertEqual(version, pins[name]["version"])

    def test_contract_catches_broken_file(self):
        """变异自证（五类坏件都必须报）。

        覆盖：去 hash / 重复钉版 / 直钉版本漂移 / 加 -r 行 / 非 ASCII。
        """
        first = parse(self.text)[0]
        name = sorted(first)[0]
        no_hash = "".join(ln for ln in self.text.splitlines(keepends=True)
                          if not ln.strip().startswith("--hash="))
        self.assertTrue(any("hash" in i for i in file_issues(no_hash, self.pyproject)),
                        "去 hash 必须报")
        dup = self.text + f"{name}=={first[name]['version']}\n"
        self.assertTrue(any("重复" in i for i in file_issues(dup, self.pyproject)),
                        "重复钉版必须报")
        drifted = self.text.replace("pyyaml==6.0.3", "pyyaml==6.0.2")
        self.assertTrue(any("漂移" in i for i in file_issues(drifted, self.pyproject)),
                        "直钉版本漂移必须报")
        included = self.text + "-r other.txt\n"
        self.assertTrue(any("自包含" in i for i in file_issues(included, self.pyproject)),
                        "加 -r 行必须报")
        non_ascii = self.text + "# 中文注释\n"
        self.assertTrue(any("ASCII" in i for i in file_issues(non_ascii, self.pyproject)),
                        "非 ASCII 必须报")


if __name__ == "__main__":
    unittest.main()
