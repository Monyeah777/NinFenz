#!/usr/bin/env python3
"""site/DEPLOY-search-submit.md 契约：通道清单 / IndexNow 配置 / 判据项数必须可核。

为什么必须有：这是「让站点被搜到」的唯一操作手册，涉及**外部控制台**与**网络请求**——最容易被写成
「已提交/已收录」而无人核对。本轮实测发现 §1 写着「33+ 项离线判据 / 28 项联网判据」，
而离线实为 **42 项**。
本轮修数字、补「§11 现状对照」「§12 复现与引用口径」，并加判据：
通道 7 类、`indexnow.json` 的 4 条 URL 与 4 家引擎、密钥文件在场、
`.assetsignore` 排除 DEPLOY 文档、离线 42 项、以及**不声称「已收录」**（那是引擎侧事实）。

范围：只判本文与 site/tools 配置/`.assetsignore` 事实自洽（不发网络请求）。
同族判据：test_deploy_cloudflare_doc_contract.py（同族站点手册）/ site-check --offline 实跑。
契约：复核位、7 类通道、urlList 4 条逐条、enginesCovered 4 家、密钥文件名、离线 42 项、
`.assetsignore` 排除两篇 DEPLOY、联网命令标注「需网络」、不声称已收录、复现三命令。
"""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "site" / "DEPLOY-search-submit.md"
IDX = ROOT / "site" / "tools" / "indexnow.json"
ASSETS_IGNORE = ROOT / "site" / ".assetsignore"
CHANNELS = ("IndexNow", "Google Search Console", "Bing Webmaster Tools",
            "Yandex Webmaster", "百度搜索资源平台", "AI 生成式引擎")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"提交手册不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("提交手册为空")
    return text


def offline_check() -> subprocess.CompletedProcess:
    return subprocess.run(["node", "site/tools/site-check.mjs", "--offline"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, check=False)


def doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 搜索引擎提交"):
        issues.append("缺标题「# 搜索引擎提交：站点地图 · IndexNow · 各站控制台」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    cfg = json.loads(IDX.read_text(encoding='utf-8'))
    if cfg.get("host") != "ninfenz.dev":
        issues.append("indexnow.json host 已变")
    urls = cfg.get("urlList") or []
    if len(urls) != 4:
        issues.append(f"urlList 条数已变（{len(urls)}）")
    for u in urls:
        if u not in text:
            issues.append(f"正文缺 URL：{u}")
    if len(cfg.get("enginesCovered") or []) != 4:
        issues.append("enginesCovered 已变（应为 4 家）")
    keyfile = ROOT / "site" / (cfg.get("key", "") + ".txt")
    if not keyfile.is_file():
        issues.append("IndexNow 密钥文件不在站点根")
    if cfg.get("key", "") not in text:
        issues.append("正文未写密钥")
    for ch in CHANNELS:
        if ch not in text:
            issues.append(f"缺提交通道：{ch}")
    if "42 项" not in text:
        issues.append("未写离线 42 项判据")
    ignored = ASSETS_IGNORE.read_text(encoding='utf-8')
    for name in ("DEPLOY-search-submit.md", "DEPLOY-cloudflare-workers.md"):
        if name not in ignored:
            issues.append(f".assetsignore 未排除：{name}")
    if "需网络" not in text and "需联网" not in text:
        issues.append("未标注哪些命令需要网络")
    if "已收录" not in text or "不声称" not in text:
        issues.append("缺「不声称已收录（引擎侧事实）」的口径")
    for cmd in ("node site/tools/site-check.mjs --offline",
                "node site/tools/indexnow.mjs --dry-run"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class SearchSubmitDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_doc_matches_contract(self):
        self.assertEqual([], doc_issues(self.text), "提交手册不满足契约")

    def test_offline_check_reports_42(self):
        proc = offline_check()
        self.assertEqual(0, proc.returncode, proc.stdout[-500:])
        self.assertIn("42 项", proc.stdout)

    def test_contract_catches_mutations(self):
        """变异自证：缺通道 / 缺 URL / 缺 42 项 / 缺「不声称已收录」。"""
        no_ch = self.text.replace("Yandex Webmaster", "Yandex")
        self.assertTrue(any("Yandex" in i for i in doc_issues(no_ch)))
        no_url = self.text.replace("https://ninfenz.dev/en/use/", "https://ninfenz.dev/other/")
        self.assertTrue(any("URL" in i for i in doc_issues(no_url)))
        no_n = self.text.replace("42 项", "几十项")
        self.assertTrue(any("42 项" in i for i in doc_issues(no_n)))
        no_claim = self.text.replace("不声称", "声称")
        self.assertTrue(any("已收录" in i for i in doc_issues(no_claim)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_search_submit.md")


if __name__ == "__main__":
    unittest.main()
