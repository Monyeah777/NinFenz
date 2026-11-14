#!/usr/bin/env python3
"""packaging/hf-space/README.md 契约：Space 说明必须「模式 / 限额 / 端口 / 前提 / doctor」自洽。

为什么必须有：这份 README 是 HF Space 的卡片（frontmatter 决定平台参数），也是「浏览器里跑真门禁」
的唯一说明；但此前散文只写「17 项只读体检」，没有一处可核——读者无法确认四模式是哪四条、
限额多少、缺 NF 树时怎么失败、镜像是钉版还是浮动 tag。本轮补「§现状对照」「§复现与引用口径」
并加本判据，把 README ⇄ server.py ⇄ Dockerfile ⇄ doctor 实测钉住。

范围：只判文档与 Space 实现/载体事实自洽（不改实现）。
同族判据：test_doc_hygiene.py / test_doc_examples.py（本页 bash 块首行须是 nf/python 命令）。
契约：frontmatter（sdk docker / app_port 7860）、四模式逐名、200 KB / 180 s 限额、
零 pip、两段 `@sha256` 钉版、EXPOSE 7860 + CMD server.py、缺树退出码 3、doctor 17/17 实测。
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "packaging" / "hf-space" / "README.md"
SERVER = ROOT / "packaging" / "hf-space" / "server.py"
DOCKER = ROOT / "packaging" / "hf-space" / "Dockerfile"
MODES = ("lint", "stats", "conformance", "doctor")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"HF Space README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("HF Space README 为空")
    return text


def doctor_total() -> str:
    proc = subprocess.run([sys.executable, "scripts/nf.py", "doctor"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, check=False)
    m = re.search(r"体检：(\d+)/(\d+) 通过", proc.stdout)
    return m.group(0) if m else ""


def space_issues(text: str) -> list:
    issues = []
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        issues.append("缺 frontmatter（HF Space 卡片头）")
        fm = ""
    else:
        fm = m.group(1)
    if "sdk: docker" not in fm or "app_port: 7860" not in fm:
        issues.append("frontmatter 缺 sdk: docker / app_port: 7860")
    for section in ("## 能做什么", "## 实现纪律", "## 本地复现", "## 现状对照",
                    "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    server = SERVER.read_text(encoding="utf-8")
    for mode in MODES:
        if f"('{mode}'" not in server:
            issues.append(f"server.py 白名单缺模式：{mode}")
        if mode not in text:
            issues.append(f"正文缺模式：{mode}")
    if "**4**" not in text:
        issues.append("现状未写 4 模式")
    if "MAX_INPUT = 200_000" not in server or "**200 KB**" not in text:
        issues.append("输入上限（200 KB）与 server.py 不一致")
    if "TIMEOUT_S = 180" not in server or "**180 s**" not in text:
        issues.append("超时上限（180 s）与 server.py 不一致")
    if "pip install" in server:
        issues.append("server.py 出现 pip install（应零第三方依赖）")
    docker = DOCKER.read_text(encoding="utf-8")
    froms = re.findall(r"(?m)^FROM\s+(\S+)", docker)
    if len(froms) < 2 or any("@sha256:" not in f for f in froms):
        issues.append("Dockerfile 基座未全部按 @sha256 钉版")
    if "EXPOSE 7860" not in docker or '"server.py"' not in docker:
        issues.append("Dockerfile 缺 EXPOSE 7860 或 CMD server.py")
    if "**7860**" not in text:
        issues.append("现状未写端口 7860")
    if "@sha256" not in text:
        issues.append("现状未写镜像钉版")
    if "退出码 **3**" not in text:
        issues.append("缺「缺 NF 树 → 退出码 3」标注")
    total = doctor_total()
    if "17/17" not in total:
        issues.append(f"doctor 实测不再是 17/17：{total}")
    if "**17/17 通过**" not in text:
        issues.append("现状未写 doctor 17/17")
    if "只读" not in text:
        issues.append("缺只读纪律")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class HfSpaceReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], space_issues(self.text), "HF Space README 不满足契约")

    def test_space_facts_live(self):
        self.assertIn("17/17", doctor_total())
        server = SERVER.read_text(encoding="utf-8")
        self.assertIn("MAX_INPUT = 200_000", server)
        self.assertIn("TIMEOUT_S = 180", server)

    def test_contract_catches_mutations(self):
        """变异自证：限额漂移 / 缺模式 / 端口漂移 / doctor 条数改错。"""
        bad = self.text.replace("**200 KB**", "**500 KB**")
        self.assertTrue(any("200 KB" in i for i in space_issues(bad)))
        no_mode = self.text.replace("conformance", "conf")
        self.assertTrue(any("conformance" in i for i in space_issues(no_mode)))
        bad_port = self.text.replace("**7860**", "**8080**")
        self.assertTrue(any("7860" in i for i in space_issues(bad_port)))
        bad_total = self.text.replace("**17/17 通过**", "**20/20 通过**")
        self.assertTrue(any("17/17" in i for i in space_issues(bad_total)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_space_readme.md")


if __name__ == "__main__":
    unittest.main()
