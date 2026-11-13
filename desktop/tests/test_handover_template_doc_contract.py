#!/usr/bin/env python3
"""handovers/HO-9000-示例-接力模板.md 契约：模板必须可机检、口径与协议件一致、公开面只留模板。

为什么必须有：这是公开仓里唯一的接力件样板——它是「怎么写交接」的唯一示范，但没有自己的判据：
五段/必填字段/状态词表/未决项带判据/refs 可解析 这些口径全在 `protocol/handover.json` 与
`nf handover check` 里，模板本身不与它们对账（改模板就可能演示一个不合规的写法）。
本轮补「§模板自检（可核口径）」并加本判据，把模板 ⇄ 协议件 ⇄ CLI 三方钉住。

范围：只判模板与协议/CLI/发布边界事实自洽（不改五段正文）。
同族判据：test_publish_boundary.py / test_adr_0000_contract.py / test_cli_json_face.py。
契约：frontmatter 六必填、五段逐段、状态词表、未决项带判据、refs 逐条可解析、
三条只读命令在场、自检段声明「不是第六段」、公开目录只有 README + HO-9xxx。
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "handovers" / "HO-9000-示例-接力模板.md"
PROTO = ROOT / "protocol" / "handover.json"
DIR = ROOT / "handovers"
CMDS = ("handover check", "handover verify", "handover ls")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"接力模板不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("接力模板为空")
    return text


def proto() -> dict:
    return json.loads(PROTO.read_text(encoding="utf-8"))


def cli_check() -> str:
    proc = subprocess.run([sys.executable, "scripts/nf.py", "handover", "check",
                           "handovers/HO-9000-示例-接力模板.md"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, check=False)
    return proc.stdout + proc.stderr + f"[rc={proc.returncode}]"


def template_issues(text: str) -> list:
    issues = []
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        issues.append("缺 frontmatter（--- 包裹）")
        fm = {}
    else:
        fm = {}
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
    p = proto()
    for field in p["required_fields"]:
        if field not in fm:
            issues.append(f"frontmatter 缺必填字段：{field}")
    if fm.get("status") not in p["status_vocabulary"]:
        issues.append(f"status 不在词表：{fm.get('status')}")
    if not re.fullmatch(r"HO-9\d{3}", fm.get("id", "")):
        issues.append(f"id 不符合 HO-9xxx：{fm.get('id')}")
    for sec in p["sections"]:
        if f"## {sec}" not in text:
            issues.append(f"缺段：## {sec}")
    if "判据" not in text:
        issues.append("未决项缺「判据」要求")
    if "不是第六段" not in text:
        issues.append("缺「自检段不是第六段」声明")
    for cmd in CMDS:
        if cmd not in text:
            issues.append(f"缺只读命令：{cmd}")
    if "私有仓" not in text:
        issues.append("缺「真实交接件在私有仓」边界")
    refs = re.findall(r"^  - (\S+)$", text, re.M)
    if len(refs) < 3:
        issues.append(f"refs 过少（{len(refs)}）")
    out = cli_check()
    if "rc=0" not in out:
        issues.append(f"nf handover check 未通过：{out[-120:]}")
    names = sorted(p.name for p in DIR.iterdir() if p.is_file())
    if names != ["HO-9000-示例-接力模板.md", "README.md"]:
        issues.append(f"公开目录出现非模板件：{names}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class HandoverTemplateDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_template_matches_contract(self):
        self.assertEqual([], template_issues(self.text), "接力模板不满足契约")

    def test_protocol_and_cli_live(self):
        self.assertEqual(("情境", "背景", "评估", "建议", "未决项"), tuple(proto()["sections"]))
        self.assertIn("rc=0", cli_check())

    def test_contract_catches_mutations(self):
        """变异自证：缺段 / 状态跑出词表 / 缺命令 / 缺判据 / id 不合式。"""
        no_sec = self.text.replace("## 评估", "## 现状")
        self.assertTrue(any("评估" in i for i in template_issues(no_sec)))
        bad_status = self.text.replace("status: open", "status: wip")
        self.assertTrue(any("词表" in i for i in template_issues(bad_status)))
        no_cmd = self.text.replace("handover verify", "看验证")
        self.assertTrue(any("handover verify" in i for i in template_issues(no_cmd)))
        no_judge = self.text.replace("判据", "说明")
        self.assertTrue(any("判据" in i for i in template_issues(no_judge)))
        bad_id = self.text.replace("id: HO-9000", "id: HO-9x")
        self.assertTrue(any("HO-9xxx" in i for i in template_issues(bad_id)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_handover.md")


if __name__ == "__main__":
    unittest.main()
