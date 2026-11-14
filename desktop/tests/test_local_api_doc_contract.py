#!/usr/bin/env python3
"""docs/ccos/local-api-v0.md 契约：本地 HTTP 面规范必须「三端点/判定语义/安全边界与实现一致」。

为什么必须有：这是「不装 Python 也能验」的底座——端点路径、判定语义（invalid 也 200）、安全边界
（只绑回环 / Origin / 8 MiB / 无路径）任何一处写错，前端与第三方都会按错契约写。本轮补现状与
鉴权边界澄清（MCP 面 --ingress-policy 不适用于 HTTP 面），并把三端点、契约 id、18 例判据、
MAX_BODY、LOOPBACK、CSP、页面资源承载处全部活绑定。

范围：只判本文与 http_api/endpoint_contract/web_pages 事实自洽（不改端点）。同族判据：
test_http_api.py（18 例）/ test_web_pages*.py / test_endpoint_contract*.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、三路由在实现且在文、契约 local.* 三条、18 例判据、MAX_BODY 8 MiB、
LOOPBACK 三值、CSP 同源、页面资源在 web_pages、判定语义「invalid 也 200」、ingress 边界区分、
现状对照 + 复现两命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import http_api, web_pages  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "local-api-v0.md"
CONTRACT = ROOT / "protocol" / "endpoint_contract.json"
TEST = ROOT / "desktop" / "tests" / "test_http_api.py"
NF = ROOT / "scripts" / "nf.py"
ROUTES = ("/api/health", "/api/verify", "/api/check")
SECTIONS = ("## 是什么", "## 启动", "## 端点", "## 工作台页", "## 安全边界",
            "## 判定语义", "## 判据（可证）", "## 现状对照", "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"本地 HTTP 面文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("本地 HTTP 面文档为空")
    return text


def contract_ids() -> list:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return [e.get("id") for e in data.get("endpoints") or []
            if str(e.get("id")) .startswith("local.")]


def http_cases() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def local_api_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 本地 HTTP 面 v0"):
        issues.append("缺标题「# 本地 HTTP 面 v0（local api）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for route in ROUTES:
        if route not in text:
            issues.append(f"正文缺端点：{route}")
    ids = contract_ids()
    if sorted(ids) != ["local.check", "local.health", "local.verify"]:
        issues.append(f"endpoint_contract 的 local.* 已变：{ids}")
    for i in ids:
        if i not in text and "local." not in text:
            issues.append(f"正文缺契约 id：{i}")
    api = (ROOT / "desktop" / "src" / "core" / "http_api.py").read_text(encoding="utf-8")
    for route in ROUTES:
        if '"' + route + '"' not in api and route not in api:
            issues.append(f"http_api 缺路由：{route}")
    if http_api.MAX_BODY != 8 * 1024 * 1024:
        issues.append(f"MAX_BODY 已变：{http_api.MAX_BODY}")
    if "8 MiB" not in text:
        issues.append("未写体量上限 8 MiB")
    if getattr(http_api, "LOOPBACK", ()) != ("127.0.0.1", "localhost", "::1"):
        issues.append("LOOPBACK 白名单已变")
    if "default-src 'none'" not in web_pages.CSP:
        issues.append("CSP 常量已变（不再 default-src none）")
    if "CSP" not in text or "default-src 'none'" not in text:
        issues.append("正文缺 CSP 口径（default-src 'none'）")
    if "web_pages.py" not in text:
        issues.append("未写页面资源承载处")
    page = web_pages.html().decode("utf-8")
    if "/assets/verify.js" not in page:
        issues.append("页面资源缺 verify.js")
    if "/assets/verify.css" not in page:
        issues.append("页面资源缺 verify.css")
    for marker in ("invalid", "200", "4xx", "5xx"):
        if marker not in text:
            issues.append(f"判定语义缺要素：{marker}")
    if "ingress-policy" not in text:
        issues.append("缺 MCP/HTTP 鉴权边界区分（--ingress-policy）")
    if "无鉴权" not in text:
        issues.append("缺「无鉴权」如实标注")
    n_cases = http_cases()
    if n_cases != 18:
        issues.append(f"test_http_api 例数已变（{n_cases}）")
    if str(n_cases) + " 项" not in text:
        issues.append(f"未写判据数（{n_cases} 项）")
    nf = NF.read_text(encoding="utf-8")
    if '"--http"' not in nf:
        issues.append("CLI 缺 --http")
    for cmd in ("python scripts/nf.py serve --http --port 0",
                "python -m pytest desktop/tests/test_http_api.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class LocalApiDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_local_api_matches_contract(self):
        self.assertEqual([], local_api_issues(self.text), "本地 HTTP 面文档不满足契约")

    def test_api_facts_live(self):
        self.assertEqual(8 * 1024 * 1024, http_api.MAX_BODY)
        self.assertEqual(("127.0.0.1", "localhost", "::1"), tuple(http_api.LOOPBACK))
        self.assertIn("default-src 'none'", web_pages.CSP)
        self.assertEqual(["local.check", "local.health", "local.verify"],
                         sorted(contract_ids()))
        self.assertEqual(18, http_cases())

    def test_contract_catches_mutations(self):
        """变异自证：去端点 / 改判定语义 / 去 CSP / 去 ingress 边界 / 例数漂移 / 缺命令。"""
        no_route = self.text.replace("/api/check", "/api/policy")
        self.assertTrue(any("/api/check" in i for i in local_api_issues(no_route)))
        no_sem = self.text.replace("200", "204")
        self.assertTrue(any("200" in i or "判定语义" in i
                            for i in local_api_issues(no_sem)))
        no_csp = self.text.replace("default-src 'none'", "default-src self")
        self.assertTrue(any("CSP" in i for i in local_api_issues(no_csp)))
        no_ing = self.text.replace("ingress-policy", "策略")
        self.assertTrue(any("ingress-policy" in i for i in local_api_issues(no_ing)))
        old_n = self.text.replace("18 项", "10 项")
        self.assertTrue(any("18 项" in i or "例数" in i
                            for i in local_api_issues(old_n)))
        no_cmd = self.text.replace("python scripts/nf.py serve --http --port 0", "起服务")
        self.assertTrue(any("serve --http" in i for i in local_api_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_local_api.md")


if __name__ == "__main__":
    unittest.main()
