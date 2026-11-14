"""全仓代码质量审查 CQ0/CQ1（NF-Final §13B，WP-0H）：工具固定 + 全量自动扫描 + 基线/热点。

为什么（§13B.8）：CQ 不是「跑一次 lint」——先把**工具与版本固定**（本机可用/缺失都如实记），
再做**全量自动扫描**（全语言：Python 语法、JSON/YAML/Shell、ruff/bandit/radon/vulture），
产出可复算的扫描件与热点，并把发现分诊成 P0/P1/P2 清单。

契约口径（与仓库既有棘轮不冲突）：
- 本模块只**汇总**，不替代既有门禁（verify check12/27/34/35 等）；CQ 是额外纵深；
- 缺失工具（如 cosign/gitleaks）→ `status=blocked`，**不得**写成通过；
- 产物：`results/cq/toolchain.json`、`results/cq/scan.json`、`results/cq/findings.jsonl`、
  `results/cq/hotspots.md`；`docs/CQ_REPORT.md` + `docs/QUALITY_DEBT.md` 人读面；
- 新鲜度：`check()` 比对「HEAD + 工作树状态 + 工具版本」指纹（不重跑全量扫描），
  树/工具一变即要求 `--run` 重算——不把旧报告当新结论。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOLCHAIN_SCHEMA = "nf-cq-toolchain/1"
SCAN_SCHEMA = "nf-cq-scan/1"
DIR_REL = "results/cq"
TOOLCHAIN_REL = DIR_REL + "/toolchain.json"
SCAN_REL = DIR_REL + "/scan.json"
FINDINGS_REL = DIR_REL + "/findings.jsonl"
HOTSPOTS_REL = DIR_REL + "/hotspots.md"
GUIDE = "修复指引："
SEVERITIES = ("P0", "P1", "P2", "P3")
DIMS = ("syntax-python", "json-parse", "shell-syntax", "yaml-parse", "ruff", "bandit",
        "radon-cc", "vulture", "claims-words")
#: id → (命令, 必需?, 说明)
TOOLS: Tuple[Tuple[str, Tuple[str, ...], bool, str], ...] = (
    ("python", ("python", "--version"), True, "运行时/语法扫描"),
    ("ruff", ("ruff", "--version"), True, "Python lint（钉版本）"),
    ("bandit", ("bandit", "--version"), True, "Python 安全 sink（SAST）"),
    ("radon", ("radon", "--version"), True, "复杂度/可维护性指标"),
    ("mypy", ("mypy", "--version"), True, "类型检查（新增收缩）"),
    ("coverage", ("coverage", "--version"), True, "覆盖率（行/分支）"),
    ("vulture", ("vulture", "--version"), True, "死代码/未使用"),
    ("shellcheck", ("shellcheck", "--version"), True, "Shell 静态检查"),
    ("node", ("node", "--version"), False, "跨语言实现/工具链"),
    ("cargo", ("cargo", "--version"), False, "Rust 引擎"),
    ("dotnet", ("dotnet", "--version"), False, ".NET 引擎"),
    ("cosign", ("cosign", "version"), True, "外部签名锚（缺失=BLOCKED，不冒充）"),
    ("gitleaks", ("gitleaks", "version"), True, "秘密扫描（缺失=BLOCKED，不冒充）"),
)
NEGATION = ("不", "非", "无", "未", "≠", "禁止", "不得")
FORBIDDEN_WORDS = ("不可抵赖", "合规", "认证")
#: 同形异义的技术词（不是监管声明）：schema 合规/格式合规/组合规则/摘要认证/合规率…
BENIGN_PHRASES = ("组合规则", "schema 合规", "格式合规", "合规率", "合规台",
                  "摘要/认证", "遵从认证", "合规审核", "（合规）", "合规模板")


def _run(cmd: List[str], timeout: int = 180, cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, cwd=cwd)
        return {"rc": proc.returncode, "out": proc.stdout or "", "err": proc.stderr or ""}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"rc": None, "out": "", "err": "%s: %s" % (type(exc).__name__, str(exc)[:160])}


def _tracked(root: str) -> List[str]:
    res = _run(["git", "-c", "core.quotepath=false", "ls-files"], cwd=root)
    if res["rc"] != 0:
        return []
    return [line for line in res["out"].splitlines() if line.strip()]


def toolchain(root: str = ".") -> Dict[str, Any]:
    """工具矩阵：present/version/status；缺失或不可用 → blocked（不冒充）。"""
    entries: List[Dict[str, Any]] = []
    for tid, cmd, required, why in TOOLS:
        exe = shutil.which(cmd[0])
        entry = {"id": tid, "cmd": " ".join(cmd), "required": required, "why": why,
                 "present": bool(exe), "version": "", "status": "ok", "blocked_reason": ""}
        if not exe:
            entry["status"] = "blocked"
            entry["blocked_reason"] = "工具不在场（缺失=BLOCKED，不写成通过）"
        else:
            res = _run(list(cmd), timeout=30, cwd=root)
            text = (res["out"] or res["err"]).strip().splitlines()
            entry["version"] = text[0][:120] if text else ""
            if res["rc"] not in (0,):
                entry["status"] = "blocked"
                entry["blocked_reason"] = "命令不可用：%s" % (entry["version"] or res["err"][:80])
        entries.append(entry)
    return {"schema": TOOLCHAIN_SCHEMA, "tools": entries,
            "blocked": [e["id"] for e in entries if e["status"] != "ok"],
            "note": "工具版本固定后记录；缺失/不可用一律 blocked，不冒充通过"}


def _finding(dim: str, severity: str, message: str, file: str = "", line: int = 0,
             fix: str = "") -> Dict[str, Any]:
    return {"dim": dim, "severity": severity, "message": message, "file": file,
            "line": line, "fix": fix, "owner": "maintainers", "status": "open"}


def _scan_syntax(root: str, files: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    findings = []
    py = [f for f in files if f.endswith(".py")]
    for rel in py:
        try:
            source = (Path(root) / rel).read_bytes()
            compile(source, rel, "exec")
        except SyntaxError as exc:
            findings.append(_finding("syntax-python", "P0",
                                     "语法错误：%s" % exc.msg, rel, exc.lineno or 0,
                                     "修语法后重跑"))
        except OSError as exc:
            findings.append(_finding("syntax-python", "P1", "读不出：%s" % exc, rel, 0))
    return {"files": len(py), "issues": len(findings)}, findings


def _scan_json(root: str, files: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    findings = []
    js = [f for f in files if f.endswith(".json")]
    for rel in js:
        try:
            json.loads((Path(root) / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            findings.append(_finding("json-parse", "P0", "JSON 不可解析：%s" % exc, rel, 0,
                                     "修 JSON 后重跑"))
    return {"files": len(js), "issues": len(findings)}, findings


def _scan_shell(root: str, files: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    findings = []
    sh = [f for f in files if f.endswith(".sh")]
    for rel in sh:
        res = _run(["bash", "-n", str(Path(root) / rel)], timeout=30, cwd=root)
        if res["rc"] not in (0, None):
            findings.append(_finding("shell-syntax", "P0", "shell 语法错误：%s"
                                     % (res["err"].strip().splitlines()[-1:] or [""])[0],
                                     rel, 0, "bash -n 修语法"))
    return {"files": len(sh), "issues": len(findings)}, findings


def _scan_yaml(root: str, files: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    findings = []
    yml = [f for f in files if f.endswith((".yaml", ".yml"))]
    try:
        import yaml  # noqa: F401 - 软依赖：缺失记 blocked 语义
    except Exception:
        return {"files": len(yml), "issues": 0, "status": "blocked",
                "blocked_reason": "PyYAML 不在场"}, findings
    for rel in yml:
        try:
            yaml.safe_load((Path(root) / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            findings.append(_finding("yaml-parse", "P0", "YAML 不可解析：%s" % exc, rel, 0))
    return {"files": len(yml), "issues": len(findings)}, findings


def _scan_ruff(root: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not shutil.which("ruff"):
        return {"status": "blocked", "blocked_reason": "ruff 不在场", "issues": 0}, []
    res = _run(["ruff", "check", "desktop/src/core", "scripts",
                "--output-format=concise"], timeout=180, cwd=root)
    lines = [ln for ln in (res["out"] or "").splitlines()
             if ln.strip() and not ln.startswith(("Found ", "All checks passed"))]
    findings = [_finding("ruff", "P2", ln.strip()[:200], ln.split(":", 1)[0], 0,
                         "ruff check --fix 或人工修") for ln in lines[:200]]
    return {"files": 2, "issues": len(lines)}, findings


def _scan_bandit(root: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not shutil.which("bandit"):
        return {"status": "blocked", "blocked_reason": "bandit 不在场", "issues": 0}, []
    res = _run(["bandit", "-q", "-r", "desktop/src/core", "-f", "json"], timeout=300, cwd=root)
    try:
        doc = json.loads(res["out"] or "{}")
    except ValueError:
        return {"status": "blocked", "blocked_reason": "bandit 输出不可解析", "issues": 0}, []
    rows = doc.get("results") or []
    counts = {"high": 0, "medium": 0, "low": 0}
    findings = []
    for row in rows:
        sev = str(row.get("issue_severity", "")).lower()
        if sev in counts:
            counts[sev] += 1
        level = {"high": "P1", "medium": "P2", "low": "P3"}.get(sev, "P3")
        findings.append(_finding("bandit", level,
                                 "%s %s" % (row.get("test_id"), row.get("issue_text", "")[:160]),
                                 str(row.get("filename")), int(row.get("line_number") or 0),
                                 "按 bandit 报告人工复核/修"))
    return {"files": 1, "issues": len(rows), "severity_counts": counts}, findings


def _scan_radon(root: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not shutil.which("radon"):
        return {"status": "blocked", "blocked_reason": "radon 不在场", "issues": 0}, []
    res = _run(["radon", "cc", "desktop/src/core", "-s", "-j"], timeout=180, cwd=root)
    try:
        doc = json.loads(res["out"] or "{}")
    except ValueError:
        return {"status": "blocked", "blocked_reason": "radon 输出不可解析", "issues": 0}, []
    max_cc = 0
    over = 0
    hotspots = []
    for path, blocks in doc.items():
        for block in blocks or []:
            cc = int(block.get("complexity") or 0)
            max_cc = max(max_cc, cc)
            if cc > 15:
                over += 1
            if cc >= 20:
                hotspots.append({"file": path, "name": block.get("name"),
                                 "complexity": cc, "lineno": block.get("lineno")})
    hotspots.sort(key=lambda x: (-x["complexity"], x["file"]))
    findings = [_finding("radon-cc", "P2", "函数 CC=%s 超阈值 15" % h["complexity"],
                         h["file"], int(h["lineno"] or 0), "拆分/降低复杂度") for h in hotspots[:50]]
    return {"files": len(doc), "issues": over, "max_cc": max_cc,
            "cc_gt15": over, "hotspots": hotspots[:20]}, findings


def _scan_vulture(root: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not shutil.which("vulture"):
        return {"status": "blocked", "blocked_reason": "vulture 不在场", "issues": 0}, []
    res = _run(["vulture", "desktop/src/core", "--min-confidence", "80"], timeout=180, cwd=root)
    lines = [ln for ln in (res["out"] or "").splitlines() if ln.strip()]
    findings = [_finding("vulture", "P3", ln.strip()[:200],
                         ln.split(":", 1)[0].strip(), 0, "人工确认后删/加白") for ln in lines[:200]]
    return {"files": 1, "issues": len(lines)}, findings


def _scan_claims(root: str, files: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    targets = [f for f in files if f == "README.md" or f.startswith("docs/")
               and f.endswith(".md") and f.count("/") == 1]
    findings = []
    for rel in targets:
        try:
            text = (Path(root) / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(p in line for p in BENIGN_PHRASES):
                continue
            for word in FORBIDDEN_WORDS:
                if word in line and not any(m in line for m in NEGATION):
                    findings.append(_finding("claims-words", "P2",
                                             "疑似过度声明：%s" % word, rel, lineno,
                                             "改否定语境或删除声明"))
    return {"files": len(targets), "issues": len(findings)}, findings


SCANNERS = (("syntax-python", _scan_syntax), ("json-parse", _scan_json),
            ("shell-syntax", _scan_shell), ("yaml-parse", _scan_yaml),
            ("ruff", lambda root, files: _scan_ruff(root)),
            ("bandit", lambda root, files: _scan_bandit(root)),
            ("radon-cc", lambda root, files: _scan_radon(root)),
            ("vulture", lambda root, files: _scan_vulture(root)),
            ("claims-words", _scan_claims))


def _fingerprint(root: str, tc: Dict[str, Any]) -> str:
    """指纹 = 被扫输入件内容（tracked，排除本目录产物）+ 工具版本。

    为什么不用 HEAD/工作树状态：产物自身写盘/入库会改状态，导致「刚算完即过期」死循环；
    内容哈希在 commit 前后不变（commit 不改文件内容），只在输入件或工具版本变化时失效。
    """
    digest = hashlib.sha256()
    for rel in _tracked(root):
        if rel.startswith(DIR_REL + "/"):
            continue
        try:
            data = (Path(root) / rel).read_bytes()
        except OSError:
            data = b""
        digest.update(rel.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(hashlib.sha256(data).digest())
    versions = "|".join("%s=%s" % (e["id"], e["version"]) for e in tc.get("tools") or [])
    digest.update(("|" + versions + "|" + ",".join(DIMS)).encode("utf-8"))
    return digest.hexdigest()


def build(root: str = ".") -> Dict[str, Any]:
    """跑全量自动扫描 → (toolchain, scan)。"""
    tc = toolchain(root)
    files = _tracked(root)
    dims: Dict[str, Any] = {}
    findings: List[Dict[str, Any]] = []
    hotspots: List[Dict[str, Any]] = []
    for dim, fn in SCANNERS:
        stats, got = fn(root, files)
        dims[dim] = stats
        for item in got:
            item["id"] = "F-%03d" % (len(findings) + 1)
            findings.append(item)
        if dim == "radon-cc":
            hotspots = stats.get("hotspots") or []
    p0 = [f for f in findings if f["severity"] == "P0"]
    p1 = [f for f in findings if f["severity"] == "P1"]
    scan = {"schema": SCAN_SCHEMA, "fingerprint": _fingerprint(root, tc),
            "toolchain_fingerprint": tc.get("blocked"),
            "dimensions": dims, "findings_counts":
                {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES},
            "p0": len(p0), "findings": findings, "hotspots": hotspots,
            "note": "全量自动扫描（CQ1）；缺失工具记 blocked，不冒充通过；P0/P1 进整改"}
    return tc, scan


def artifact_issues(tc: Dict[str, Any], scan: Dict[str, Any]) -> List[str]:
    """扫描件结构判据（供测试/变异自证复用；不重跑扫描）。"""
    issues: List[str] = []
    if str(tc.get("schema")) != TOOLCHAIN_SCHEMA:
        issues.append("toolchain schema 不匹配")
    tools = tc.get("tools") or []
    if len(tools) < len(TOOLS):
        issues.append("toolchain 工具数少于登记矩阵（%d < %d）" % (len(tools), len(TOOLS)))
    for entry in tools:
        if not isinstance(entry, dict) or not str(entry.get("id")):
            issues.append("toolchain 含无效条目")
            continue
        if str(entry.get("status")) not in ("ok", "blocked"):
            issues.append("%s 的 status 非法：%s" % (entry.get("id"), entry.get("status")))
        if entry.get("status") == "blocked" and not str(entry.get("blocked_reason") or "").strip():
            issues.append("%s blocked 但缺理由" % entry.get("id"))
        if entry.get("status") == "ok" and not str(entry.get("version") or "").strip():
            issues.append("%s ok 但缺版本（工具版本必须固定记录）" % entry.get("id"))
    blocked = tc.get("blocked") or []
    if blocked != [e["id"] for e in tools if e.get("status") != "ok"]:
        issues.append("blocked 列表与工具状态不一致（缺失=BLOCKED，不冒充通过）")
    if str(scan.get("schema")) != SCAN_SCHEMA:
        issues.append("scan schema 不匹配")
    fp = str(scan.get("fingerprint") or "")
    if len(fp) != 64:
        issues.append("scan.fingerprint 必须是 64 位 sha256")
    dims = scan.get("dimensions") or {}
    for dim in DIMS:
        if dim not in dims:
            issues.append("缺扫描维度：%s" % dim)
    findings = scan.get("findings") or []
    for item in findings:
        if str(item.get("severity")) not in SEVERITIES:
            issues.append("findings 含非法 severity：%s" % item.get("severity"))
            break
        if not str(item.get("dim")) or not str(item.get("owner")) or not str(item.get("status")):
            issues.append("finding %s 缺 dim/owner/status" % item.get("id"))
            break
    counts = scan.get("findings_counts") or {}
    for sev in SEVERITIES:
        want = sum(1 for f in findings if f.get("severity") == sev)
        if counts.get(sev) != want:
            issues.append("%s 计数不一致（记录 %s / 实际 %s）" % (sev, counts.get(sev), want))
    hotspots = scan.get("hotspots") or []
    if any(int(h.get("complexity") or 0) < int(hotspots[i + 1].get("complexity") or 0)
           for i, h in enumerate(hotspots[:-1])):
        issues.append("hotspots 未按复杂度降序")
    return issues


def render_json(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_findings(findings: List[Dict[str, Any]]) -> str:
    return "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n"
                   for f in findings)


def render_hotspots(scan: Dict[str, Any]) -> str:
    rows = scan.get("hotspots") or []
    lines = ["# CQ 热点（复杂度 top）", "",
             "> 由 `python scripts/cq_scan.py --run` 生成；radon CC 单函数 ≥20 入榜。", "",
             "| 文件 | 函数 | CC | 行 |", "|---|---|---|---|"]
    for item in rows:
        lines.append("| `%s` | `%s` | %s | %s |" % (item.get("file"), item.get("name"),
                                                    item.get("complexity"), item.get("lineno")))
    if not rows:
        lines.append("| — | — | — | — |")
    return "\n".join(lines) + "\n"


def write(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    from core import atomic_write
    tc, scan = build(root)
    dest = Path(root) / DIR_REL
    dest.mkdir(parents=True, exist_ok=True)
    atomic_write.write_text(dest / "toolchain.json", render_json(tc))
    atomic_write.write_text(dest / "scan.json", render_json(scan))
    atomic_write.write_text(dest / "findings.jsonl", render_findings(scan["findings"]))
    atomic_write.write_text(dest / "hotspots.md", render_hotspots(scan))
    issues = []
    if scan["p0"]:
        issues.append("P0=%d（%s 先修 P0 再进 CQ2）" % (scan["p0"], GUIDE))
    if tc.get("blocked"):
        issues.append("缺失/不可用工具：%s（BLOCKED，不冒充通过）" % ", ".join(tc["blocked"]))
    return issues, {"toolchain": tc, "scan": scan}


def check(root: str = ".") -> List[str]:
    """新鲜度：产物在场 + 指纹（输入件内容 + 工具版本）与实时一致。"""
    scan_path = Path(root) / SCAN_REL
    tc_path = Path(root) / TOOLCHAIN_REL
    for path in (scan_path, tc_path):
        if not path.is_file():
            return ["缺 %s（%s 跑 python scripts/cq_scan.py --run）"
                    % (path.relative_to(Path(root)).as_posix(), GUIDE)]
    try:
        scan = json.loads(scan_path.read_text(encoding="utf-8"))
        tc = json.loads(tc_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["CQ 产物不可解析：%s" % exc]
    live_tc = toolchain(root)
    live_fp = _fingerprint(root, live_tc)
    if scan.get("fingerprint") != live_fp:
        return ["CQ 扫描件过期（输入件或工具版本已变；%s 跑 python scripts/cq_scan.py --run）"
                % GUIDE]
    return []
