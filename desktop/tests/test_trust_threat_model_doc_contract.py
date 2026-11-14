#!/usr/bin/env python3
"""docs/trust/THREAT_MODEL.md 契约：STRIDE/删除矩阵/边界/红队/风险全绑定。

为什么必须有：威胁模型的价值全在**自洽**——行数覆盖计划、每条威胁指向现存控制点与判据、
未实现项显式标 OPEN/ACCEPTED-RISK、且不把 T0/T1 写成 T3/T4。没有判据时，这些主张会随
文档编辑静默漂移（本仓已有 docs/ccos/threat-model.md 的同族判据，本件是其 trust 面）。

范围：只判本文与实现事实自洽（不改承诺面）。同族判据：test_threat_model_doc_contract.py（CCOS 线）、
test_trust_schemas.py、test_evidence.py、test_trust_boundary.py。
契约：标题/复核位/节顺序、STRIDE 8 行与状态词表、删除矩阵 8 行、信任边界 6 行、红队 2 角色各 5 条、
ACCEPTED-RISK owner、禁用词否定语境、引用路径与测试文件在场、三条复核命令、变异自证。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "trust" / "THREAT_MODEL.md"

SECTIONS = (
    "## 这份文件管什么",
    "## 信任根与本机边界",
    "## 攻击者模型",
    "## STRIDE 矩阵",
    "## 删除 / 篡改矩阵",
    "## 信任边界",
    "## 密钥与信任根",
    "## 逐条性质：能证 / 不能证",
    "## 红队回合",
    "## ACCEPTED-RISK 登记",
    "## 已知缺口",
    "## 现状对照",
    "## 复核命令",
    "## 不承诺",
)
STRIDE_HEADER = ["编号", "类别", "威胁", "控制点", "判据", "状态"]
DT_HEADER = ["编号", "攻击", "期望", "控制点", "判据", "状态"]
TB_HEADER = ["编号", "边界", "内容", "威胁", "当前控制", "状态"]
RISK_HEADER = ["编号", "风险", "为什么接受", "owner", "触发信号"]
STATUS_PREFIX = ("T0", "T1", "T2", "OPEN", "ACCEPTED-RISK")
NEGATIVE_MARKERS = ("不承诺", "不能", "不做", "不提供", "不写", "不声称",
                    "非合规", "非认证", "只提供工程证据")
OPEN_IDS = ("OPEN-G1", "OPEN-G2", "OPEN-G3", "OPEN-G4")
CMDS = (
    "python -m pytest desktop/tests/test_trust_threat_model_doc_contract.py -q",
    "python -m pytest desktop/tests/test_evidence.py desktop/tests/test_timestamp.py -q",
    "python scripts/nf.py verify --only 42",
)
PATH_RE = re.compile(r"((?:desktop|scripts)/[A-Za-z0-9_./-]+\.py)")
TEST_RE = re.compile(r"(test_[a-z0-9_]+\.py)")
ATTACK_KEYS = ("obligation", "中间 step", "删尾", "拼接", "model-card", "撤销", "回拨", "无锚声称")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"威胁模型不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("威胁模型为空")
    return text


def parse_tables(text: str) -> list:
    """返回 [(表头 cells, 数据行 cells...)]；只收标准 pipe 表。"""
    blocks, cur = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cur.append([c.strip() for c in s[1:-1].split("|")])
        else:
            if cur:
                blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    out = []
    for block in blocks:
        if len(block) >= 2 and all(re.fullmatch(r":?-{2,}:?", c) for c in block[1]):
            out.append((block[0], block[2:]))
    return out


def find_table(text: str, header: list):
    for head, rows in parse_tables(text):
        if head == header:
            return rows
    return None


def _test_exists(name: str) -> bool:
    return (ROOT / "desktop" / "tests" / name).is_file()


def _role_block(text: str, role: str):
    """取「### 红队 X：」小节正文（到下一个二级/三级标题为止）。"""
    m = re.search(rf"^### {role}：.*$", text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^(?:##|###) ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# Trust Fabric 威胁模型 v0"):
        issues.append("缺标题「# Trust Fabric 威胁模型 v0」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核：" not in text:
        issues.append("缺「复核」说明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if "T3 / T4 不提供" not in text:
        issues.append("缺「T3 / T4 不提供」的等级诚实声明")
    for gid in OPEN_IDS:
        if gid not in text:
            issues.append(f"缺缺口：{gid}")

    stride = find_table(text, STRIDE_HEADER)
    if stride is None:
        issues.append("缺 STRIDE 表（表头必须为 编号/类别/威胁/控制点/判据/状态）")
    else:
        if len(stride) != 8:
            issues.append(f"STRIDE 行数 {len(stride)} ≠ 8（计划 §9.2 八行）")
        ids = [r[0] for r in stride]
        want_ids = [f"TH-{i:02d}" for i in range(1, 9)]
        if ids != want_ids:
            issues.append(f"STRIDE 编号不连续：{ids}")
        cats = {r[1] for r in stride}
        if not cats <= set("STRIDE") or len(cats - {"S"}) < 5:
            issues.append(f"STRIDE 类别异常：{sorted(cats)}")
        for row in stride:
            if any(not cell for cell in row):
                issues.append(f"STRIDE 行有空单元：{row[0]}")
                continue
            if not row[5].startswith(STATUS_PREFIX):
                issues.append(f"{row[0]} 状态词表越界：{row[5]}")
            if row[5].startswith("OPEN") and "计划" not in row[4]:
                issues.append(f"{row[0]} 标 OPEN 但判据未写「计划」")
            if row[5].startswith(("T0", "T1", "T2")):
                names = TEST_RE.findall(row[4])
                if not any(_test_exists(n) for n in names):
                    issues.append(f"{row[0]} 标已覆盖但未点名现存测试")

    dt = find_table(text, DT_HEADER)
    if dt is None:
        issues.append("缺删除/篡改矩阵（表头必须为 编号/攻击/期望/控制点/判据/状态）")
    else:
        if len(dt) != 8:
            issues.append(f"删除矩阵行数 {len(dt)} ≠ 8（计划 §9.3 八行）")
        if [r[0] for r in dt] != [f"DT-{i:02d}" for i in range(1, 9)]:
            issues.append("删除矩阵编号不连续")
        attacks = " ".join(r[1] for r in dt)
        for key in ATTACK_KEYS:
            if key not in attacks:
                issues.append(f"删除矩阵缺攻击：{key}")
        for row in dt:
            if any(not cell for cell in row):
                issues.append(f"删除矩阵行有空单元：{row[0]}")

    tb = find_table(text, TB_HEADER)
    if tb is None:
        issues.append("缺信任边界表（表头必须为 编号/边界/内容/威胁/当前控制/状态）")
    elif len(tb) != 6:
        issues.append(f"信任边界行数 {len(tb)} ≠ 6（计划 §9.1 六条）")

    risk = find_table(text, RISK_HEADER)
    if risk is None:
        issues.append("缺 ACCEPTED-RISK 表（表头必须为 编号/风险/为什么接受/owner/触发信号）")
    else:
        if len(risk) < 2:
            issues.append("ACCEPTED-RISK 少于 2 条")
        for row in risk:
            if not row[3] or row[3] in ("—", "-"):
                issues.append(f"{row[0]} 缺 owner")
            if len(row[4]) < 6:
                issues.append(f"{row[0]} 触发信号过短")
            if not row[0].startswith("R-"):
                issues.append(f"风险编号异常：{row[0]}")

    for role in ("红队 A", "红队 B"):
        block = _role_block(text, role)
        if block is None:
            issues.append(f"缺{role}")
            continue
        bullets = re.findall(r"^- ([AB])-([1-9]) ", block, re.M)
        if len(bullets) != 5:
            issues.append(f"{role} 应有 5 条攻击路径，实得 {len(bullets)}")
        if {b[1] for b in bullets} != {"1", "2", "3", "4", "5"}:
            issues.append(f"{role} 攻击编号不是 1..5")

    for line in text.splitlines():
        if "不可抵赖" in line and not any(m in line for m in NEGATIVE_MARKERS):
            issues.append(f"正面声明不可抵赖：{line.strip()[:60]}")
        if ("合规" in line or "认证" in line) and not any(
                m in line for m in NEGATIVE_MARKERS):
            issues.append(f"正面声明合规/认证：{line.strip()[:60]}")
        if "计划" not in line:
            for name in TEST_RE.findall(line):
                if not _test_exists(name):
                    issues.append(f"引用不存在的测试：{name}")
    for token in PATH_RE.findall(text):
        if not (ROOT / token).is_file():
            issues.append(f"引用不存在的实现件：{token}")
    for word in ("TODO", "FIXME"):
        if word in text:
            issues.append(f"含占位债：{word}")
    for cmd in CMDS:
        if cmd not in text:
            issues.append(f"复核命令缺失：{cmd}")
    return issues


class TrustThreatModelTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_doc_satisfies_contract(self):
        self.assertEqual([], doc_issues(self.text), "威胁模型不满足契约")

    def test_live_anchors_exist(self):
        self.assertTrue(DOC.is_file())
        self.assertEqual([], [t for t in PATH_RE.findall(self.text)
                              if not (ROOT / t).is_file()])

    def test_contract_catches_mutations(self):
        # ① 删一行 STRIDE：行数/编号必红
        lines = self.text.splitlines()
        th04 = [i for i, ln in enumerate(lines) if ln.startswith("| TH-04 ")]
        self.assertEqual(1, len(th04))
        dropped = "\n".join(ln for i, ln in enumerate(lines) if i != th04[0])
        self.assertTrue(any("STRIDE 行数" in i for i in doc_issues(dropped)))
        # ② 判据指向不存在的测试：引件必红
        broken = self.text.replace("test_meta_cockpit.py", "test_ghost_xyz.py", 1)
        self.assertTrue(any("不存在的测试" in i for i in doc_issues(broken)))
        # ③ 正面声明不可抵赖：禁用词必红
        claim = self.text + "\n\n本系统提供不可抵赖与合规认证。\n"
        self.assertTrue(any("不可抵赖" in i for i in doc_issues(claim)))
        # ④ 风险行缺 owner：必红
        no_owner = self.text.replace("Monyeah777（维护者）", "—", 1)
        self.assertTrue(any("缺 owner" in i for i in doc_issues(no_owner)))
        # ⑤ 红队缺一条路径：必红
        no_bullet = self.text.replace("- A-3 回放上一版证据包", "- 回放上一版证据包", 1)
        self.assertTrue(any("红队 A" in i for i in doc_issues(no_bullet)))
        # ⑥ 缺段：必红
        no_section = self.text.replace("## 不承诺", "## 其它", 1)
        self.assertTrue(any("缺段" in i for i in doc_issues(no_section)))
        # ⑦ 等级诚实：去掉「T3 / T4 不提供」必红
        no_level = self.text.replace("T3 / T4 不提供", "T3 / T4 部分提供", 1)
        self.assertTrue(any("T3 / T4 不提供" in i for i in doc_issues(no_level)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "docs" / "trust" / "no_such_threat_model.md")


if __name__ == "__main__":
    unittest.main()
