#!/usr/bin/env python3
"""CODEOWNERS 契约判据：承重面必须显式归人、规则不得空转、owner 与维护者表同源（2026-11-11）。

为什么必须有：CODEOWNERS 是评审分派面，写错不会让任何测试红——死 pattern 静默失效、
owner 写成不存在的人、承重面（门禁/协议/判据/投稿面）漏列，都不会有人发现。GitHub 的语义是
「最后一条匹配生效」，所以顺序也是语义。本件把「能用的 CODEOWNERS」钉成契约。

范围：只判 .github/CODEOWNERS。同族判据：test_maintainers_contract（执行主体真源）、
test_ci_supply_chain（workflow 面）。
"""
import fnmatch
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
MAINTAINERS = ROOT / "MAINTAINERS.md"

#: 承重面：必须有 **非 *** 的显式规则覆盖（用代表路径判定）
CRITICAL = (
    "verify.sh", "STRATEGY.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md",
    "CODE_OF_CONDUCT.md", "MAINTAINERS.md", "LICENSE", "REUSE.toml",
    "CITATION.cff", ".zenodo.json", "THIRD-PARTY-NOTICES.md",
    "protocol/", "scripts/", "desktop/tests/", "desktop/src/core/",
    ".github/", "library/", "community/", "packaging/", "site/",
)
OWNER_RE = re.compile(r"^@[A-Za-z0-9](?:[A-Za-z0-9-]*)$")


def load_text(path: Path = CODEOWNERS) -> str:
    """读 CODEOWNERS（缺失 / 空件显式报错）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"CODEOWNERS 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("CODEOWNERS 为空")
    return text


def tracked_files(root: Path = ROOT) -> list:
    """git 追踪面（CODEOWNERS 只管受跟踪文件）。"""
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"git ls-files 不可用：{exc}") from exc
    return [p for p in proc.stdout.split("\0") if p]


def parse_rules(text: str) -> list:
    """→ [(pattern, [owners])]；跳过空行与整行注释（CODEOWNERS 不支持行内注释）。"""
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        rules.append((parts[0], parts[1:]))
    return rules


def rule_matches(pattern: str, path: str) -> bool:
    """CODEOWNERS 语义的子集：* / 根锚定 / 尾斜杠目录 / fnmatch。"""
    p = pattern.strip()
    if p == "*":
        return True
    root_only = p.startswith("/")
    if root_only:
        p = p[1:]
    if p.endswith("/"):
        base = p.rstrip("/")
        return path == base or path.startswith(base + "/")
    if "/" in p or root_only:
        return fnmatch.fnmatchcase(path, p) or path == p
    return fnmatch.fnmatchcase(Path(path).name, p)


def maintainer_owners() -> set:
    """维护者表里点名的 GitHub 账号（owner 真源）。"""
    return set(re.findall(r"@([A-Za-z0-9][A-Za-z0-9-]*)",
                          MAINTAINERS.read_text(encoding="utf-8")))


def representative(path_prefix: str, files: list) -> str:
    """承重面的代表文件（目录用前缀匹配，文件用全等）。"""
    if path_prefix.endswith("/"):
        base = path_prefix.rstrip("/")
        for rel in files:
            if rel == base or rel.startswith(base + "/"):
                return rel
        return ""
    return path_prefix if path_prefix in files else ""


def codeowners_issues(text: str, files: list = None) -> list:
    """CODEOWNERS 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    rules = parse_rules(text)
    if not rules:
        return ["没有任何规则（全仓无 owner）"]
    files = tracked_files() if files is None else files
    owners = set()
    for pattern, rule_owners in rules:
        if not rule_owners:
            issues.append(f"规则缺 owner：{pattern}")
        for owner in rule_owners:
            if not OWNER_RE.match(owner):
                issues.append(f"owner 格式非法：{owner!r}（应为 @handle）")
            owners.add(owner.lstrip("@"))
    want = maintainer_owners()
    if want and owners != want:
        issues.append(f"owner 与 MAINTAINERS.md 不一致：{sorted(owners)} ≠ {sorted(want)}")
    if rules[0][0] != "*":
        issues.append("首条规则必须是 catch-all `*`（否则未列面无人认领）")
    for pattern, _rule_owners in rules:
        if not any(rule_matches(pattern, rel) for rel in files):
            issues.append(f"规则空转（不匹配任何受跟踪文件）：{pattern}")
    for prefix in CRITICAL:
        rel = representative(prefix, files)
        if not rel:
            issues.append(f"承重面不在追踪面：{prefix}")
            continue
        explicit = [pattern for pattern, _owners in rules
                    if pattern != "*" and rule_matches(pattern, rel)]
        if not explicit:
            issues.append(f"承重面缺显式规则：{prefix}")
    return issues


class CodeownersContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()
        self.files = tracked_files()

    def test_codeowners_matches_contract(self):
        self.assertEqual([], codeowners_issues(self.text, self.files),
                         "CODEOWNERS 不满足契约")

    def test_no_dead_rules(self):
        """每条规则都必须命中至少一个受跟踪文件。"""
        for pattern, _owners in parse_rules(self.text):
            self.assertTrue(any(rule_matches(pattern, rel) for rel in self.files),
                            f"规则空转：{pattern}")

    def test_critical_surfaces_are_explicit(self):
        """承重面必须有显式（非 *）规则，将来加第二 reviewer 时不用重新判断。"""
        for prefix in CRITICAL:
            rel = representative(prefix, self.files)
            self.assertTrue(rel, f"承重面不在追踪面：{prefix}")
            explicit = [p for p, _o in parse_rules(self.text)
                        if p != "*" and rule_matches(p, rel)]
            self.assertTrue(explicit, f"承重面缺显式规则：{prefix}")

    def test_owner_matches_maintainers(self):
        """owner 必须是维护者表里点名的人（单一执行主体真源）。"""
        owners = {o.lstrip("@") for _p, rule_owners in parse_rules(self.text)
                  for o in rule_owners}
        self.assertEqual(maintainer_owners(), owners, "CODEOWNERS owner 与 MAINTAINERS 不一致")

    def test_contract_catches_broken_codeowners(self):
        """变异自证：删 catch-all / 死规则 / 错 owner / 漏承重面——都必须报。"""
        no_catchall = self.text.replace("*                                 @Monyeah777\n", "")
        self.assertTrue(any("catch-all" in i for i in codeowners_issues(no_catchall, self.files)),
                        "删掉 catch-all 必须报")
        dead = self.text + "\n/no_such_dir/            @Monyeah777\n"
        self.assertTrue(any("空转" in i for i in codeowners_issues(dead, self.files)),
                        "死规则必须报")
        bad_owner = self.text.replace("@Monyeah777", "@ghost-user")
        self.assertTrue(any("不一致" in i or "非法" in i
                            for i in codeowners_issues(bad_owner, self.files)),
                        "owner 漂移必须报")
        no_critical = self.text.replace("/scripts/                         @Monyeah777\n", "")
        self.assertTrue(any("scripts/" in i for i in codeowners_issues(no_critical, self.files)),
                        "漏掉承重面必须报")
        with self.assertRaises(ValueError):
            load_text(ROOT / ".github" / "no_such_codeowners")


if __name__ == "__main__":
    unittest.main()
