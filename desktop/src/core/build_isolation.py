"""构建隔离体检（SLSA L3 —— Build isolation）：构建入口不联网 / 基座按 digest 钉 / 工具链定版。

为什么补（设计文档 §3.2 能力空洞 P0）：本仓此前只有「产物能否复现」（check25/31/40）的判据，
没有「**构建期读面是否被宿主污染**」的判据——同一份源码在联网机器上可能装配出不同产物，
而门禁对此完全沉默。SLSA L3 要求构建期无网络、只读源、工具链固定；本模块把这三条做成
**静态可判**的判据，全部可变异置红（见 tests/test_gate_41_42.py）。

判据（三条，任一为红即 FAIL）：

1. **入口无网络**：构建入口（`packaging/npm/tools/*.mjs`、`packaging/npm/package.json`）
   不得出现取网/取包命令——取包发生在**构建期**，产物就不可复现。
   注意 `packaging/npm/bin/*.mjs` **不在面内**：它是发布后的运行时壳（帮助文案里写着
   "git clone" 提示），把它算成构建入口会制造假红——判据只认真正跑构建的件；
2. **基座按 digest 钉**：`Dockerfile*` 的镜像引用必须带 `@sha256:`；`:latest` 与裸 tag 一律拒；
3. **工具链定版**：`packaging/npm/package.json` 声明 `engines.node`、`engine/rust/Cargo.lock`
   在场、CI 里 setup-python / setup-node 必须给**具体版本号**（不许浮动 major / 只给版本文件）。

边界：本模块只报**读面事实**，不判定「这样够不够 SLSA L3」——等级声明归 docs/CHANGELOG，
判据只管「可证的三条有没有做到」。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

#: 构建期取网/取包命令（命中即污染产物来源）。刻意收窄：只认**命令式**写法，
#: 避免把文档/注释里的 "npm install" 说明误判成构建动作。
NETWORK_TOKENS = (
    "curl ", "wget ", "git clone", "npm install", "npm ci", "pnpm add", "pip install",
    "fetch(", "https.request", "http.request", "https.get", "net.connect",
)
ENTRY_GLOBS = ("packaging/npm/tools/*.mjs", "packaging/npm/package.json")
DOCKER_GLOBS = ("Dockerfile", "Dockerfile.*")
#: 允许的镜像引用形态：registry/name[:tag]@sha256:<64 hex>（tag 可有可无，digest 必须有）
_DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}$")
_SETUP_RE = re.compile(r"uses:\s*actions/(setup-python|setup-node)@")


def _rel(r: Path, p: Path) -> str:
    try:
        return p.relative_to(r).as_posix()
    except ValueError:
        return p.as_posix()


def entry_files(root: Path) -> list[Path]:
    """构建入口文件清单（按路径排序）——缺失的 glob 只是不进面。"""
    out: list[Path] = []
    for pattern in ENTRY_GLOBS:
        out.extend(sorted(p for p in root.glob(pattern) if p.is_file()))
    return out


def network_hits(paths: list[Path]) -> list[str]:
    """→ ["文件: 命中词"]；读不动/解码失败的件跳过（其存在性由别的判据管）。"""
    hits: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for token in NETWORK_TOKENS:
            if token in text:
                hits.append("%s: %s" % (path.name, token.strip()))
    return hits


def base_image_issues(root: Path) -> tuple[list[str], int]:
    """容器基座 → (issues, 镜像引用数)。变量化 FROM 由同名 ARG 的取值判定。"""
    issues: list[str] = []
    seen = 0
    for dockerfile in sorted({p for pattern in DOCKER_GLOBS for p in root.glob(pattern)
                              if p.is_file()}):
        try:
            text = dockerfile.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            issues.append("%s 不可读（修复指引：确认该构建件可读，或从构建面移除）"
                          % dockerfile.name)
            continue
        args = dict(re.findall(r"(?m)^ARG\s+([A-Za-z_][A-Za-z0-9_]*)=(\S+)", text))
        for line in text.splitlines():
            m = re.match(r"(?m)^FROM\s+(\S+)", line)
            if not m:
                continue
            ref = m.group(1)
            var = re.fullmatch(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", ref)
            if var:
                ref = args.get(var.group(1), "")
                if not ref:
                    issues.append("%s：FROM 引用了未声明的构建变量 %s（修复指引：用 ARG 声明"
                                  "带 @sha256 的镜像）" % (dockerfile.name, m.group(1)))
                    continue
            seen += 1
            if ":latest" in ref or not _DIGEST_RE.search(ref.split(" AS ")[0].strip()):
                issues.append("%s：基座 %s 未按 digest 钉（修复指引：改成 name:tag@sha256:<64hex>；"
                              ":latest 一律拒）" % (dockerfile.name, ref))
    return issues, seen


def toolchain_issues(root: Path) -> list[str]:
    """工具链定版：node engines / Cargo.lock / CI 版本号。"""
    issues: list[str] = []
    pkg = root / "packaging" / "npm" / "package.json"
    if not pkg.is_file():
        issues.append("缺 packaging/npm/package.json（修复指引：构建入口必须声明自身依赖面）")
    else:
        try:
            doc = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
        engines = (doc.get("engines") if isinstance(doc, dict) else {}) or {}
        if not str(engines.get("node") or "").strip():
            issues.append("packaging/npm/package.json 未声明 engines.node（修复指引：写明支持的"
                          " node 版本范围，构建期工具链才可固定）")
    if not (root / "engine" / "rust" / "Cargo.lock").is_file():
        issues.append("缺 engine/rust/Cargo.lock（修复指引：锁文件是依赖定版的证据，必须入仓）")
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        for wf in sorted(workflows.glob("*.yml")):
            try:
                text = wf.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for kind in ("python", "node"):
                if not re.search(r"uses:\s*actions/setup-\s*%s@" % kind, text):
                    continue
                if not re.search(r"(?m)^\s*%s-version:\s*'?\d+\.\d+" % kind, text):
                    issues.append(".github/workflows/%s：setup-%s 未给具体版本号（修复指引：写"
                                  " python-version/node-version 的 X.Y，不留浮动 major）"
                                  % (wf.name, kind))
    return issues


def scan(root: str = ".") -> tuple[list[str], dict[str, object]]:
    """→ (issues, stats)；issues 空 = 三条判据全过。"""
    r = Path(root)
    issues: list[str] = []
    entries = entry_files(r)
    if not entries:
        issues.append("找不到构建入口（packaging/npm/tools/*.mjs 与 package.json）"
                      "（修复指引：确认构建面在场，或把新构建入口登记到 ENTRY_GLOBS）")
    hits = network_hits(entries)
    if hits:
        issues.append("构建入口出现取网/取包命令：%s（修复指引：构建期只读仓内既有件；确需联网的"
                      "步骤拆到发布编排，别放进构建入口）" % ", ".join(hits[:4]))
    image_issues, images = base_image_issues(r)
    issues.extend(image_issues)
    issues.extend(toolchain_issues(r))
    stats = {"entry_files": len(entries), "base_images": images,
             "network_hits": len(hits)}
    return issues, stats
