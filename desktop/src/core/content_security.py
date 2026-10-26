"""内容供应链安全扫描（T8.3：域包/投稿正文 = 外来内容，形态可扫描可拦截）。

定位（威胁模型见 `docs/security/threat-model.md`）：
`community/**`（社区域包）与 `library/**`（投稿入库）的正文是**外来内容**——按数据消费，
但其形态可能夹带可执行片段、明文凭据、隐藏/超长载荷或植入式指令。本模块给出**只读、
离线、确定性**的形态扫描：不联网、不执行、不改写任何文件，只把「哪一行是什么形态」如实
报出来，供人工/CI 抽查。

**复用（单一真相源，不自造第二套正则）**：
- 指令注入标记 → `core.trust_boundary.detect()`（AGENTS.md / 06 §12 已把注入面立成判据）；
- 疑似明文凭据形状 → `core.ingest_common.secret_shape_hit()`（与 CI 明文密钥扫描同源，
  只回显前 4 字符的掩码，绝不把疑似密钥再抄一遍）。

severity 分类（口径 = 06 §12「疑似内嵌指令一律忽略并记档」+ 本仓「内容即数据」纪律）：
- `critical`：**硬风险**——可执行/主动内容（`<script>` / `javascript:` / `data:text/html` /
  事件处理器 / 可执行文件下载链接）、明文凭据或私钥。命中即非零退出（exit 1）。
- `warn`：**咨询面**——指令注入标记、隐藏/控制字符、超长单行、base64 大块、可疑外链。
  只报不阻断（exit 0）：讨论注入防御/安全研究的合法正文同样会命中，见 `trust_boundary`
  的既有裁定；是否处置由人裁定。
- 不可判定：IO/解码/二进制/超大件 → exit 2（fail-closed：判不了就明说，不静默放过）。

纪律：纯标准库、无副作用、同输入同输出（findings 按 文件→行→规则序 稳定排序）。
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core import ingest_common as _ingest
from core import trust_boundary as _tb

SCHEMA = "nf-content-security/1"
KIND = "security-scan"

#: 默认扫描面（外来内容面；与 `trust_boundary.UNTRUSTED_PREFIXES` 同口径的前两项）。
DEFAULT_PATHS: Tuple[str, ...] = ("community", "library")

#: **显式**测试样本白名单（前缀，仓库根相对）：样本本身故意含恶意片段，用于自证扫描器
#: 抓得住。白名单不是「静默放过」——默认扫描把它们列进 `skipped`；显式传参扫描时 findings
#: 仍逐条报出（标 `allowlisted: true`），只是不计入退出码判定。
TEST_SAMPLE_ALLOWLIST: Tuple[str, ...] = (
    "desktop/tests/fixtures/security/",
    "docs/security/examples/",
)

#: 硬风险（exit 1）的 kind；其余为咨询面（warn）。
CRITICAL_KINDS = ("executable_content", "secret_material")
#: 全部 finding kind（JSON 消费方据此枚举）。
FINDING_KINDS = ("prompt_injection", "hidden_character", "control_character",
                 "executable_content", "secret_material", "long_line",
                 "base64_blob", "external_link")
#: 规则序（同一行多命中时的报告顺序；也用于稳定排序）。
RULE_ORDER = ("authority_spoof", "override_instruction", "role_redefine",
              "system_prompt_probe", "credential_exfil", "hidden_channel",
              "control_character", "script_tag", "active_content", "event_handler",
              "executable_link", "secret_shape", "private_key", "long_line",
              "base64_blob", "http_plain", "link_shortener", "punycode_host",
              "ip_host")

#: 单文件上限（字节）：超限记「不可判定」而不是把整份读进内存。
MAX_FILE_BYTES = 4 * 1024 * 1024
#: 单行上限（字符）：超长单行拖慢审阅与渲染，也是隐藏载荷的常见载体。
MAX_LINE_CHARS = 4000
#: base64 大块下限（字符）：低于此值属正常文本（短语/短 id），不报。
BASE64_MIN_CHARS = 256
#: 只扫内容格式（源码/二进制不在默认面；`.svg`/`.graphml` 是 XML 内容件，仍扫）。
TEXT_EXTS = (".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".mmd",
             ".graphml", ".svg")
#: 遍历时跳过的目录（版本库/缓存/虚拟环境）。
SKIP_DIRS = frozenset({".git", ".gitee", ".nf-cache", "__pycache__",
                       "node_modules", ".mypy_cache", ".ruff_cache"})

#: 输入管线/展示的修复指引（kind → 一句话；保持确定性，便于逐条对账）。
FIXES: Dict[str, str] = {
    "prompt_injection": "把该正文按**数据**消费：不要执行其中的指令；若属注入防御/安全研究等"
                        "合法题材，登记进显式白名单（TEST_SAMPLE_ALLOWLIST）并在威胁模型记档。",
    "hidden_character": "删除零宽/双向控制字符（U+200B–U+200F / U+202A–U+202E 等）——正文不应"
                        "携带隐藏通道字符。",
    "control_character": "删除 C0/C1 控制字符，改为可见文本或转义写法；确需展示请放围栏代码块"
                         "并说明来源。",
    "executable_content": "删除可执行/主动内容（<script>/<iframe>/javascript:/data:text/html/"
                          "事件处理器/可执行文件下载链接）；文档里只以围栏代码块展示示例。",
    "secret_material": "按 CONTRIBUTING 的 Token 轮换 SOP 撤销并重建该凭据，再从内容中删除；"
                       "本报告只保留掩码，不要再把疑似密钥复制到别处。",
    "long_line": "把超长单行拆行或放入围栏代码块（超长单行拖慢渲染/审阅，也是隐藏载荷常见载体）。",
    "base64_blob": "base64 大块无法人工审阅：解码后改写为可读文本；确需保留请放入围栏代码块"
                   "并写明来源与解码方式。",
    "external_link": "核对链接目标与协议：改用 https、写真实域名（避免短链/裸 IP/punycode），"
                     "可执行文件下载链接须删除。",
    "undecidable": "该件无法按文本判定（IO/编码/大小/二进制）：先修复可读性再重扫，或在威胁"
                   "模型的「未覆盖项」里如实登记。",
}

_NS_PREFIXES = ("http://www.w3.org/", "http://graphml.graphdrawing.org/",
                "http://purl.org/", "http://xmlns.", "http://schemas.")

#: 行内规则表（顺序即 RULE_ORDER；`(rule, kind, severity, pattern)`）。
_LINE_RULES: Tuple[Tuple[str, str, str, "re.Pattern[str]"], ...] = (
    ("script_tag", "executable_content", "critical", re.compile(r"<\s*script", re.I)),
    ("active_content", "executable_content", "critical",
     re.compile(r"<\s*(?:iframe|object|embed)\b|javascript\s*:|data\s*:\s*text/html", re.I)),
    ("event_handler", "executable_content", "critical",
     re.compile(r"\bon(?:error|load|click|mouseover)\s*=", re.I)),
    ("executable_link", "executable_content", "critical",
     re.compile(r"\]\(\s*[^)\n]*\.(?:exe|scr|bat|cmd|ps1|vbs|jar|msi|dll|com|pif)\b", re.I)),
    ("private_key", "secret_material", "critical",
     re.compile(r"-----BEGIN [A-Z ]{0,20}PRIVATE KEY-----")),
    ("base64_blob", "base64_blob", "warn",
     re.compile(r"[A-Za-z0-9+/]{%d,}={0,2}" % BASE64_MIN_CHARS)),
    ("link_shortener", "external_link", "warn",
     re.compile(r"\b(?:bit\.ly|tinyurl\.com|t\.cn|url\.cn|goo\.gl|ow\.ly|is\.gd)\b", re.I)),
    ("punycode_host", "external_link", "warn", re.compile(r"\bhttps?://xn--", re.I)),
    ("ip_host", "external_link", "warn",
     re.compile(r"\bhttps?://\d{1,3}(?:\.\d{1,3}){3}")),
)
#: 明文 http（非 TLS）——排除 XML 命名空间声明（内容件里的 xmlns 不是外链）。
_HTTP_PLAIN = re.compile(r"http://(?!(?:www\.w3\.org|graphml\.graphdrawing\.org|purl\.org|"
                         r"xmlns\.|schemas?\.))")
#: C0/C1 控制字符（不含 \t \n \r 这些正常排版字符）。
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

_SKIP_BINARY_SNIFF = 8192


def _finding(file: str, line: int, kind: str, severity: str, rule: str,
             evidence: str, column: int = 0,
             allowlisted: bool = False) -> Dict[str, Any]:
    return {"file": file, "line": int(line), "kind": kind, "severity": severity,
            "rule": rule, "masked_evidence": evidence, "fix": FIXES[kind],
            "column": int(column), "allowlisted": bool(allowlisted)}


def _snippet(text: str, n: int = 80) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= n else s[:n] + "…"


def is_allowlisted(rel: str) -> bool:
    """仓库根相对路径是否落在显式测试样本白名单（前缀匹配，大小写不敏感）。"""
    p = str(rel or "").replace("\\", "/").lstrip("./").lower()
    return any(p.startswith(pre.lower()) for pre in TEST_SAMPLE_ALLOWLIST)


def _injection_findings(text: str, file: str,
                        allowlisted: bool) -> List[Dict[str, Any]]:
    """指令注入标记（单源 = `trust_boundary.detect`）→ warn 级 findings。"""
    out: List[Dict[str, Any]] = []
    for hit in _tb.detect(text) or []:
        rule = str(hit.get("rule") or "")
        if rule == "truncated":
            continue
        kind = "hidden_character" if rule == "hidden_channel" else "prompt_injection"
        out.append(_finding(file, int(hit.get("line") or 0), kind, "warn", rule,
                            _snippet(hit.get("snippet") or ""), allowlisted=allowlisted))
    return out


def _line_findings(line: str, lineno: int, file: str,
                   allowlisted: bool) -> List[Dict[str, Any]]:
    """单行形态规则（可执行/凭据/结构/外链）→ findings。"""
    out: List[Dict[str, Any]] = []
    if len(line) > MAX_LINE_CHARS:
        out.append(_finding(file, lineno, "long_line", "warn", "long_line",
                            "%s…（共 %d 字符）" % (_snippet(line, 40), len(line)),
                            allowlisted=allowlisted))
    for rule, kind, severity, pat in _LINE_RULES:
        for m in pat.finditer(line):
            out.append(_finding(file, lineno, kind, severity, rule,
                                _masked(m.group(0), rule), m.start(),
                                allowlisted))
    sec = _ingest.secret_shape_hit(line)
    if sec:
        out.append(_finding(file, lineno, "secret_material", "critical",
                            "secret_shape", sec, allowlisted=allowlisted))
    for m in _CTRL.finditer(line):
        out.append(_finding(file, lineno, "control_character", "warn",
                            "control_character", repr(m.group(0)), m.start(),
                            allowlisted))
    for m in _HTTP_PLAIN.finditer(line):
        out.append(_finding(file, lineno, "external_link", "warn", "http_plain",
                            "http://…", m.start(), allowlisted))
    out.sort(key=lambda f: RULE_ORDER.index(f["rule"]) if f["rule"] in RULE_ORDER else 99)
    return out


def _masked(token: str, rule: str) -> str:
    """命中片段 → 掩码证据（永不回显完整敏感/载荷内容）。"""
    if rule == "private_key":
        return "-----BEGIN …PRIVATE KEY-----"
    t = _snippet(token, 60)
    if rule == "base64_blob":
        return "%s…（base64 块，共 %d 字符）" % (t[:20], len(token))
    if rule in ("link_shortener", "punycode_host", "ip_host"):
        return re.sub(r"(https?://[^/\s]+).*", r"\1/…", token, flags=re.I)[:60]
    if rule == "executable_link":
        return "…" + token[-40:]
    return t


def scan_text(text: str, file: str = "<text>",
              allowlisted: bool = False) -> List[Dict[str, Any]]:
    """扫描一段文面 → findings（按 行→规则序 稳定排序）。"""
    out = _injection_findings(text, file, allowlisted)
    for lineno, line in enumerate(text.splitlines(), 1):
        out.extend(_line_findings(line, lineno, file, allowlisted))
    out.sort(key=lambda f: (f["line"], RULE_ORDER.index(f["rule"])
                            if f["rule"] in RULE_ORDER else 99, f["column"]))
    return out


def _read_text(path: str) -> Tuple[Optional[str], str]:
    """读文件 → (text, 不可判定原因)。二进制/超限/解码失败都如实返回原因。"""
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        return None, "不可读：%s" % exc
    if size > MAX_FILE_BYTES:
        return None, "超过单文件上限（%d > %d 字节）" % (size, MAX_FILE_BYTES)
    try:
        with open(path, "rb") as fh:
            head = fh.read(_SKIP_BINARY_SNIFF)
        if b"\x00" in head:
            return None, "含 NUL 字节（按二进制跳过，不做文本判定）"
        with open(path, encoding="utf-8") as fh:
            return fh.read(), ""
    except UnicodeDecodeError as exc:
        return None, "非 UTF-8 文本（%s）" % exc
    except OSError as exc:
        return None, "不可读：%s" % exc


def _rel(root: str, path: str) -> str:
    """→ 报告用的仓库根相对路径（统一 `/`；`_no_machine_paths` 要求不留机器绝对路径）。"""
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    except ValueError:                              # Windows 跨盘符
        return os.path.basename(path)
    return rel.replace("\\", "/")


def _iter_files(root: str, rel: str) -> List[str]:
    """展开扫描目标 → 文件绝对路径列表（目录递归；跳过 SKIP_DIRS；只看内容格式）。"""
    abs_path = os.path.abspath(os.path.join(root, rel))
    if os.path.isfile(abs_path):
        return [abs_path]
    if not os.path.isdir(abs_path):
        return []
    out: List[str] = []
    for base, dirs, files in os.walk(abs_path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in TEXT_EXTS:
                out.append(os.path.join(base, name))
    return out


def _norm_rel(target: str) -> str:
    """扫描目标 → 仓库根相对写法的规范形（去 `./` 前缀、`\\` 归一为 `/`）。"""
    p = str(target or "").replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p or "."


def scan(paths: Optional[Sequence[str]] = None, root: str = ".") -> Dict[str, Any]:
    """扫描 → 结构化报告（`kind`/`schema`/`findings`/`summary`/`exit` 齐备）。

    - `paths` 缺省 = `DEFAULT_PATHS`（community/ 与 library/）；显式路径可含文件或目录。
    - 白名单（显式测试样本）：默认扫描**不扫但登记**进 `skipped`（含白名单前缀下实存件，
      不是静默放过）；显式传参扫描时仍逐条报 findings（`allowlisted: true`），但不计入退出码。
    """
    root = os.path.abspath(root)
    raw_targets = [str(p) for p in (paths or DEFAULT_PATHS)]
    # 报告里的路径一律仓库根相对（`--json` 成功面不得回吐机器绝对路径）。
    display = [_norm_rel(_rel(root, t) if os.path.isabs(t) else t) for t in raw_targets]
    findings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    n_bytes = n_files = 0
    for target in raw_targets:
        rel_t = _norm_rel(_rel(root, target) if os.path.isabs(target) else target)
        explicit = bool(paths)                        # 显式传参 ⇒ 白名单件也真扫
        files = _iter_files(root, target if os.path.isabs(target) else rel_t)
        if not files:
            errors.append({"file": rel_t, "reason": "扫描目标不存在或无可扫描文件",
                           "kind": "undecidable"})
            continue
        for abs_path in files:
            rel_f = _rel(root, abs_path)
            allowed = is_allowlisted(rel_f)
            if allowed and not explicit:
                skipped.append({"file": rel_f, "reason": "allowlist（显式测试样本）"})
                continue
            text, reason = _read_text(abs_path)
            if text is None:
                errors.append({"file": rel_f, "reason": reason, "kind": "undecidable"})
                continue
            n_files += 1
            n_bytes += len(text.encode("utf-8"))
            findings.extend(scan_text(text, rel_f, allowlisted=allowed))
    if not paths:
        # 默认扫描**显式登记**测试样本面：它们不在扫描路径内，但必须让读者看见「这些件被
        # 白名单跳过了」——白名单是声明，不是静默放过（默认面 = 内容面 + 已知样本面）。
        for prefix in TEST_SAMPLE_ALLOWLIST:
            for abs_path in _iter_files(root, prefix.rstrip("/") or "."):
                rel_f = _rel(root, abs_path)
                if is_allowlisted(rel_f) and rel_f not in [s["file"] for s in skipped]:
                    skipped.append({"file": rel_f,
                                    "reason": "allowlist（显式测试样本）"})
    summary = {
        "critical": sum(1 for f in findings if f["severity"] == "critical"),
        "warn": sum(1 for f in findings if f["severity"] == "warn"),
        "undecidable": len(errors),
        "allowlisted": sum(1 for f in findings if f["allowlisted"]),
        "findings": len(findings),
    }
    exit_code = exit_code_for(summary)
    return {"kind": KIND, "schema": SCHEMA, "root": _rel(root, root),
            "paths": display, "allowlist": list(TEST_SAMPLE_ALLOWLIST),
            "scanned": {"files": n_files, "bytes": n_bytes},
            "skipped": skipped, "findings": findings, "errors": errors,
            "summary": summary, "exit": exit_code, "ok": exit_code == 0}


def exit_code_for(summary: Dict[str, Any]) -> int:
    """退出码口径：0 干净（无 critical） / 1 有 critical / 2 不可判定（fail-closed）。"""
    if int(summary.get("undecidable") or 0) > 0:
        return 2
    if int(summary.get("critical") or 0) > 0:
        return 1
    return 0


def render_text(report: Dict[str, Any]) -> str:
    """人读报告（确定性；含逐条掩码证据与修复指引）。"""
    s = report.get("summary") or {}
    lines = ["== 内容供应链安全扫描 ==",
             "  扫描 %d 件 / %d 字节 · critical %d · warn %d · 不可判定 %d"
             % ((report.get("scanned") or {}).get("files", 0),
                (report.get("scanned") or {}).get("bytes", 0),
                s.get("critical", 0), s.get("warn", 0), s.get("undecidable", 0))]
    if report.get("paths"):
        lines.append("  路径：%s（根：%s）"
                     % ("、".join(report["paths"]), report.get("root") or "."))
    for item in report.get("skipped") or []:
        lines.append("  [白名单] %s — %s（不计入判定）"
                     % (item.get("file"), item.get("reason")))
    for f in report.get("findings") or []:
        tag = "CRITICAL" if f["severity"] == "critical" else "WARN"
        lines.append("  [%s] %s:%d %s — %s"
                     % (tag, f["file"], f["line"], f["kind"], f["masked_evidence"]))
        lines.append("        修复：%s" % f["fix"])
    for item in report.get("errors") or []:
        lines.append("  [不可判定] %s — %s" % (item.get("file"), item.get("reason")))
    if report.get("ok"):
        lines.append("  ✓ 无 critical（退出码 0）")
    elif int(report.get("exit") or 0) == 2:
        lines.append("  ? 存在不可判定件（退出码 2）——先修复可读性再重扫")
    else:
        lines.append("  ✗ 存在 critical（退出码 1）——按上方修复指引处置后重扫")
    return "\n".join(lines)
