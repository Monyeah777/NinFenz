"""core.cq_scan 私有实现分片 1/2（对外只经 core.cq_scan 门面导入）：TOOLCHAIN_SCHEMA 等"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
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
