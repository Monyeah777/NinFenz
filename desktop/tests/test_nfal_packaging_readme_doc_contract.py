#!/usr/bin/env python3
"""packaging/nfal/README.md 契约：镜像形态 / 子命令 / 本机限制必须与 Dockerfile 与 CI 一致。

为什么必须有：这份 README 是「NFA-L 容器怎么建、怎么跑」的唯一说明，但此前没有判据——
最容易漂的三件事：① 镜像到底装了什么（只装引擎，内容靠卷挂载）；② 基座是否仍按 digest 钉死；
③ 本机没有容器引擎时，文档有没有把「未在本地构建」说清（否则读者以为已验证）。
本轮补「§现状对照」「§复现与引用口径」并加本判据。

范围：只判本文与 Dockerfile / 工作流 / CLI 事实自洽（不构建镜像）。
同族判据：test_docker_nfal_workflow_contract.py / test_nfal_doc_contract.py（docs/nfal.md）。
契约：复核位、基座 digest 钉版、无 RUN pip install、ENTRYPOINT core.nfal_cli、VOLUME /repo、
5 子命令、工作流 2 job、44 例判据、本机无 Docker 如实标注、复现命令在场。
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "packaging" / "nfal" / "README.md"
DOCKER = ROOT / "packaging" / "nfal" / "Dockerfile"
WF = ROOT / ".github" / "workflows" / "docker-nfal.yml"
CLI = ROOT / "desktop" / "src" / "core" / "nfal_cli.py"
SUBS = ("parse", "check", "build", "eval", "schema-check")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"nfal README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("nfal README 为空")
    return text


def cli_out() -> str:
    proc = subprocess.run([sys.executable, "-m", "core.nfal_cli", "--help"],
                          cwd=str(ROOT / "desktop" / "src"), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, check=False)
    return proc.stdout + proc.stderr


def nfal_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NFA-L 容器分发"):
        issues.append("缺标题「# NFA-L 容器分发（零成本）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for section in ("## 构建", "## 运行", "## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    docker = DOCKER.read_text(encoding="utf-8")
    froms = re.findall(r"(?m)^FROM\s+(\S+)", docker)
    if len(froms) != 1 or "@sha256:" not in froms[0]:
        issues.append("Dockerfile 基座未保持单一 @sha256 钉版")
    if re.search(r"(?m)^RUN[^\n]*pip install", docker):
        issues.append("Dockerfile 出现 RUN pip install（应零依赖）")
    if "core.nfal_cli" not in docker:
        issues.append("Dockerfile ENTRYPOINT 不是 core.nfal_cli")
    if 'VOLUME ["/repo"]' not in docker:
        issues.append("Dockerfile 缺 VOLUME /repo（内容靠卷挂载）")
    if "sha256:5e2bdb1b" not in text:
        issues.append("正文未写基座 digest 前缀")
    if "**按 digest 钉死**" not in text:
        issues.append("现状未写「按 digest 钉死」")
    for sub in SUBS:
        if sub not in text:
            issues.append(f"正文缺子命令：{sub}")
        if sub not in CLI.read_text(encoding="utf-8"):
            issues.append(f"实现缺子命令：{sub}")
    if "**5 个**" not in text:
        issues.append("现状未写 5 子命令")
    wf = WF.read_text(encoding="utf-8")
    if wf.count("\njobs:") < 1 or wf.count("name: build-") != 2:
        issues.append("工作流 job 数已变（应 2 个）")
    if "**2 个 job**" not in text:
        issues.append("现状未写 2 个 job")
    if "**44 例**" not in text:
        issues.append("现状未写 44 例判据")
    if "本机无 Docker" not in text and "本机**无 Docker**" not in text:
        issues.append("缺「本机无 Docker」如实标注")
    for cmd in ("docker build -f packaging/nfal/Dockerfile -t nfal .",
                "python -m pytest desktop/tests/test_docker_nfal_workflow_contract.py -q"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    for line in text.splitlines():
        if "镜像自带内容" in line and "不要" not in line and "别" not in line:
            issues.append("文档把「卷挂载」写成「镜像自带内容」")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class NfalReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_nfal_readme_matches_contract(self):
        self.assertEqual([], nfal_issues(self.text), "nfal README 不满足契约")

    def test_cli_has_five_subcommands(self):
        out = cli_out()
        self.assertIn("{parse,check,build,eval,schema-check}", out)

    def test_contract_catches_mutations(self):
        """变异自证：缺本机限制 / 缺 digest / 子命令漏写 / 写成镜像自带内容。"""
        no_limit = self.text.replace("本机无 Docker", "本机已构建")
        self.assertTrue(any("本机无 Docker" in i for i in nfal_issues(no_limit)))
        no_digest = self.text.replace("sha256:5e2bdb1b", "sha256:00000000")
        self.assertTrue(any("digest" in i for i in nfal_issues(no_digest)))
        no_sub = self.text.replace("`schema-check`", "`schema`")
        self.assertTrue(any("schema-check" in i for i in nfal_issues(no_sub)))
        wrong = self.text + "\n镜像自带内容。\n"
        self.assertTrue(any("镜像自带内容" in i for i in nfal_issues(wrong)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_nfal_readme.md")


if __name__ == "__main__":
    unittest.main()
