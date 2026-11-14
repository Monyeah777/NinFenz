#!/usr/bin/env python3
"""docs/endpoint.md 契约：服务端点契约文档必须「端点计数/conventions/幂等例外/SSE 与契约实读一致」。

为什么必须有：这份文档是「契约存在 ≠ 服务存在」的边界声明——端点数量、幂等例外、
SSE 声明、派生面标注，任何一处漂移都会让读者把形状声明误读成已实装服务。
本轮补四组现状数字：**11 端点**（8 远端 proposed +
3 local.* 已实装）、**6 conventions**、
**1 条幂等例外**（bench.evaluate / non-idempotent / required）、**1 个 SSE**（assemble.plan），
并把它们与协议、CLI、派生面全部活绑定。

范围：只判本文与 endpoint_contract / nf endpoint / interop_export 事实自洽（不改协议）。
同族判据：test_governance_faces.py（契约面）/ test_local_api_doc_contract.py /
test_interop*.py / test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、11 端点与 CLI 一致、status proposed、6 conventions、
1 例外（key=required）、1 SSE、x-nf-idempotency 在派生面、现状对照 + 复现三命令、
「契约存在 ≠ 服务存在」边界。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "endpoint.md"
DATA = ROOT / "protocol" / "endpoint_contract.json"
NF = ROOT / "scripts" / "nf.py"
EXPORT = ROOT / "desktop" / "src" / "core" / "interop_export.py"
SECTIONS = ("## 是什么", "## 怎么用", "## 判据（可证", "## 幂等声明",
            "## 现状对照", "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"端点契约文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("端点契约文档为空")
    return text


def contract() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def endpoint_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 服务端点契约（endpoint）"):
        issues.append("缺标题「# 服务端点契约（endpoint）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    doc = contract()
    eps = doc.get("endpoints") or []
    if len(eps) != 11:
        issues.append(f"端点数已变（{len(eps)}）")
    if "11 个端点" not in text:
        issues.append("未写 11 个端点")
    if doc.get("status") != "proposed":
        issues.append(f"顶层 status 已变：{doc.get('status')}")
    if "proposed" not in text:
        issues.append("未写 status proposed")
    local = [e for e in eps if str(e.get("id")).startswith("local.")]
    if len(local) != 3:
        issues.append(f"local.* 端点数已变（{len(local)}）")
    if "local.*" not in text:
        issues.append("未点名 local.* 三端点")
    conv = list(doc.get("conventions") or {})
    if len(conv) != 6:
        issues.append(f"conventions 数已变（{len(conv)}）")
    if "6 条" not in text:
        issues.append("未写 6 条 conventions")
    for key in ("idempotency", "deprecation", "streaming"):
        if key not in conv or key not in text:
            issues.append(f"conventions 缺要素：{key}")
    exc = doc.get("idempotency_exceptions") or []
    if len(exc) != 1:
        issues.append(f"幂等例外数已变（{len(exc)}）")
    one = exc[0] if exc else {}
    if one.get("id") != "bench.evaluate" or one.get("mode") != "non-idempotent" \
            or one.get("key") != "required":
        issues.append(f"幂等例外字段已变：{one}")
    if "bench.evaluate" not in text or "required" not in text:
        issues.append("正文缺 bench.evaluate / required")
    sse = [e for e in eps if e.get("streaming") is True]
    if len(sse) != 1 or sse[0].get("id") != "assemble.plan":
        issues.append(f"SSE 端点已变：{[e.get('id') for e in sse]}")
    if "assemble.plan" not in text:
        issues.append("正文缺 SSE 端点 assemble.plan")
    nf = NF.read_text(encoding="utf-8")
    for flag in ("endpoint", "--json"):
        if flag not in nf:
            issues.append(f"CLI 缺要素：{flag}")
    if "x-nf-idempotency" not in EXPORT.read_text(encoding="utf-8"):
        issues.append("派生面缺 x-nf-idempotency")
    if "x-nf-idempotency" not in text:
        issues.append("正文缺 x-nf-idempotency")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py endpoint",
                "python scripts/nf.py endpoint --json",
                "python -m pytest desktop/tests/test_governance_faces.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "契约存在 ≠ 服务存在" not in text:
        issues.append("缺「契约存在 ≠ 服务存在」边界")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class EndpointDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_endpoint_matches_contract(self):
        self.assertEqual([], endpoint_issues(self.text), "端点契约文档不满足契约")

    def test_contract_live(self):
        doc = contract()
        self.assertEqual(11, len(doc["endpoints"]))
        self.assertEqual("proposed", doc["status"])
        self.assertEqual(6, len(doc["conventions"]))
        self.assertEqual(1, len(doc["idempotency_exceptions"]))
        self.assertEqual(1, sum(1 for e in doc["endpoints"]
                                if e.get("streaming") is True))

    def test_contract_catches_mutations(self):
        """变异自证：端点计数回退 / 缺幂等例外 / 缺 SSE / 缺 x-nf / 缺命令。"""
        old_n = self.text.replace("11 个端点", "10 个端点")
        self.assertTrue(any("11 个端点" in i for i in endpoint_issues(old_n)))
        no_exc = self.text.replace("bench.evaluate", "bench")
        self.assertTrue(any("bench.evaluate" in i for i in endpoint_issues(no_exc)))
        no_sse = self.text.replace("assemble.plan", "assemble")
        self.assertTrue(any("assemble.plan" in i for i in endpoint_issues(no_sse)))
        no_x = self.text.replace("x-nf-idempotency", "idempotency")
        self.assertTrue(any("x-nf-idempotency" in i for i in endpoint_issues(no_x)))
        no_cmd = self.text.replace("python scripts/nf.py endpoint --json", "看 JSON")
        self.assertTrue(any("endpoint --json" in i for i in endpoint_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_endpoint.md")


if __name__ == "__main__":
    unittest.main()
