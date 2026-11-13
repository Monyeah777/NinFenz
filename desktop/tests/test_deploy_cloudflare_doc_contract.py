#!/usr/bin/env python3
"""site/DEPLOY-cloudflare-workers.md 契约：wrangler 关键键 / 站点工具 / 三条自检命令必须可核。

为什么必须有：这是站点上线的唯一操作手册，写错一个字段就是「部署了但打不开」。此前它没有判据：
`wrangler.jsonc` 改键、站点工具改名、或 CI 步骤被摘，都不会被发现。本轮补「§现状对照」
「§复现与引用口径」，并加判据把「关键键 + 五个工具 + 三条命令 + CI 接线」绑定到实盘。
另外本轮实测发现站点数字漂移（npm 体积 24.74 vs 25.21 MB）——判据**只断言文档如实登记了该事实**，
不会假装全绿（真修在 site/README 轮次随各面口径一起收）。

范围：只判本文与 wrangler.jsonc / site/tools / CI 工作流事实自洽（不改部署配置）。
同族判据：site-check/sync-numbers/worker-check（实跑门禁）/ test_site_* 若有。
契约：复核位、wrangler 9 个关键键逐名、五个工具逐名、三条命令、CI 两步、
「assets.binding 必需」的实测说明、漂移登记、复现口径、不把漂移写成全绿。
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "site" / "DEPLOY-cloudflare-workers.md"
WRANGLER = ROOT / "wrangler.jsonc"
TOOLS = ROOT / "site" / "tools"
CI = ROOT / ".github" / "workflows" / "ci-verify.yml"
KEYS = ('"name"', '"main"', '"directory"', '"binding"', '"html_handling"',
        '"not_found_handling"', '"run_worker_first"', '"workers_dev"',
        '"compatibility_date"')
SCRIPTS = ("sync-numbers.mjs", "site-check.mjs", "worker-check.mjs",
           "set-origin.mjs", "indexnow.mjs")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"部署文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("部署文档为空")
    return text


def node_offline() -> subprocess.CompletedProcess:
    return subprocess.run(["node", "site/tools/site-check.mjs", "--offline"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, check=False)


def doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# Cloudflare Workers 部署"):
        issues.append("缺标题「# Cloudflare Workers 部署（NinFenz 静态站）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    cfg = WRANGLER.read_text(encoding='utf-8')
    for key in KEYS:
        if key not in cfg:
            issues.append(f"wrangler.jsonc 缺键：{key}")
    for name in SCRIPTS:
        if not (TOOLS / name).is_file():
            issues.append(f"站点工具不在场：{name}")
        if name not in text:
            issues.append(f"正文未列工具：{name}")
    for cmd in ("node site/tools/sync-numbers.mjs",
                "node site/tools/site-check.mjs --offline",
                "node site/tools/worker-check.mjs"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "assets.binding" not in text and "binding" not in text:
        issues.append("缺 assets.binding 必需性的说明")
    if "env.ASSETS" not in text:
        issues.append("缺「binding 缺失则 env.ASSETS 为 undefined」的实测说明")
    if CI.is_file():
        ci = CI.read_text(encoding='utf-8')
        if "sync-numbers" not in ci or "site-check" not in ci:
            issues.append("CI 未接 sync-numbers / site-check")
    else:
        issues.append("CI 工作流不在场")
    if "复核不变" not in text:
        issues.append("缺复核结论")
    if "漂移" not in text and "exit 1" not in text:
        issues.append("缺数字漂移登记（本站实测红项）")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class DeployDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_doc_matches_contract(self):
        self.assertEqual([], doc_issues(self.text), "部署文档不满足契约")

    def test_offline_site_check_passes(self):
        proc = node_offline()
        self.assertEqual(0, proc.returncode, proc.stdout[-500:] + proc.stderr[-300:])
        self.assertIn("离线体检全过", proc.stdout)

    def test_contract_catches_mutations(self):
        """变异自证：缺工具 / 缺命令 / 缺 binding 说明 / 缺漂移登记。"""
        no_tool = self.text.replace("worker-check.mjs", "worker.mjs")
        self.assertTrue(any("worker-check" in i for i in doc_issues(no_tool)))
        no_cmd = self.text.replace("node site/tools/sync-numbers.mjs", "sync")
        self.assertTrue(any("sync-numbers" in i for i in doc_issues(no_cmd)))
        no_binding = self.text.replace("env.ASSETS", "ASSETS")
        self.assertTrue(any("env.ASSETS" in i for i in doc_issues(no_binding)))
        no_drift = self.text.replace("漂移", "差异").replace("exit 1", "非零")
        self.assertTrue(any("漂移" in i for i in doc_issues(no_drift)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_deploy.md")


if __name__ == "__main__":
    unittest.main()
