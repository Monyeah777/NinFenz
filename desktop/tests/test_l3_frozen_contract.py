#!/usr/bin/env python3
"""docs/L3_FROZEN 契约：端壳退役记录必须「退役件不在树 + 保留件在场 + CI 清单现状 + 机检面」。

为什么必须有：本文件是端壳退役的**真相源**——它列了「已彻底移除、不再恢复」的 8 类路径与
「保留（L0–L2）」清单；若某退役件悄悄回来、或保留件被删、或 CI 清单与仓库不一致，本文件就会
从「真相源」变成「过期叙事」。本轮补最后复核位、退役/保留的机检面、CI 22 个 workflow 全量点名、
使用与复现口径，并把「不在树/在场」两侧都立成机检断言。

范围：只判本文与仓库树/CLI/CI 事实自洽（不改退役结论）。同族判据：
check39（端壳零回潮，verify.sh）/ test_doc_hygiene.py / test_doc_examples.py /
test_doc_reachability.py（指令与旗标可达）。
契约：最后复核位、Status 段、L0–L3 表 4 行、退役清单 8 类路径**确实不在树**、
保留件 5 项在场、声明⇄机检面（check39/doc_hygiene/LAYERS）、21 个命名 workflow 存在、
nf shell 入口与 docs/terminal.md 在场、复现三命令。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

DOC = ROOT / "docs" / "L3_FROZEN.md"
NF = ROOT / "scripts" / "nf.py"
VERIFY = ROOT / "verify.sh"
WORKFLOWS = ROOT / ".github" / "workflows"
RETIRED = ("android", "desktop/src/ui", "desktop/main.py", "desktop/packaging",
           "desktop/scripts/smoke_gui.py", "desktop/scripts/bench.py",
           "scripts/smoke_zone_g_market.py", "scripts/selftest_android.py",
           "scripts/sync_android.sh",
           ".github/workflows/build-desktop.yml", ".github/workflows/build-android.yml")
KEPT = ("desktop/src/core", "desktop/tests", "desktop/scripts/seed_from_repo.py",
        "scripts/e2e_desktop_headless.py", "scripts/reconcile_assets.sh",
        "docs/terminal.md", "docs/layers.md")
NAMED = ("ci-health", "ci-verify", "codeql", "coverage", "cross-lang", "cross-platform",
         "dependency-audit", "docker-nfal", "dotnet-build", "e2e-desktop",
         "external-links", "gitee-poll", "library-ingest", "lint",
         "linux-parity-refresh", "net-probes", "npm-package-check", "npm-publish",
         "release-gate", "rust-crate", "sast", "scorecard")
SECTIONS = ("## 分层定义", "## 本文件 = 退役清单索引", "## 声明 ⇄ 机检面",
            "## 使用与复现口径", "## 治理同步", "## 纪律")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"L3 记录不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("L3 记录为空")
    return text


def l3_issues(text: str) -> list:
    issues = []
    if not text.startswith("# L3 端壳层退役记录"):
        issues.append("缺标题「# L3 端壳层退役记录」")
    if "最后复核" not in text:
        issues.append("缺「最后复核」位")
    if "2026-09-09 永久退役" not in text:
        issues.append("缺「2026-09-09 永久退役」状态")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for row in ("L0 协议层", "L1 内容层", "L2 核心逻辑层", "L3 端壳层"):
        if row not in text:
            issues.append(f"分层表缺行：{row}")
    for rel in RETIRED:
        if (ROOT / rel).exists():
            issues.append(f"退役件回到树中：{rel}")
        base = rel.rsplit("/", 1)[-1]
        if base not in text:
            issues.append(f"退役清单缺项：{base}")
    for rel in KEPT:
        if not (ROOT / rel).exists():
            issues.append(f"保留件缺失：{rel}")
        base = rel.rsplit("/", 1)[-1]
        if base not in text:
            issues.append(f"保留清单缺项：{base}")
    verify = VERIFY.read_text(encoding="utf-8")
    if "check39" not in verify:
        issues.append("verify.sh 缺 check39（端壳零回潮判据）")
    if "check39" not in text:
        issues.append("正文缺 check39 口径")
    nf = NF.read_text(encoding="utf-8")
    if '"shell", aliases=["terminal"]' not in nf and 'add_parser("shell"' not in nf:
        issues.append("CLI 缺 shell 入口")
    if "nf shell" not in text:
        issues.append("缺「人机入口 = nf shell」口径")
    names = sorted(p.stem for p in WORKFLOWS.glob("*.yml"))
    if names != sorted(NAMED):
        issues.append(f"workflow 集合与命名清单不一致：{names}")
    if str(len(names)) + " 个 workflow" not in text:
        issues.append(f"未写现行 workflow 数（{len(names)} 个）")
    for name in NAMED:
        if (name + ".yml") not in text:
            issues.append(f"CI 现状缺 workflow：{name}.yml")
    for cmd in ("python scripts/nf.py explain check39",
                "python scripts/nf.py shell --help",
                "bash verify.sh --checks-only"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class L3FrozenContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_l3_matches_contract(self):
        self.assertEqual([], l3_issues(self.text), "L3 退役记录不满足契约")

    def test_retired_absent_and_kept_present(self):
        for rel in RETIRED:
            self.assertFalse((ROOT / rel).exists(), rel)
        for rel in KEPT:
            self.assertTrue((ROOT / rel).exists(), rel)
        self.assertEqual(22, len(list(WORKFLOWS.glob("*.yml"))))

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 退役缺项 / 保留件缺失 / 缺 check39 / 缺 workflow / 缺命令。"""
        no_date = self.text.replace("最后复核", "说明")
        self.assertTrue(any("最后复核" in i for i in l3_issues(no_date)))
        no_item = self.text.replace("smoke_zone_g_market.py", "z.py")
        self.assertTrue(any("退役清单" in i for i in l3_issues(no_item)))
        no_kept = self.text.replace("seed_from_repo.py", "种子器")
        self.assertTrue(any("seed_from_repo" in i for i in l3_issues(no_kept)))
        no_check = self.text.replace("check39", "某 check")
        self.assertTrue(any("check39" in i for i in l3_issues(no_check)))
        no_wf = self.text.replace("docker-nfal.yml", "docker.yml")
        self.assertTrue(any("docker-nfal" in i for i in l3_issues(no_wf)))
        no_cmd = self.text.replace("python scripts/nf.py shell --help", "看 shell")
        self.assertTrue(any("shell --help" in i for i in l3_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_l3.md")


if __name__ == "__main__":
    unittest.main()
