#!/usr/bin/env python3
"""clients/go/README.md 契约：Go 侧第二实现文档必须「七调向量 55 / 7 子命令 / 前提写清」。

为什么必须有：这份 README 声称「七调判定面与真源同口径、共 55 例向量」，但此前既无判据、
也没写「跑 go test 需要 Go 工具链」——在不装 Go 的机器上，读者只能要么盲信、要么以为仓库坏了。
本轮补「§现状对照」：向量数逐文件与 results/ccos 对账、CLI 子命令 7 条逐条核对、
工具链前提显式化（本机缺 Go，不声称已跑），并新增本判据把这三件事钉住。

范围：只判本文与向量 JSON / main.go / go.mod 事实自洽（不编译 Go）。
同族判据：test_doc_hygiene.py / test_doc_examples.py / CCOS ABI 相关 Python 侧判据。
契约：复核位、七调向量逐值（55 与分项）、7 子命令逐名、go.mod 版本与正文一致、
「本轮未跑」诚实标注、退出码 5 值、现状对照段在场。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "clients" / "go" / "README.md"
VECTORS = ROOT / "results" / "ccos"
MAIN = ROOT / "clients" / "go" / "cmd" / "nfverify" / "main.go"
GOMOD = ROOT / "clients" / "go" / "go.mod"
FILES = {
    "evidence": "evidence_verdict_vectors.json",
    "check": "check_verdict_vectors.json",
    "label": "label_verdict_vectors.json",
    "attest": "attest_envelope_vectors.json",
    "replay": "replay_trace_vectors.json",
    "diff": "diff_delta_vectors.json",
    "resolve": "resolve_contract_vectors.json",
}
SUBS = ("verify", "check", "label", "attest", "replay", "diff", "resolve")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Go 客户端 README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("Go 客户端 README 为空")
    return text


def counts() -> dict:
    out = {}
    for key, name in FILES.items():
        data = json.loads((VECTORS / name).read_text(encoding="utf-8"))
        out[key] = len(data.get("vectors") or [])
    return out


def go_issues(text: str) -> list:
    issues = []
    if not text.startswith("# CCOS Go 客户端"):
        issues.append("缺标题「# CCOS Go 客户端（nfverify）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺「复核（2026-11-14）」说明")
    c = counts()
    total = sum(c.values())
    if total != 55:
        issues.append(f"向量总数已变（{total}）")
    if "**55**" not in text:
        issues.append("现状未写向量总数 55")
    for label in ("**28**", "**6**", "**7**", "**3**", "**1**", "**4**"):
        if label not in text:
            issues.append(f"现状缺向量分项：{label}")
    main = MAIN.read_text(encoding="utf-8")
    for sub in SUBS:
        if f'case "{sub}"' not in main:
            issues.append(f"main.go 缺子命令分派：{sub}")
        if sub not in text:
            issues.append(f"正文缺子命令：{sub}")
    if "**7**" not in text:
        issues.append("现状未写 7 个子命令")
    mod = GOMOD.read_text(encoding="utf-8")
    m = re.search(r"(?m)^go (\d+\.\d+)$", mod)
    if not m:
        issues.append("go.mod 缺 go 版本")
    elif f"Go ≥ {m.group(1)}" not in text:
        issues.append(f"正文 Go 版本与 go.mod 不一致（应为 {m.group(1)}）")
    if "本轮未跑" not in text:
        issues.append("缺「go test 本轮未跑」诚实标注")
    for code in ("0 ok", "1 invalid", "2 revoked", "3 expired", "4 用法错"):
        if code not in text:
            issues.append(f"退出码口径缺：{code}")
    if "## 现状对照" not in text:
        issues.append("缺「§现状对照」段")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class GoClientDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_go_readme_matches_contract(self):
        self.assertEqual([], go_issues(self.text), "Go 客户端 README 不满足契约")

    def test_vectors_live(self):
        c = counts()
        self.assertEqual(55, sum(c.values()))
        self.assertEqual(28, c["evidence"])
        self.assertEqual(6, c["check"])
        self.assertEqual(7, c["label"])
        self.assertEqual(3, c["attest"])
        self.assertEqual(1, c["replay"])

    def test_contract_catches_mutations(self):
        """变异自证：总数回退 / 版本漂移 / 缺未跑标注 / 缺退出码。"""
        old = self.text.replace("**55**", "**50**")
        self.assertTrue(any("55" in i for i in go_issues(old)))
        mod = GOMOD.read_text(encoding="utf-8")
        m = re.search(r"(?m)^go (\d+\.\d+)$", mod)
        bad_ver = self.text.replace(f"Go ≥ {m.group(1)}", "Go ≥ 1.11")
        self.assertTrue(any("go.mod" in i for i in go_issues(bad_ver)))
        no_run = self.text.replace("本轮未跑", "已跑通")
        self.assertTrue(any("本轮未跑" in i for i in go_issues(no_run)))
        no_code = self.text.replace("3 expired", "3 expire")
        self.assertTrue(any("退出码" in i for i in go_issues(no_code)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_go_readme.md")


if __name__ == "__main__":
    unittest.main()
