"""仓库信任判定（H1）：`nf verify` 会执行目标仓库自带的门禁脚本，跨信任边界。

## 问题（2026-10-22 安全审计 H1）

`nf verify` 的引擎侧会对目标仓库 `verify.sh` 里的 heredoc Python 做 `exec(compile(...))`
（`core/gate_inproc.py`）——也就是说：**在谁的仓库里跑 `nf verify`，就执行谁的代码**。
用户 `cd` 进一个不可信仓库（或别人发来的包）后跑本命令，那个仓库就能读 `~/.ssh`、写盘、
外传（CWE-94/95；OWASP A03:2021 – Injection；ASVS V5.2.1「不得对不可信数据求值」）。

## 信任模型（fail-closed）

- **只有当前运行代码所在的安装根自动可信**；外部仓库伪造官方 `origin` 仍不可信；
- 否则（无 origin / 非 git 检出 / 非 GitHub 形态 / owner 无显式 opt-in）⇒ **不可信**：
  `nf verify` 默认拒绝执行 inproc，需显式 `--trust-repo`（等价 `NF_TRUST_REPO=1`）；
- `NF_TRUST_OWNERS`（逗号分隔）是外部仓库 owner 的**显式 opt-in**（fork CI / 自建镜像用）；
- 判定只读；判不出就是不可信，不猜。

## 实现口径

**直接读 `.git/config`**（不跑 git 子进程）：本模块是信任门的最底层，越少外部执行面越好；
同时天然支持 linked worktree（`.git` 是 `gitdir:` 指针文件 → 经 `commondir` 找到共享 config）。
`include.path` 等高级形态不解析——判不出 origin 即不可信（fail-closed），符合本模块语义。

## 边界

只用标准库；不 import core.*（叶子件，避免与门禁链互相牵制）；不写盘、无网络。
"""
from __future__ import annotations

import configparser
import os
import re
from pathlib import Path

#: 显式放行开关（`nf verify --trust-repo` 会置位）。
ENV_TRUST = "NF_TRUST_REPO"
#: 可追加的允许 owner（逗号分隔；默认白名单之外的自建镜像/fork CI 用）。
ENV_OWNERS = "NF_TRUST_OWNERS"
#: 默认允许的 origin owner（本仓作者）。**只增不减**须评审：每条都是「允许执行谁的代码」。
ALLOWED_OWNERS = frozenset({"Monyeah777"})
INSTALL_ROOT = Path(__file__).resolve().parents[3]

#: GitHub 仓库 URL 形态：`https://github.com/<owner>/<repo>`、`git@github.com:<owner>/<repo>`
#: `ssh://git@github.com/<owner>/<repo>`（`.git` 后缀可选）。只认 GitHub——其它托管不猜。
_OWNER = r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)"
_REPO = r"(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?"
_GH_WEB = re.compile(rf"^https?://github\.com/{_OWNER}/{_REPO}/?$", re.I)
_GH_SSH = re.compile(rf"^ssh://git@github\.com(?::\d+)?/{_OWNER}/{_REPO}/?$", re.I)
_GH_SCP = re.compile(rf"^git@github\.com:{_OWNER}/{_REPO}$", re.I)


class UntrustedRepoError(RuntimeError):
    """目标仓库不可信，拒绝在进程内执行它自带的代码（H1）。"""


def _git_config_path(root: str) -> Path | None:
    """目标仓库的**共享 git config** 路径（linked worktree 走 gitdir→commondir）；判不出 → None。"""
    dotgit = Path(root) / ".git"
    try:
        if dotgit.is_dir():
            return dotgit / "config"
        if not dotgit.is_file():
            return None                          # 非 git 检出（含 npm payload 解包树）⇒ 不可信
        pointer = dotgit.read_text(encoding="utf-8", errors="replace").strip()
        if not pointer.startswith("gitdir:"):
            return None
        gitdir = Path(pointer.split(":", 1)[1].strip())
        if not gitdir.is_absolute():
            gitdir = (Path(root) / gitdir).resolve()
        common = gitdir / "commondir"
        if common.is_file():
            rel = common.read_text(encoding="utf-8", errors="replace").strip()
            gitdir = (gitdir / rel).resolve()
        return gitdir / "config"
    except OSError:
        return None


def origin_url(root: str) -> str | None:
    """目标仓库 `origin` 的 URL（无 origin / 非 git 检出 / 配置不可读 ⇒ None）。"""
    cfg = _git_config_path(root)
    if cfg is None or not cfg.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(str(cfg), encoding="utf-8")
    except (OSError, configparser.Error):
        return None
    try:
        url = parser.get('remote "origin"', "url", fallback="").strip()
    except configparser.Error:
        return None
    return url or None


def origin_owner(root: str) -> str | None:
    """从 origin URL 解析 GitHub owner（形态不认识 ⇒ None，不猜）。"""
    url = origin_url(root)
    if not url:
        return None
    m = _GH_WEB.fullmatch(url) or _GH_SSH.fullmatch(url) or _GH_SCP.fullmatch(url)
    return m.group("owner") if m else None


def allowed_owners() -> frozenset:
    """允许的 owner 集合（默认白名单 + `NF_TRUST_OWNERS` 追加；空项忽略）。"""
    extra = {x.strip() for x in (os.environ.get(ENV_OWNERS) or "").split(",") if x.strip()}
    return ALLOWED_OWNERS | extra


def trust_status(root: str) -> tuple:
    """→ (是否可信, 理由)。**任何判不出的情形都返回不可信**（fail-closed）。"""
    if os.path.normcase(os.path.realpath(root)) == os.path.normcase(str(INSTALL_ROOT)):
        return True, f"目标仓库就是当前运行代码的安装根（{INSTALL_ROOT}）"
    if os.environ.get(ENV_TRUST) == "1":
        return True, f"显式放行（{ENV_TRUST}=1，用户自担风险）"
    owner = origin_owner(root)
    explicit = frozenset(x.strip() for x in (os.environ.get(ENV_OWNERS) or "").split(",")
                         if x.strip())
    if owner and owner in explicit:
        return True, f"origin owner={owner} 经 {ENV_OWNERS} 显式放行（用户自担风险）"
    if owner:
        return False, (f"origin owner={owner!r} 不构成自动信任；外部仓库须显式设置 "
                       f"{ENV_OWNERS} 或使用 --trust-repo")
    return False, "无法判定 origin owner（无 origin / 非 git 检出 / 非 GitHub 形态；须显式信任）"


def refusal_message(root: str, reason: str = "") -> str:
    """拒绝执行时的**对外文案**：讲清风险 + 给可执行的修复指引（供 CLI 与引擎共用）。"""
    ok, why = trust_status(root)
    if ok:
        return ""
    return (
        f"拒绝在目标仓库内执行门禁脚本（H1/CWE-94）：{reason or why}。"
        "该仓库不可信——`nf verify` 会把目标仓库 verify.sh 内嵌的 Python 当作**本机进程代码**"
        "执行（可读家目录/写盘/外传），故此面默认关闭。修复指引：仅当你信任该仓库时显式加 "
        "`nf verify --trust-repo`（或 NF_TRUST_REPO=1），风险自担；自建镜像/fork CI 可把 owner "
        "加进 NF_TRUST_OWNERS。不可信仓库请先人工审阅其 verify.sh，或只用 `bash verify.sh` "
        "前的静态面（不要经 nf verify 执行）。"
    )


def assert_trusted(root: str) -> None:
    """不信任即抛 `UntrustedRepoError`（gate_inproc 的纵深防御入口）。"""
    ok, why = trust_status(root)
    if not ok:
        raise UntrustedRepoError(refusal_message(root, why))


__all__ = ["ALLOWED_OWNERS", "ENV_OWNERS", "ENV_TRUST", "UntrustedRepoError",
           "allowed_owners", "assert_trusted", "origin_owner", "origin_url",
           "refusal_message", "trust_status"]
