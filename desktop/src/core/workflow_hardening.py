"""工作流工业级加固判据（Python-only 面 · 2026-10-13 补）。

**为什么单独成件**：`core/workflow_policy.py` 是 `python scripts/verify_report.py` 的 **native 面**
（Rust 引擎 `engine/rust/src/workflow_policy.rs` 与其逐字节对账）；改它的问题/统计面就必须
同步移植到 Rust，否则跨语言对账当场红。本件守的是 **CI 运行面**（并发 / 凭据 / 缓存 / 评审路由 /
生态覆盖），不属于跨语言契约面——按仓库既有先例，新子判据挂到**喂入面**
（`core/quality_depth_scan.py` 由 `--results` 喂给快线，不参与其自算）。

五条判据（出处：GitHub Actions 官方 Control concurrency 与安全加固；`actions/checkout` 的
`persist-credentials` 默认 true；`actions/setup-python` caching；GitHub Docs
About code owners；Scorecard §Dependency-Update-Tool）：
1. 每件须显式 `concurrency:`；**写入型**（`contents: write` 或含 `git push`）必须
   `cancel-in-progress: false`（取消写者会留下半推送状态），且所有写入型**共享同一 group**
   ——本仓两个入库前端都会 `git push origin`，并发即写竞态。
2. 非写入型的 checkout 须显式 `persist-credentials: false`（否则 token 留在 `.git/config`）。
3. 凡真跑 `pip install` 的须声明 `cache: pip} + `cache-dependency-path`（注：见文末
   的写法说明——判据串是 cache 与 pip 的组合）。
4. `CODEOWNERS` 在场且含 `*` 兜底规则。
5. dependabot 覆盖仓库**真实**生态（按结构推断）：工作流 → github-actions；
   requirements-*.txt → pip；packaging/npm/package.json → npm。

纪律：纯标准库、只读、错误消息带修复指引。
"""
from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS_REL = ".github/workflows"
CONC_GROUP_RE = re.compile(r"^\s*group:\s*(\S.*?)\s*$", re.M)
CONC_CANCEL_RE = re.compile(r"^\s*cancel-in-progress:\s*(true|false)\s*$", re.M)
WRITER_PUSH = "git push"
CACHE_MARK = "cache:" + " pip"


def workflows(root: str = ".") -> list:
    """仓库内的工作流件（仓库相对、排序）。"""
    d = Path(root) / WORKFLOWS_REL
    if not d.is_dir():
        return []
    return sorted(f"{WORKFLOWS_REL}/{p.name}"
                  for p in d.iterdir() if p.suffix in (".yml", ".yaml"))


def is_writer(text: str) -> bool:
    """该工作流是否会写仓库（内容写权限，或真的 git push）。"""
    if re.search(r"^\s*contents:\s*write\s*$", text, re.M):
        return True
    return WRITER_PUSH in text


def _concurrency_issues(rel: str, text: str) -> tuple:
    """判据 1 → (issues, 写入型并发组名；非写者返回空串)。"""
    writer = is_writer(text)
    if not re.search(r"^concurrency:", text, re.M):
        hint = ("group: ${ github.workflow }-${ github.ref } + cancel-in-progress: true；"
                "写入型用固定组 + false")
        return ([rel + " 缺 concurrency 并发分组（修复指引：push/PR 型用 " + hint + "）"],
                "?" if writer else "")
    out: list = []
    m = CONC_CANCEL_RE.search(text)
    cancel = m.group(1) if m else ""
    g = CONC_GROUP_RE.search(text)
    group = g.group(1).strip() if g else ""
    if not cancel:
        out.append(f"{rel} 的 concurrency 缺 cancel-in-progress（修复指引：显式 true/false，"
                   f"不要留给默认）")
    if writer and cancel != "false":
        out.append(f"{rel} 是写入型工作流（contents: write / git push）却允许取消并发运行"
                   f"（修复指引：cancel-in-progress: false——取消写者会留下半推送状态）")
    if writer and not group:
        out.append(f"{rel} 是写入型工作流但 concurrency 缺 group（修复指引：给固定组名，"
                   f"与其它写者共享）")
    return out, (group if writer else "")


def _credential_issues(rel: str, text: str, writer: bool) -> list:
    """判据 2：非写入型的 checkout 不得持久化凭据。"""
    if writer or "actions/checkout@" not in text:
        return []
    if "persist-credentials" in text:
        return []
    return [f"{rel} 的 checkout 未关凭据持久化（修复指引：with 下加 persist-credentials: false"
            f"——actions/checkout 默认把 GITHUB_TOKEN 写进 .git/config，后续步骤都能读到）"]


def _cache_issues(rel: str, text: str) -> list:
    """判据 3：真跑 pip install 的须声明依赖缓存。"""
    if not re.search(r"\bpip install\b", text):
        return []
    if CACHE_MARK in text and "cache-dependency-path" in text:
        return []
    return [f"{rel} 有 pip 安装但未声明依赖缓存（修复指引：actions/setup-python 的 with 下加 "
            f"cache: pip 与 cache-dependency-path: .github/requirements-*.txt）"]


def _codeowners_issues(root: str) -> list:
    """判据 4：评审路由须可见。"""
    for rel in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        p = Path(root) / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\*\s+\S", text, re.M):
            return []
        return [f"{rel} 缺 * 兜底规则（修复指引：至少一行 * <owner>，否则未列出的文件没有属主）"]
    return ["缺 CODEOWNERS（修复指引：.github/CODEOWNERS 至少一行 * <owner>——"
            "GitHub Docs About code owners / Scorecard §Code-Review 要求评审路由可核）"]


def _dependabot_issues(root: str) -> tuple:
    """判据 5 → (issues, 已覆盖生态清单)。"""
    p = Path(root) / ".github" / "dependabot.yml"
    if not p.is_file():
        return (["缺 .github/dependabot.yml（修复指引：固定 SHA/版本后必须有自动跟进，"
                 "否则等于冻结上游安全修复——Scorecard §Dependency-Update-Tool）"], [])
    text = p.read_text(encoding="utf-8", errors="replace")
    have = set(re.findall(r"package-ecosystem:\s*([A-Za-z-]+)", text))
    need = set()
    if workflows(root):
        need.add("github-actions")
    if list((Path(root) / ".github").glob("requirements-*.txt")):
        need.add("pip")
    if (Path(root) / "packaging" / "npm" / "package.json").is_file():
        need.add("npm")
    missing = sorted(need - have)
    if missing:
        return ([f".github/dependabot.yml 未覆盖仓库真实生态：{'/'.join(missing)}"
                 f"（修复指引：按存在的清单补 package-ecosystem 条目——本仓同时有 workflow / "
                 f"requirements-*.txt / packaging/npm）"], sorted(have))
    return ([], sorted(have))


def scan(root: str = ".") -> tuple:
    """→ (issues, stats)：五条 CI 运行面加固判据。"""
    issues: list = []
    files = workflows(root)
    writer_groups: dict = {}
    with_conc = 0
    writers = 0
    for rel in files:
        text = (Path(root) / rel).read_text(encoding="utf-8", errors="replace")
        w = is_writer(text)
        if w:
            writers += 1
        c_iss, group = _concurrency_issues(rel, text)
        issues += c_iss
        if re.search(r"^concurrency:", text, re.M):
            with_conc += 1
        if group and group != "?":
            writer_groups.setdefault(group, []).append(rel)
        issues += _credential_issues(rel, text, w)
        issues += _cache_issues(rel, text)
    if len(writer_groups) > 1:
        joined = " / ".join(f"{g}:{','.join(v)}" for g, v in sorted(writer_groups.items()))
        issues.append(f"写入型工作流未共享同一并发组（{joined}）——它们会并发 push 同一分支"
                      f"（修复指引：统一 group 名，如 library-write）")
    issues += _codeowners_issues(root)
    dep_iss, ecosystems = _dependabot_issues(root)
    issues += dep_iss
    stats: dict = {"workflows": len(files), "with_concurrency": with_conc,
                   "writer_workflows": writers, "writers_share_group": len(writer_groups) <= 1,
                   "dependabot_ecosystems": ecosystems}
    return issues, stats
