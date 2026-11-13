#!/usr/bin/env python3
"""site/README.md 契约：站点总览的「页数 / 机器面 / 工具 / 判据项数 / npm 口径」必须可核。

为什么必须有：这是站点总览入口，它同时是 **npm 体积口径的一个投影面**——历史上这里手抄数字，
漂移过（写 24.74 MB，payload 清单 25.21 MB），只能靠 `sync-numbers --write` 收。本轮：
① 用 `sync-numbers --write` 把该口径同步到 5 个站点面 + 根 llms-full.txt；② 补「§现状对照」
「§复现与引用口径」；③ 加判据：页数 / 6 个机器面 / 5+1 工具 / 42 项离线 / 16 项 worker /
**npm 口径与 payload 清单一致（不钉具体数字，判据现场比对）** / 人工勿手抄的口径。

范围：只判本页与 site/ 实盘、payload 清单一致（不改站点内容）。
同族判据：test_npm_readme_doc_contract.py / test_deploy_cloudflare_doc_contract.py /
test_search_submit_doc_contract.py（站点三手册）。
契约：复核位、4 页 + 机器面 6 个 + 工具 5+1、42 项离线、16 项 worker、
**npm 件数/体积与 payload 清单相等**、复现四命令、发布前必跑口径。
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "site" / "README.md"
SITE = ROOT / "site"
MANIFEST = ROOT / "packaging" / "npm" / "payload" / "payload-manifest.json"
PAGES = ("index.html", "en/index.html", "use/index.html", "en/use/index.html")
MACHINE = ("llms.txt", "llms-full.txt", "nf.txt", "agent.txt", "facts.json", "run.sh")
TOOLS = ("set-origin.mjs", "sync-numbers.mjs", "site-check.mjs", "worker-check.mjs",
         "indexnow.mjs", "make-demo-gif.py")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"site README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("site README 为空")
    return text


def npm_volume_in_doc(text: str):
    """取本页写的 npm 件数/体积（只认含 ninfenz 的行，与 sync-numbers 同口径）。"""
    counts, sizes = set(), set()
    for line in text.splitlines():
        if "ninfenz" not in line:
            continue
        c = re.search(r"(\d{3,})\s*(?:文件|files)", line)
        if c:
            counts.add(c.group(1))
        s = re.search(r"(\d+\.\d+)\s*MB", line)
        if s:
            sizes.add(s.group(1))
    return counts, sizes


def doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# site/ · 静态站"):
        issues.append("缺标题「# site/ · 静态站（NinFenz 官网）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for page in PAGES:
        if not (SITE / page).is_file():
            issues.append(f"页面不在盘：{page}")
    for face in MACHINE:
        if not (SITE / face).is_file():
            issues.append(f"机器面不在盘：{face}")
        if face not in text:
            issues.append(f"正文未列机器面：{face}")
    for tool in TOOLS:
        if not (SITE / 'tools' / tool).is_file():
            issues.append(f"工具不在盘：{tool}")
    for section in ("## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "42 项" not in text:
        issues.append("未写离线 42 项判据")
    if "16 项" not in text:
        issues.append("未写 worker 16 项判据")
    if "人工勿手抄" not in text and "发布前必须跑" not in text:
        issues.append("缺「数字不许手抄/发布前必跑」口径")
    for cmd in ("node site/tools/sync-numbers.mjs",
                "node site/tools/site-check.mjs --offline"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding='utf-8'))
        want_count = str(man["count"])
        want_mb = "%.2f" % (man["total_bytes"] / 1048576)
        counts, sizes = npm_volume_in_doc(text)
        if counts and counts != {want_count}:
            issues.append(f"npm 件数与本页不一致：{sorted(counts)} vs 清单 {want_count}")
        if sizes and sizes != {want_mb}:
            issues.append(f"npm 体积与本页不一致：{sorted(sizes)} vs 清单 {want_mb}")
    else:
        issues.append("payload 清单不在场（无法核对 npm 口径）")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class SiteReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], doc_issues(self.text), "site README 不满足契约")

    def test_sync_numbers_passes(self):
        proc = subprocess.run(["node", "site/tools/sync-numbers.mjs"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, proc.stdout[-500:] + proc.stderr[-500:])

    def test_offline_check_passes(self):
        proc = subprocess.run(["node", "site/tools/site-check.mjs", "--offline"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, proc.stdout[-500:])
        self.assertIn("42 项", proc.stdout)

    def test_contract_catches_mutations(self):
        """变异自证：改坏 npm 体积 / 缺机器面 / 缺判据项数 / 缺手抄口径。"""
        bad = self.text.replace("25.21 MB", "24.74 MB")
        self.assertTrue(any("npm 体积" in i for i in doc_issues(bad)))
        no_machine = self.text.replace("facts.json", "数据")
        self.assertTrue(any("facts.json" in i or "机器面" in i for i in doc_issues(no_machine)))
        no_n = self.text.replace("42 项", "若干项")
        self.assertTrue(any("42 项" in i for i in doc_issues(no_n)))
        no_rule = self.text.replace("人工勿手抄", "随便抄").replace("发布前必须跑", "有空再跑")
        self.assertTrue(any("手抄" in i or "必跑" in i for i in doc_issues(no_rule)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_site_readme.md")


if __name__ == "__main__":
    unittest.main()
