#!/usr/bin/env python3
"""Dependabot 契约判据：仓库里每一处版本固定都必须有跟进面（2026-11-11）。

为什么必须有：dependabot.yml 是供应链自动更新的唯一声明，写漏一个生态不会让任何测试红——
固定就退化成冻结上游安全修复（本仓实测两处漏面：pyproject extras 镜像、Rust 引擎 Cargo.lock；
容器 digest 也无跟进面）。本件把「覆盖完整 + 配置合法 + 分组不吞 major」钉成契约。

范围：只判 .github/dependabot.yml。同族判据：test_ci_supply_chain（action 固定面）、
test_third_party_notices_contract（依赖许可面）。
"""
import copy
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "dependabot.yml"

#: 合法更新节奏
INTERVALS = ("daily", "weekly", "monthly", "quarterly", "semiannually", "yearly")
#: 分组禁止吞 major（本仓策略：major 单独进 PR，安全修复才能插队）
GROUP_TYPES = {"minor", "patch"}
ECOSYSTEMS = ("github-actions", "pip", "npm", "cargo", "docker", "gitsubmodule")


def load_config(path: Path = CONFIG) -> dict:
    """读 dependabot.yml（缺失 / 非法 YAML / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"dependabot.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("dependabot.yml 根节点必须是映射")
    return doc


def tracked_files(root: Path = ROOT) -> list:
    """git 追踪面（只用受跟踪文件判断「真实存在的固定面」，避免本地产物污染）。"""
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"git ls-files 不可用：{exc}") from exc
    return [p for p in proc.stdout.split("\0") if p]


def _deps_non_empty(cargo_toml: Path) -> bool:
    """Cargo.toml 的 [dependencies] 是否非空（std-only crate 不需要跟进面）。"""
    text = cargo_toml.read_text(encoding="utf-8", errors="replace")
    in_deps = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_deps = line == "[dependencies]"
            continue
        if in_deps and line and not line.startswith("#"):
            return True
    return False


def expected_surfaces(root: Path = ROOT) -> list:
    """仓库里真实存在的「版本固定面」→ 期望的 (ecosystem, directory)。"""
    out = []
    files = tracked_files(root)
    if any(rel.startswith(".github/workflows/") for rel in files):
        out.append(("github-actions", "/"))
    if any(rel.startswith(".github/requirements-") for rel in files):
        out.append(("pip", "/.github"))
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        m = re.search(r"(?ms)^\[project\.optional-dependencies\].*?(?=^\[|\Z)", text)
        if m and "==" in m.group(0):
            out.append(("pip", "/"))
    if "packaging/npm/package.json" in files:
        out.append(("npm", "/packaging/npm"))
    for rel in files:
        if not rel.endswith("Cargo.toml") or not rel.startswith("engine/"):
            continue
        cargo = root / rel
        if _deps_non_empty(cargo):
            parent = cargo.parent.relative_to(root).as_posix()
            out.append(("cargo", "/" + parent))
    for rel in files:
        if rel.rsplit("/", 1)[-1] != "Dockerfile":
            continue
        parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
        out.append(("docker", "/" if not parent else "/" + parent))
    return sorted(set(out))


def config_issues(doc: dict, root: Path = ROOT, surfaces: list = None) -> list:
    """dependabot 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("version") != 2:
        issues.append(f"version 必须为 2，实际 {doc.get('version')!r}")
    updates = doc.get("updates") or []
    if not updates:
        return issues + ["updates 为空（没有任何跟进面）"]
    pairs = []
    for i, item in enumerate(updates):
        item = item or {}
        eco = str(item.get("package-ecosystem") or "").strip()
        directory = str(item.get("directory") or "").strip()
        if eco not in ECOSYSTEMS:
            issues.append(f"updates[{i}] 生态非法：{eco!r}")
        if not directory.startswith("/"):
            issues.append(f"updates[{i}] directory 必须根锚定（/ 开头）：{directory!r}")
        elif not (root / directory.lstrip("/")).is_dir():
            issues.append(f"updates[{i}] directory 不存在：{directory}")
        pairs.append((eco, directory))
        schedule = item.get("schedule") or {}
        if str(schedule.get("interval") or "") not in INTERVALS:
            issues.append(f"updates[{i}] schedule.interval 非法：{schedule.get('interval')!r}")
        limit = item.get("open-pull-requests-limit", 5)
        if not isinstance(limit, int) or not 1 <= limit <= 10:
            issues.append(f"updates[{i}] open-pull-requests-limit 必须 1..10：{limit!r}")
        labels = [str(x) for x in (item.get("labels") or [])]
        if "dependencies" not in labels:
            issues.append(f"updates[{i}] 缺 dependencies 标签")
        prefix = str((item.get("commit-message") or {}).get("prefix") or "").strip()
        if not prefix:
            issues.append(f"updates[{i}] 缺 commit-message.prefix")
        for name, group in (item.get("groups") or {}).items():
            group = group or {}
            types = {str(x) for x in (group.get("update-types") or [])}
            if not types:
                issues.append(f"updates[{i}] 分组 {name} 缺 update-types")
            bad = sorted(types - GROUP_TYPES)
            if bad:
                issues.append(f"updates[{i}] 分组 {name} 混入 major/非法类型：{bad}")
            applies = str(group.get("applies-to") or "").strip()
            if applies and applies not in ("version-updates", "security-updates"):
                issues.append(f"updates[{i}] 分组 {name} applies-to 非法：{applies!r}")
    for pair in sorted({p for p in pairs if pairs.count(p) > 1}):
        issues.append(f"重复的跟进面：{pair[0]} @ {pair[1]}")
    want = set(expected_surfaces(root) if surfaces is None else surfaces)
    got = set(pairs)
    missing = sorted(want - got)
    if missing:
        issues.append(f"版本固定面缺跟进：{missing}")
    return issues


class DependabotContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_config()

    def test_config_matches_contract(self):
        self.assertEqual([], config_issues(self.doc), "dependabot.yml 不满足契约")

    def test_all_pinned_surfaces_are_covered(self):
        """仓库里真实存在的版本固定面（actions/pip/npm/cargo/docker）必须全覆盖。"""
        want = set(expected_surfaces())
        got = {(str(u.get("package-ecosystem")), str(u.get("directory")))
               for u in (self.doc.get("updates") or [])}
        self.assertEqual(set(), want - got, f"缺跟进面：{sorted(want - got)}")

    def test_groups_never_swallow_major(self):
        """分组只收 minor/patch；major 必须单独进 PR（安全修复才能插队）。"""
        for i, item in enumerate(self.doc.get("updates") or []):
            for name, group in ((item or {}).get("groups") or {}).items():
                types = {str(x) for x in ((group or {}).get("update-types") or [])}
                self.assertEqual(set(), types - GROUP_TYPES,
                                 f"updates[{i}] 分组 {name} 混入 major")

    def test_contract_catches_broken_config(self):
        """变异自证：删 npm 面 / 非法节奏 / 不存在目录 / major 入组 / 重复面——都必须报。"""
        surfaces = expected_surfaces()
        no_npm = copy.deepcopy(self.doc)
        no_npm["updates"] = [u for u in no_npm["updates"]
                             if u.get("package-ecosystem") != "npm"]
        self.assertTrue(any("缺跟进" in i for i in config_issues(no_npm, surfaces=surfaces)),
                        "删掉 npm 面必须报")
        bad_interval = copy.deepcopy(self.doc)
        bad_interval["updates"][0]["schedule"]["interval"] = "sometimes"
        interval_issues = config_issues(bad_interval, surfaces=surfaces)
        self.assertTrue(any("interval" in i for i in interval_issues), "非法节奏必须报")
        bad_dir = copy.deepcopy(self.doc)
        bad_dir["updates"].append({"package-ecosystem": "npm", "directory": "/no_such_dir",
                                   "schedule": {"interval": "weekly"},
                                   "labels": ["dependencies"],
                                   "commit-message": {"prefix": "ci"}})
        self.assertTrue(any("不存在" in i for i in config_issues(bad_dir, surfaces=surfaces)),
                        "不存在目录必须报")
        major_group = copy.deepcopy(self.doc)
        major_group["updates"][0]["groups"]["bad"] = {"update-types": ["major"]}
        self.assertTrue(any("major" in i for i in config_issues(major_group, surfaces=surfaces)),
                        "major 入组必须报")
        dup = copy.deepcopy(self.doc)
        dup["updates"].append(copy.deepcopy(dup["updates"][0]))
        self.assertTrue(any("重复" in i for i in config_issues(dup, surfaces=surfaces)),
                        "重复跟进面必须报")
        with self.assertRaises(ValueError):
            load_config(ROOT / ".github" / "no_such_dependabot.yml")


if __name__ == "__main__":
    unittest.main()
