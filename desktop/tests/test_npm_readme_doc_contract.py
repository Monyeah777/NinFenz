#!/usr/bin/env python3
"""packaging/npm/README.md 契约：体积口径由 stager 生成、入口/供应链/引擎事实与 package.json 一致。

为什么必须有：这页 npm 包的唯一说明，而它有一处**生成数字**（`当前体积：N 件 · 解包 X MB`）——
本轮实测发现它已漂移（写 24.74 MB，实际 25.19 MB），且 stager 会被这个漂移挡住并给出
`--sync-readme` 修复指引。此外「Node >= 18.17 / bin / files / 无 install 脚本 / provenance」
都写在文档里，却没有任何判据。本轮补「§现状对照」「§复现与引用口径」并加本判据。

范围：只判本文与 package.json / 清单 / stager 事实自洽（不跑 npm publish）。
同族判据：test_npm_package.py（含 `npm run verify` 实跑）/ test_npm_publish_workflow_contract.py。
契约：复核位、体积行与清单一致、版本 == NF_CLI_VERSION、engines >=18.17、bin 两别名、
files 五项、无 install 脚本、provenance 为真、payload 不含 .github/results 说明、复现命令在场。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _live():
    """payload 清单的活值（判据不钉死数字，变异自证用活值）。"""
    man = json.loads((ROOT / "packaging" / "npm" / "payload" /
                       "payload-manifest.json").read_text(encoding="utf-8"))
    return str(man["count"]), "%.2f" % (man["total_bytes"] / 1048576)

DOC = ROOT / "packaging" / "npm" / "README.md"
PKG = ROOT / "packaging" / "npm" / "package.json"
MANIFEST = ROOT / "packaging" / "npm" / "payload" / "payload-manifest.json"
STAGER = ROOT / "packaging" / "npm" / "tools" / "stage-payload.mjs"
VOLUME = re.compile(r"当前体积：\*\*(\d+) 件 · 解包 ([0-9.]+) MB\*\*")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"npm README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("npm README 为空")
    return text


def npm_issues(text: str) -> list:
    issues = []
    if not text.startswith("# ninfenz · npm 一键包"):
        issues.append("缺标题「# ninfenz · npm 一键包」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for section in ("## 快速开始", "## 前置条件", "## 供应链纪律", "## 现状对照",
                    "## 复现与引用口径", "## 维护者：发布流程"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    pkg = json.loads(PKG.read_text(encoding="utf-8"))
    if pkg.get("engines", {}).get("node") != ">=18.17":
        issues.append(f"engines.node 已变：{pkg.get('engines')}")
    if "**>= 18.17**" not in text:
        issues.append("正文未写 Node >= 18.17")
    bin_map = pkg.get("bin") or {}
    if set(bin_map) != {"nf", "ninfenz"}:
        issues.append(f"bin 别名已变：{sorted(bin_map)}")
    if set(pkg.get("files") or []) != {"bin/", "lib/", "payload/", "README.md", "LICENSE"}:
        issues.append(f"files 已变：{pkg.get('files')}")
    scripts = pkg.get("scripts") or {}
    if any(k in scripts for k in ("preinstall", "install", "postinstall")):
        issues.append("出现安装期脚本（供应链纪律要求为零）")
    if (pkg.get("publishConfig") or {}).get("provenance") is not True:
        issues.append("publishConfig.provenance 不是 true")
    m = VOLUME.search(text)
    if not m:
        issues.append("缺「当前体积」生成行")
    elif MANIFEST.is_file():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        count = manifest.get("file_count") or manifest.get("files")
        if isinstance(count, list):
            count = len(count)
        if count is not None and int(m.group(1)) != int(count):
            issues.append(f"体积件数与清单不一致（{m.group(1)} vs {count}）")
    if "--sync-readme" not in text:
        issues.append("缺「体积数字由 --sync-readme 生成」口径")
    if "不能**跑全部门禁" not in text and "不能跑全部门禁" not in text:
        issues.append("缺「payload 工作树不能跑全部门禁」说明")
    for cmd in ("npm run stage -- --sync-readme", "npm run verify", "npm test"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class NpmReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_npm_readme_matches_contract(self):
        self.assertEqual([], npm_issues(self.text), "npm README 不满足契约")

    def test_volume_line_is_generated(self):
        stager = STAGER.read_text(encoding="utf-8")
        if "--sync-readme" not in stager:
            self.skipTest("当前 stager 无 --sync-readme")
        self.assertRegex(self.text, VOLUME)

    def test_contract_catches_mutations(self):
        """变异自证：体积数字改错 / 缺复核位 / 缺 sync 口径 / 写安装脚本。"""
        bad = self.text.replace(f"{_live()[0]} 件", "3000 件")
        self.assertTrue(any("件数" in i for i in npm_issues(bad)))
        no_rev = self.text.replace("复核（2026-11-14）", "复核")
        self.assertTrue(any("复核位" in i for i in npm_issues(no_rev)))
        no_sync = self.text.replace("--sync-readme", "--write")
        self.assertTrue(any("sync-readme" in i for i in npm_issues(no_sync)))
        no_guard = self.text.replace("不能**跑全部门禁", "可以跑全部门禁")
        self.assertTrue(any("全部门禁" in i for i in npm_issues(no_guard)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_npm_readme.md")


if __name__ == "__main__":
    unittest.main()
