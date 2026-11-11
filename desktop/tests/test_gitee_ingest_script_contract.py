#!/usr/bin/env python3
"""gitee_ingest 脚本契约判据：先真源后镜像、幂等、令牌不外泄、有界、屏障齐全（2026-11-11）。

为什么必须有：这是每 10 分钟跑一轮的跨端机器人，本体错误会被高频放大。两处真实风险：①**推送顺序**——
先推 Gitee 镜像再推 origin，会让镜像领先真源，下一次镜像推送必然非快进 → 镜像**永久卡死**；
②**幂等**——入库成功后若回评/关闭失败，下一轮必须靠「来源：Gitee Issue #N」认出来，
否则重复入库。
本件把顺序、幂等、令牌纪律、有界响应、拒收闸门钉成契约。

范围：只判 .github/scripts/gitee_ingest.py。同族判据：test_gitee_poll_workflow_contract（调度面）、
test_library_ingest_script_contract（GitHub 前端对称件）。
"""
import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "gitee_ingest.py"
ALLOWED_MODULES = {"json", "os", "re", "sys", "urllib", "urllib.request",
                   "datetime", "glob", "core"}
TOKEN_SHAPE = re.compile(r"(ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{22,}|sk-[0-9A-Za-z]{20,})")


def load_script():
    spec = importlib.util.spec_from_file_location("nf_gitee_ingest", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def script_issues(text: str) -> list:
    """Gitee 机器人契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    mods = set()
    for m in re.finditer(r"(?m)^import\s+([A-Za-z0-9_.]+)", text):
        mods.add(m.group(1))
    for m in re.finditer(r"(?m)^from\s+([A-Za-z0-9_.]+)\s+import", text):
        mods.add(m.group(1))
    extra = {m for m in mods
             if m not in ALLOWED_MODULES and not m.startswith(("core", "urllib"))}
    if extra:
        issues.append(f"只许标准库（+core）：出现 {sorted(extra)}")
    for needle, why in (
            ("MAX_BODY_CHARS", "必须有正文超长拒收"),
            ("secret_shape_hit", "必须有密钥形状拒收"),
            ("injection_probe", "必须有注入面记档"),
            ("fm_fields_ok", "必须有 frontmatter 形状闸门"),
            ("load_gate('gitee')", "必须走 gitee 通道闸门声明"),
            ("quota_denial", "必须有投稿配额闸门"),
            ("record_quota", "入库成功必须记配额"),
            ("SEG_RE", "必须校验档位/自定义段字符"),
            ("to_b36", "编号必须走 36 进制"),
            ("atomic_write", "落盘必须走原子写"),
            ("redact", "日志/错误必须脱敏"),
            ("修复指引", "错误文案必须带修复指引")):
        if needle not in text:
            issues.append(f"脚本缺口径：{why}")
    if "GITEE_TOKEN" not in text:
        issues.append("令牌必须只从 GITEE_TOKEN env 取")
    if "secret=TOKEN" not in text:
        issues.append("git 调用必须传 secret=TOKEN（回显脱敏）")
    if TOKEN_SHAPE.search(text):
        issues.append("脚本里不得出现明文 token 形状字符串（若为文档示例请加空格断开）")
    for needle, why in (("_read_bounded", "API 响应必须有界"),
                        ("MAX_API_RESPONSE_BYTES", "响应上限常量"),
                        ("MAX_ISSUE_PAGES", "issue 分页必须有上限"),
                        ("page_limit", "翻页超限必须显式失败")):
        if needle not in text:
            issues.append(f"脚本缺口径：{why}")
    if "already_processed" not in text or "来源：Gitee Issue #" not in text:
        issues.append("必须有幂等防重（来源：Gitee Issue #N 认账）")
    origin_at = text.find("git('push', 'origin'")
    mirror_at = text.find("git('push', gitee_url")
    if origin_at < 0 or mirror_at < 0:
        issues.append("必须双向推送（origin + gitee_url）")
    elif origin_at > mirror_at:
        issues.append("推送顺序必须**先 origin（真源）后 Gitee（镜像）**，否则镜像会永久卡死")
    for remote, why in (("'origin'", "真源"), ("gitee_url", "镜像")):
        if f"git('pull', '--rebase', {remote}" not in text:
            issues.append(f"{why}推送必须有 pull --rebase 重试（否则一次非快进就丢/卡）")
    if "gitee.com/api/v5" not in text:
        issues.append("Gitee API 必须走 v5")
    if "DRY_RUN" not in text:
        issues.append("必须有 DRY_RUN 干跑通道")
    for bad in ("subprocess", "os.system", "eval(", "exec("):
        if bad in text:
            issues.append(f"脚本不得引入执行面：{bad}")
    if re.search(r"open\([^)]*['\"]w", text):
        issues.append("落盘只许 atomic_write，禁止裸 open(..., 'w')")
    return issues


class GiteeIngestScriptContractTest(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_script_matches_contract(self):
        self.assertEqual([], script_issues(self.text), "gitee_ingest.py 不满足契约")

    def test_already_processed_recognizes_source_marker(self):
        """幂等口径功能测试：注记头含「来源：Gitee Issue #N」即认账。"""
        mod = load_script()
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                os.makedirs("library")
                Path("library/NF-1.md").write_text(
                    "> 来源：Gitee Issue #7（NF 投稿通道）\n", encoding="utf-8")
                self.assertTrue(mod.already_processed(7))
                self.assertFalse(mod.already_processed(8))
            finally:
                os.chdir(cwd)

    def test_contract_catches_broken_script(self):
        """变异自证（五类坏件都必须报）。

        覆盖：推送顺序颠倒 / 去镜像 rebase / 去幂等 / 去分页上限 / 引第三方依赖。
        """
        origin_line = "    git('push', 'origin', 'HEAD:main')"
        mirror_line = "        git('push', gitee_url, 'HEAD:main')"
        swapped = self.text.replace(origin_line, "@@ORIGIN@@").replace(
            mirror_line, origin_line).replace("@@ORIGIN@@", mirror_line)
        self.assertTrue(any("顺序" in i for i in script_issues(swapped)),
                        "推送顺序颠倒必须报")
        no_mirror_rebase = self.text.replace("git('pull', '--rebase', gitee_url, 'main')", "pass")
        self.assertTrue(any("rebase" in i for i in script_issues(no_mirror_rebase)),
                        "去镜像 rebase 必须报")
        no_idem = self.text.replace("already_processed", "x")
        self.assertTrue(any("幂等" in i for i in script_issues(no_idem)),
                        "去幂等必须报")
        no_cap = self.text.replace("MAX_ISSUE_PAGES", "999999")
        self.assertTrue(any("分页" in i or "上限" in i for i in script_issues(no_cap)),
                        "去分页上限必须报")
        extra_dep = "import requests\n" + self.text
        self.assertTrue(any("标准库" in i for i in script_issues(extra_dep)),
                        "引第三方依赖必须报")


if __name__ == "__main__":
    unittest.main()
