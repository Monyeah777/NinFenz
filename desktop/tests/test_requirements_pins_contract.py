#!/usr/bin/env python3
"""requirements-pins 契约判据：hash 完备、生成可复现、跨文件版本一致（2026-11-11）。

为什么必须有：这三份固定集由各自 workflow 用 --require-hashes 安装，且 cross-platform 会在同一
环境里同时装三份——一旦某份被手工编辑、缺 hash、或两份对同一包钉了不同版本，就会出现
「本机能装、云端解析冲突」或「哈希缺失被拒」。它们此前只有 ci 一份有判据（本轮补上三份）。

范围：只判 .github/requirements-{lint,sast,audit}.txt 与 pyproject.toml 对应 extras。
同族判据：test_requirements_ci_contract（ci 单独一份）、test_ci_supply_chain。
"""
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQ_DIR = ROOT / ".github"
PYPROJECT = ROOT / "pyproject.toml"
#: 文件 → (pyproject extra 名, 生成命令必须含的额外 flag)
FILES = {
    "lint": ("lint", ()),
    "sast": ("sast", ()),
    "audit": ("audit", ("--allow-unsafe",)),
}
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


def extra_pins(pyproject_text: str, extra: str) -> dict:
    doc = tomllib.loads(pyproject_text)
    deps = (doc.get("project") or {}).get("optional-dependencies") or {}
    out = {}
    for dep in deps.get(extra) or []:
        m = PIN_RE.match(str(dep))
        if m:
            out[m.group(1).lower()] = m.group(3)
    return out


def file_issues(name: str, text: str, pyproject_text: str) -> list:
    """单份固定集契约问题列表（纯函数，便于变异自证）。"""
    extra, extra_flags = FILES[name]
    issues = []
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        issues.append(f"{name}: 必须 ASCII-only（pip 按 locale 解析）")
    if not text.endswith("\n"):
        issues.append(f"{name}: 文件必须以换行结尾")
    if "\r\n" in text:
        issues.append(f"{name}: 不得使用 CRLF")
    head = "\n".join(text.splitlines()[:8])
    if "pip-compile" not in (text.splitlines()[0] if text else ""):
        issues.append(f"{name}: 首行必须是 pip-compile 生成标记")
    for needle, why in (("--generate-hashes", "缺 --generate-hashes"),
                        ("--strip-extras", "缺 --strip-extras"),
                        ("pyproject.toml", "生成输入必须是仓库内 pyproject.toml"),
                        (f"--extra {extra}", f"生成命令必须 --extra {extra}")):
        if needle not in head:
            issues.append(f"{name}: 生成头缺要素：{why}")
    for flag in extra_flags:
        if flag not in head:
            issues.append(f"{name}: 生成头必须带 {flag}")
    if "direct-pins.in" in head:
        issues.append(f"{name}: 生成头不得引用不存在的外部输入文件")
    pins, includes = parse(text)
    if includes:
        issues.append(f"{name}: 固定集必须自包含（禁 -r/-c/-e/index）")
    if not pins:
        issues.append(f"{name}: 解析不到任何钉版行")
    for pname, info in sorted(pins.items()):
        if info["count"] > 1:
            issues.append(f"{name}: 重复钉版 {pname}")
        if info["extras"]:
            issues.append(f"{name}: 不得带 extras（--strip-extras）：{pname}{info['extras']}")
        if not info["hashes"]:
            issues.append(f"{name}: 钉版缺 hash：{pname}")
        elif len(set(info["hashes"])) != len(info["hashes"]):
            issues.append(f"{name}: 同一钉版重复 hash：{pname}")
    for pname, version in sorted(extra_pins(pyproject_text, extra).items()):
        got = pins.get(pname)
        if got is None:
            issues.append(f"{name}: 缺直钉（pyproject {extra} 有、固定集没有）：{pname}=={version}")
        elif got["version"] != version:
            issues.append(f"{name}: 直钉与 pyproject 漂移：{pname} {got['version']} != {version}")
    return issues


def cross_file_issues(pins_by_file: dict) -> list:
    """同一包在多份固定集里版本必须一致（cross-platform 会同时装三份）。"""
    issues = []
    seen = {}
    for name, pins in sorted(pins_by_file.items()):
        for pname, info in pins.items():
            prev = seen.get(pname)
            if prev and prev[1] != info["version"]:
                issues.append(f"跨文件版本冲突：{pname} {prev[0]}={prev[1]} "
                              f"vs {name}={info['version']}")
            elif prev is None:
                seen[pname] = (name, info["version"])
    return issues


class RequirementsPinsContractTest(unittest.TestCase):
    def setUp(self):
        self.texts = {n: (REQ_DIR / f"requirements-{n}.txt").read_text(encoding="utf-8")
                      for n in FILES}
        # ci 有独立判据；这里只把它拉进「跨文件版本一致」对账（cross-platform 会同时装全部）。
        self.ci_pins = parse((REQ_DIR / "requirements-ci.txt").read_text(encoding="utf-8"))[0]
        self.pyproject = PYPROJECT.read_text(encoding="utf-8")

    def test_files_match_contract(self):
        issues = []
        for name, text in self.texts.items():
            issues.extend(file_issues(name, text, self.pyproject))
        self.assertEqual([], issues, "固定集不满足契约")

    def test_cross_file_versions_agree(self):
        pins = {n: parse(t)[0] for n, t in self.texts.items()}
        pins["ci"] = self.ci_pins
        self.assertEqual([], cross_file_issues(pins), "跨文件钉版冲突")

    def test_contract_catches_broken_files(self):
        """变异自证（六类坏件都必须报）。

        覆盖：去 hash / 重复钉版 / 引用外部输入 / 非 ASCII / audit 缺 --allow-unsafe / 跨文件冲突。
        """
        first = parse(self.texts["sast"])[0]
        name = sorted(first)[0]
        no_hash = "".join(ln for ln in self.texts["sast"].splitlines(keepends=True)
                          if not ln.strip().startswith("--hash="))
        self.assertTrue(any("hash" in i for i in file_issues("sast", no_hash, self.pyproject)),
                        "去 hash 必须报")
        dup = self.texts["sast"] + f"{name}=={first[name]['version']}\n"
        self.assertTrue(any("重复" in i for i in file_issues("sast", dup, self.pyproject)),
                        "重复钉版必须报")
        placeholder = self.texts["lint"].replace(
            "--output-file=.github/requirements-lint.txt pyproject.toml",
            "--output-file=.github/requirements-lint.txt direct-pins.in")
        self.assertTrue(any("外部输入" in i
                            for i in file_issues("lint", placeholder, self.pyproject)),
                        "引用外部输入必须报")
        non_ascii = self.texts["lint"] + "# 中文\n"
        self.assertTrue(any("ASCII" in i
                            for i in file_issues("lint", non_ascii, self.pyproject)),
                        "非 ASCII 必须报")
        no_unsafe = self.texts["audit"].replace("--allow-unsafe", "")
        self.assertTrue(any("allow-unsafe" in i
                            for i in file_issues("audit", no_unsafe, self.pyproject)),
                        "audit 缺 --allow-unsafe 必须报")
        pins = {n: parse(t)[0] for n, t in self.texts.items()}
        pins["ci"] = parse(self.ci_pins and
                           (REQ_DIR / "requirements-ci.txt").read_text(encoding="utf-8"))[0]
        # ci 与 sast 都钉 pyyaml：把 sast 侧改一个不同版本即冲突。
        pins["sast"]["pyyaml"] = dict(pins["sast"].get("pyyaml") or
                                      {"version": "0.0.0", "extras": "", "hashes": [], "count": 1})
        pins["sast"]["pyyaml"]["version"] = "0.0.0"
        self.assertTrue(cross_file_issues(pins), "跨文件冲突必须报")


if __name__ == "__main__":
    unittest.main()
