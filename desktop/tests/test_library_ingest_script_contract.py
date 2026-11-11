#!/usr/bin/env python3
"""library_ingest 脚本契约判据：标准库、真源通道、拒收闸门、原子写、推送韧性（2026-11-11）。

为什么必须有：workflow 判据守住了调度/权限/凭据，但**机器人本体**（正文真源、超长拒收、
密钥形状拒收、注入记档、编号唯一、原子写、推送）此前零专项判据。它直接写公开仓，错误不可逆；
且本 workflow 只在 issues:opened 触发 —— 推送失败不会自动重跑，投稿会**静默丢失**
（本轮已加 rebase 重试 + Issue 可执行提示）。

范围：只判 .github/scripts/library_ingest.py。同族判据：test_library_ingest_workflow_contract
（调度/权限面）、test_intake_bots_hardening。
"""
import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "library_ingest.py"
ALLOWED_MODULES = {"json", "os", "re", "sys", "urllib", "urllib.request",
                   "datetime", "glob", "core"}


def load_script():
    """按文件路径导入脚本模块（它自己会插入 desktop/src 到 sys.path）。"""
    spec = importlib.util.spec_from_file_location("nf_library_ingest", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def script_issues(text: str) -> list:
    """脚本契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    mods = set()
    for m in re.finditer(r"(?m)^import\s+([A-Za-z0-9_.]+)", text):
        mods.add(m.group(1))
    for m in re.finditer(r"(?m)^from\s+([A-Za-z0-9_.]+)\s+import", text):
        mods.add(m.group(1))
    extra = {m for m in mods if m not in ALLOWED_MODULES and not m.startswith("core")}
    if extra:
        issues.append(f"只许标准库（+core）：出现 {sorted(extra)}")
    for needle, why in (
            ("MAX_BODY_CHARS", "必须有正文超长拒收"),
            ("secret_shape_hit", "必须有密钥形状拒收（防二次公开分发）"),
            ("injection_probe", "必须有注入面记档"),
            ("fm_fields_ok", "必须有 frontmatter 形状闸门"),
            ("load_gate", "必须读闸门声明（open/author_only/paused）"),
            ("quota_denial", "必须有投稿配额闸门"),
            ("SEG_RE", "必须校验档位/自定义段字符"),
            ("to_b36", "编号必须走 36 进制"),
            ("atomic_write", "落盘必须走原子写（防半截文件进公开仓）"),
            ("redact", "日志/错误必须脱敏（令牌不进 CI 日志）"),
            ("修复指引", "错误文案必须带修复指引（本仓文案纪律）")):
        if needle not in text:
            issues.append(f"脚本缺口径：{why}")
    if "resolve_body" not in text:
        issues.append("缺正文真源函数 resolve_body")
    else:
        fn = text.split("def resolve_body", 1)[1].split("\ndef ", 1)[0]
        order = [fn.find(k) for k in ("ISSUE_BODY_FILE", "BODY", "api(")]
        if any(i < 0 for i in order) or order != sorted(order):
            issues.append("正文真源优先级必须为 文件 > env > API（生产真源最后兜底）")
    if "git('push'" not in text:
        issues.append("缺推送调用")
    if "pull', '--rebase'" not in text:
        issues.append("推送必须有 rebase 重试（否则一次非快进就丢投稿）")
    if "推送 main 失败" not in text:
        issues.append("推送最终失败必须在 Issue 留可执行提示")
    for bad in ("subprocess", "os.system", "eval(", "exec("):
        if bad in text:
            issues.append(f"脚本不得引入执行面：{bad}")
    if re.search(r"open\([^)]*['\"]w", text):
        issues.append("落盘只许 atomic_write，禁止裸 open(..., 'w')")
    return issues


class LibraryIngestScriptContractTest(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_script_matches_contract(self):
        self.assertEqual([], script_issues(self.text), "library_ingest.py 不满足契约")

    def test_resolve_body_file_beats_env(self):
        """正文真源优先级：文件 > env（API 只在生产姿势下兜底）。"""
        mod = load_script()
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write("# 标题\n正文来自文件\n")
            path = fh.name
        old = {k: os.environ.get(k) for k in ("ISSUE_BODY_FILE", "ISSUE_BODY")}
        try:
            os.environ["ISSUE_BODY_FILE"] = path
            os.environ["ISSUE_BODY"] = "env 正文"
            mod.BODY = "env 正文"
            self.assertIn("正文来自文件", mod.resolve_body())
        finally:
            os.environ.pop("ISSUE_BODY_FILE", None)
            if old["ISSUE_BODY"] is not None:
                os.environ["ISSUE_BODY"] = old["ISSUE_BODY"]
            else:
                os.environ.pop("ISSUE_BODY", None)
            os.unlink(path)

    def test_contract_catches_broken_script(self):
        """变异自证（五类坏件都必须报）。

        覆盖：去超长拒收 / 去密钥拒收 / 去原子写 / 去 rebase 重试 / 引第三方依赖。
        """
        for needle, why in ((r"MAX_BODY_CHARS", "超长"), (r"secret_shape_hit", "密钥"),
                            (r"atomic_write", "原子写"), (r"pull', '--rebase'", "rebase")):
            mutated = re.sub(needle, "x", self.text)
            self.assertTrue(any(why in i for i in script_issues(mutated)),
                            f"去掉 {why} 必须报")
        extra_dep = "import requests\n" + self.text
        self.assertTrue(any("标准库" in i for i in script_issues(extra_dep)),
                        "引第三方依赖必须报")
        shells = self.text + "\nos.system('rm -rf x')\n"
        self.assertTrue(any("执行面" in i for i in script_issues(shells)),
                        "执行面必须报")


if __name__ == "__main__":
    unittest.main()
