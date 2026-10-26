"""隐私与 air-gap 静态审计（T11.2：把「保密/本地优先」从口号变成可机检面）。

两个互补的面（都只读、离线、确定性、不执行被扫内容）：

1. **内容面扫描**（`scan`）：默认扫 `docs/` `site/` `protocol/` `community/` `library/`，
   找 PII（邮箱/手机/身份证/银行卡）、本机路径（盘符 / `/Users/` / `/home/` / `%APPDATA%` 等）、
   凭据（**单源复用** `core.content_security` 的 secret 形状，不另造正则）。输出只给
   `file:line` + 掩码，不回显完整值。
2. **代码面静态审计**（`check`）：AST 扫 `desktop/src/core/` 与 `scripts/` 的网络站点
   （import `requests`/`urllib.request`/`http.client`/`socket`/`websocket` 等，以及
   `subprocess`/`os.system` 调 `curl`/`wget`/`nc`）。**合法站点逐条登记理由**（本机回环 IPC、
   显式网络工具），白名单不得变黑洞——登记了却没命中即红（陈旧条目）。

判定口径：
- `critical` = 真实 PII、作者本机路径、明文凭据、未登记网络站点/陈旧白名单；
- `warn` = 保留域（`example.org` 等）合成邮箱、合成占位路径；
- 不可判定（IO/非 UTF-8/二进制/超大/目标缺失）→ `exit 2`（fail-closed）。

**不宣称「绝对离线」**：本模块是**静态**审计——它证明「核心/脚本目录里有哪些网络站点、
它们是否登记了理由」，不能证明运行时网络被禁用（无沙箱/无 egress 阻断）。真实结论与未覆盖项
见 `docs/security/airgap-and-privacy.md`。
"""
from __future__ import annotations

import ast
import datetime as _dt
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core import content_security as _cs
from core import ingest_common as _ic

SCHEMA = "nf-privacy-scan/1"
KIND = "privacy-scan"
CHECK_KIND = "privacy-check"

#: 内容面默认扫描路径（发布面 + 机读真源 + 外来内容面）。
DEFAULT_PATHS: Tuple[str, ...] = ("docs", "site", "protocol", "community", "library")

#: 显式测试样本白名单（路径前缀）：合成 PII/路径只许出现在这里；默认扫描**不扫但登记**，
#: 显式传参时仍逐条报出（`allowlisted: true`）但不计入退出码（与 content_security 同口径）。
TEST_SAMPLE_ALLOWLIST: Tuple[str, ...] = ("desktop/tests/fixtures/privacy/",)

#: 网络面静态审计目录（任务口径：core/ 与 scripts/）。
AUDIT_DIRS: Tuple[str, ...] = ("desktop/src/core", "scripts")

#: 全部 finding kind（JSON 消费方据此枚举）。
FINDING_KINDS = ("pii_email", "pii_phone", "pii_id", "pii_bank_card",
                 "local_path", "credential")
CHECK_KINDS = ("network_site", "stale_whitelist")

#: 单文件上限（字节）与单行上限（字符）——与 content_security 同口径。
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_LINE_CHARS = 20000

#: 内容格式（源码另由 check 面审计，不进内容面）。
TEXT_EXTS = (".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".mmd", ".graphml",
             ".svg", ".html", ".htm", ".js", ".mjs", ".css", ".toml", ".ini")
SKIP_DIRS = frozenset({".git", ".gitee", ".nf-cache", "__pycache__", "node_modules",
                       ".mypy_cache", ".ruff_cache"})

#: 保留域（RFC 2606/6761 与示例域）：命中的邮箱判 warn（合成样例常见），其余判 critical。
RESERVED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "example.edu",
                          "example.invalid", "example.test", "test", "invalid",
                          "localhost")

#: 修复指引（kind → 一句话；确定性，便于逐条对账）。
FIXES: Dict[str, str] = {
    "pii_email": "删除真实邮箱或改为保留域（example.org）/角色地址；确需公示请走 SECURITY.md "
                 "的报告通道，不把个人邮箱写进内容面。",
    "pii_phone": "删除手机号或改为明显合成值（如 19900000000 之外请用占位写法）；"
                 "真实手机号属个人敏感信息，不得进公开仓。",
    "pii_id": "删除身份证号；确需示例请用公开合成值，并在 docs/security/airgap-and-privacy.md 记档。",
    "pii_bank_card": "删除银行卡号；确需示例请用卡组织公开测试号（如 4111 1111 1111 1111）。",
    "local_path": "改写为仓库相对路径或占位写法（`<仓库根>` / `~/…`）；作者机绝对路径既泄漏隐私"
                  "又让证据换机不可解释。",
    "credential": "按 CONTRIBUTING 的 Token 轮换 SOP 撤销重建，再从内容删除；本报告只保留掩码。",
    "network_site": "给该站点登记白名单理由（若确属本机回环/显式网络工具），或删除网络调用；"
                    "登记处 = core.privacy_scan.NETWORK_ALLOWLIST（逐条理由）+ 文档 §白名单。",
    "stale_whitelist": "白名单条目已无命中（文件删除或网络调用已移除）：删掉该条，否则名单会"
                       "变成掩盖新网络站点的黑洞（对应文件已不在场时同理）。",
}

#: 网络模块（import 面）：命中即「网络站点」候选。`urllib.parse`/`urllib.error` 不算网络。
NETWORK_MODULES = ("requests", "aiohttp", "httpx", "urllib3", "websocket", "websockets",
                   "socket", "http.client", "http.server", "ftplib", "smtplib",
                   "telnetlib", "xmlrpc.client", "urllib.request")
#: shell 取网命令（subprocess/os.system 面）：只认**调用参数里的字面量**（不认注释/文档）。
SHELL_NET_TOKENS = ("curl ", "wget ", "nc ", "ncat ", "socat ", "telnet ")
#: 动态 import 的函数名（`__import__("socket")` / `importlib.import_module("requests")`）。
DYNAMIC_IMPORT_CALLS = ("__import__", "import_module", "import_string")

#: **合法网络站点白名单**（仓库根相对路径 → 理由）。新增须同时写进
#: `docs/security/airgap-and-privacy.md` 的白名单表；无命中即红（见 FIXES.stale_whitelist）。
NETWORK_ALLOWLIST: Dict[str, str] = {
    "desktop/src/core/daemon.py":
        "本机回环 IPC 服务端：只绑 127.0.0.1（BIND_HOST），一次性令牌鉴权；不是互联网出口",
    "desktop/src/core/rust_engine.py":
        "与 nf-rs 快速通道的本机回环连接（BIND_HOST=127.0.0.1）；只连本机子进程",
    "desktop/src/core/interop.py":
        "interop loopback HTTP 服务（host 默认 127.0.0.1、port=0 取临时端口），供本地互操作/测试",
    "desktop/src/core/decision_layer.py":
        "决策模型适配器：端点由调用方显式给出（文档示例 http://127.0.0.1:8791/…）；只校验 scheme，"
        "未钉宿主——属残余风险，见 airgap-and-privacy.md §未覆盖项",
    "scripts/nf_client.py":
        "nf 客户端连接本机 daemon（127.0.0.1:port），回环 IPC 客户端面",
    "scripts/serve_decision_model.py":
        "本机 typed-decision 演示服务（默认只绑 127.0.0.1；跨机需带鉴权反代）",
    "scripts/check_external_links.py":
        "**显式**外链检查工具：本职就是联网校验外链，不在 nf 命令面运行",
    "scripts/check_interop_schemas.py":
        "**显式**上游 schema 拉取工具：对照官方 meta-schema 校验 interop 文档，CI 可选跑",
    "scripts/gen_third_party_notices.py":
        "**显式**第三方许可证文本拉取工具：生成 THIRD_PARTY-NOTICES 用，非运行时路径",
}

#: **不在审计面**的目录 → 理由（如实声明边界，而不是悄悄跳过）。
EXCLUDED_SURFACES: Dict[str, str] = {
    ".github/scripts/": "入库机器人（GitHub/Gitee API 必需联网，运行在 CI 云端；不属本机离线面）",
    "site/tools/": "站点发布工具（Node/CF/IndexNow 等，发布面而非核心运行面）",
    "desktop/tests/": "测试可含合成网络负例（拦截面自证用），不属核心运行面",
    "packaging/": "npm 包装与运行时壳（发布产物，不属 core/scripts 面）",
    "engine/": "Rust/.NET 工具链（其供应链与网络面归 SAST/scorecard 门禁）",
    "05_资产库/": "用户自定义资产面（内容扫描另见 docs/security/threat-model.md 内容供应链面）",
}

#: 身份证：GB 11643 加权校验（校验位错即不是身份证号 → 不报，避免把 18 位数字全当 PII）。
_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK = "10X98765432"
_ID_RE = re.compile(r"(?<![0-9A-Za-z])(\d{17}[\dXx])(?![0-9A-Za-z])")
#: 银行卡：13–19 位（可含空格/连字符）+ Luhn + 卡组织 BIN 前缀（防把图表里的长数字当卡号）。
_CARD_RE = re.compile(r"(?<![0-9A-Za-z])((?:\d[ -]?){12,18}\d)(?![0-9A-Za-z])")
#: 手机号（中国大陆）：1[3-9] 开头 11 位，两侧不许粘字母数字。
_PHONE_RE = re.compile(r"(?<![0-9A-Za-z])(1[3-9]\d{9})(?![0-9A-Za-z])")
#: 邮箱（宽松形状 + 保留域分类）。**量化全部加界**（局部段 ≤64 / 域标签 ≤63 / 层级 ≤8）：
#: 无界 `[A-Za-z0-9._%+-]+@` 在「长串字母数字但没有 @」的输入上是 O(n²)（ReDoS，
#: `desktop/tests/test_redos_patterns.py` 全仓面会红）。
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@"
    r"([A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,8}\.[A-Za-z]{2,24})")
#: 本机路径：Windows 用户目录 / POSIX 用户目录 / Windows 环境变量 / 一般盘符路径。
_WIN_USER = re.compile(r"(?i)(?<![A-Za-z0-9])[A-Z]:[\\/]Users[\\/][^\s\"'<>|，。；：]+")
_UNIX_USER = re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home)/[^\s\"'<>|，。；：/]+")
_WIN_ENV = re.compile(r"%(?:APPDATA|LOCALAPPDATA|USERPROFILE|TEMP|TMP)%", re.I)
_DRIVE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/][^\s\"'<>|，。；：]+")
#: 占位写法（不是真实机器路径）：含 `<…>`、通配符、省略号、转义双反斜杠（文档示例写法），
#: 或整段就是占位词。
_PLACEHOLDER_MARKS = ("<", ">", "*", "?", "…", "%USERNAME%", "\\\\")
_PLACEHOLDER_SEGS = frozenset({"user", "username", "name", "yourname", "you", "x",
                               "foo", "bar", "path", "<user>"})
#: **正则/断言模式串**（如 `protocol/assertions.json` 里的匹配式）：不是路径，直接跳过。
_REGEXISH = re.compile(r"[\[\](){}\|^$]")
#: 凭据扫描的**性能粗筛**：从 `ingest_common._SECRET_SHAPES`（content_security 的秘密形状
#: 单一真源）**在导入时派生**字面前缀正则——不复制形状知识，真源变了粗筛自动跟着变；
#: 若某个形状没有字面前缀（无法粗筛），派生结果退化为 None ⇒ 退化为「全扫」（sound fallback）。
def _derive_secret_prefixes() -> Optional["re.Pattern[str]"]:
    try:
        pattern = str(_ic._SECRET_SHAPES.pattern)      # noqa: SLF001 - 单一真源在 ingest_common
    except Exception:                                  # noqa: BLE001 - 派生失败即退化为全扫
        return None
    prefixes: List[str] = []
    for alt in pattern.split("|"):
        buf: List[str] = []
        for ch in alt:
            if ch.isalnum() or ch in "_-":
                buf.append(ch)
            else:
                break
        if not buf:
            return None                                # 有形状无字面前缀 ⇒ 不能粗筛
        prefixes.append(re.escape("".join(buf)))
    return re.compile("|".join(prefixes)) if prefixes else None


_SECRET_PREFIX_RE = _derive_secret_prefixes()


# ------------------------------------------------------------------ 掩码/校验
def _finding(file: str, line: int, kind: str, severity: str, rule: str,
             evidence: str, column: int = 0,
             allowlisted: bool = False) -> Dict[str, Any]:
    return {"file": file, "line": int(line), "kind": kind, "severity": severity,
            "rule": rule, "masked_evidence": evidence, "fix": FIXES[kind],
            "column": int(column), "allowlisted": bool(allowlisted)}


def _snippet(text: str, n: int = 60) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= n else s[:n] + "…"


def _mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    keep = local[:1] if local else ""
    return "%s***@%s" % (keep, domain)


def _mask_digits(value: str, head: int = 4, tail: int = 4) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) <= head + tail:
        return digits[:2] + "***"
    return digits[:head] + "*" * (len(digits) - head - tail) + digits[-tail:]


def _mask_path(value: str) -> str:
    """本机路径掩码：保留形态前缀，遮掉用户名与剩余段。"""
    v = str(value).replace("\\", "/")
    m = re.match(r"(?i)^([A-Z]:/Users/|/Users/|/home/|%APPDATA%|%LOCALAPPDATA%|"
                 r"%USERPROFILE%|%TEMP%|%TMP%)", v)
    prefix = m.group(1) if m else (v[:3] if re.match(r"(?i)^[A-Z]:/", v) else "")
    return prefix + "***"


def luhn_ok(number: str) -> bool:
    """银行卡号 Luhn 校验（纯函数，变异自证直接喂它）。"""
    digits = [int(c) for c in str(number) if c.isdigit()]
    if not digits:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def id_card_ok(value: str) -> bool:
    """身份证校验：GB 11643 加权校验位 + 出生日期合法（非法即不是身份证号）。"""
    s = str(value).upper()
    if not re.fullmatch(r"\d{17}[\dX]", s):
        return False
    try:
        year, month, day = int(s[6:10]), int(s[10:12]), int(s[12:14])
        _dt.date(year, month, day)
    except ValueError:
        return False
    if not 1900 <= year <= 2100:
        return False
    total = sum(int(s[i]) * _ID_WEIGHTS[i] for i in range(17))
    return _ID_CHECK[total % 11] == s[17]


def card_bin_ok(number: str) -> bool:
    """卡组织 BIN 前缀 + 长度粗筛（Visa/Mastercard/Amex/UnionPay/JCB/Discover/Diners）。"""
    digits = re.sub(r"\D", "", number)
    n = len(digits)
    if not 13 <= n <= 19:
        return False
    if digits[0] == "4" and n in (13, 16, 19):
        return True
    if 16 <= n <= 19 and digits[0] == "6":            # UnionPay / Discover
        return True
    if n == 16 and (digits.startswith(("51", "52", "53", "54", "55"))
                    or "2221" <= digits[:4] <= "2720"):
        return True
    if n == 15 and digits.startswith(("34", "37")):
        return True
    if 16 <= n <= 19 and digits.startswith("35"):
        return True
    if 14 <= n <= 19 and (digits.startswith(("30", "36", "38", "39"))):
        return True
    return False


def _is_placeholder_path(value: str, tail: str = "") -> bool:
    """占位路径判定：`<…>`/通配符/省略号/转义双反斜杠/占位段，或紧跟 `<` 的文档写法。"""
    if any(mark in value for mark in _PLACEHOLDER_MARKS):
        return True
    if tail[:1] in ("<", "\\"):
        return True
    segments = [s for s in re.split(r"[\\/]", value) if s]
    return any(seg.lower() in _PLACEHOLDER_SEGS for seg in segments[1:])


# ------------------------------------------------------------------ 内容面扫描
def _pii_findings(line: str, lineno: int, file: str,
                  allowlisted: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if "@" in line:
        for m in _EMAIL_RE.finditer(line):
            domain = m.group(1).lower().strip(".")
            reserved = any(domain == d or domain.endswith("." + d)
                           for d in RESERVED_EMAIL_DOMAINS)
            out.append(_finding(file, lineno, "pii_email",
                                "warn" if reserved else "critical", "email",
                                _mask_email(m.group(0)), m.start(), allowlisted))
    if not any(ch.isdigit() for ch in line):
        return out                                     # 号码类必要条件（性能粗筛，不漏报）
    for m in _PHONE_RE.finditer(line):
        out.append(_finding(file, lineno, "pii_phone", "critical", "phone",
                            _mask_digits(m.group(1), 3, 4), m.start(), allowlisted))
    for m in _ID_RE.finditer(line):
        if id_card_ok(m.group(1)):
            out.append(_finding(file, lineno, "pii_id", "critical", "id_card_gb11643",
                                _mask_digits(m.group(1), 4, 4), m.start(), allowlisted))
    for m in _CARD_RE.finditer(line):
        raw = m.group(1)
        if luhn_ok(raw) and card_bin_ok(raw):
            out.append(_finding(file, lineno, "pii_bank_card", "critical", "card_luhn_bin",
                                _mask_digits(raw, 4, 4), m.start(), allowlisted))
    return out


def _path_findings(line: str, lineno: int, file: str,
                   allowlisted: bool) -> List[Dict[str, Any]]:
    if not any(ch in line for ch in ("/", "\\", ":", "%")):
        return []                                   # 本机路径的必要条件（性能粗筛，不会漏报）
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for pattern, rule in ((_WIN_USER, "win_user_dir"), (_UNIX_USER, "unix_home_dir"),
                          (_WIN_ENV, "win_env_var"), (_DRIVE, "drive_path")):
        for m in pattern.finditer(line):
            value = m.group(0)
            if value in seen or _REGEXISH.search(value):
                continue        # 断言/正则模式串（如 protocol/assertions.json）不是路径
            seen.add(value)
            if rule == "win_env_var":
                # 环境变量是**符号写法**（不含用户名），不是作者机泄漏：判 warn 并保留可见。
                out.append(_finding(file, lineno, "local_path", "warn", rule,
                                    _mask_path(value), m.start(), allowlisted))
                continue
            placeholder = _is_placeholder_path(value, line[m.end():m.end() + 2])
            out.append(_finding(file, lineno, "local_path",
                                "warn" if placeholder else "critical", rule,
                                _mask_path(value), m.start(), allowlisted))
    return out


def _credential_findings(text: str, file: str,
                         allowlisted: bool) -> List[Dict[str, Any]]:
    """凭据：**单源**复用 `content_security` 的 secret 形状（不另造正则）。

    性能粗筛：`_SECRET_PREFIX_RE` 由 `ingest_common._SECRET_SHAPES` **导入时派生**（字面前缀），
    无前缀命中且无 `PRIVATE KEY` 头的文件不可能命中 secret 形状 ⇒ 整文件跳过 content_security
    （只为省时；命中判定仍由 content_security 做）。
    """
    if "PRIVATE KEY" not in text:
        if _SECRET_PREFIX_RE is None:
            pass                                       # 真源无可粗筛前缀 ⇒ 退化为全扫
        elif not _SECRET_PREFIX_RE.search(text):
            return []
    out: List[Dict[str, Any]] = []
    for hit in _cs.scan_text(text, file, allowlisted=allowlisted):
        if hit.get("kind") != "secret_material":
            continue
        out.append(_finding(file, int(hit.get("line") or 0), "credential", "critical",
                            str(hit.get("rule") or "secret_shape"),
                            str(hit.get("masked_evidence") or ""),
                            int(hit.get("column") or 0), allowlisted))
    return out


def scan_text(text: str, file: str = "<text>",
              allowlisted: bool = False) -> List[Dict[str, Any]]:
    """扫描一段内容面文本 → findings（按 行→列 稳定排序）。"""
    out: List[Dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if len(line) > MAX_LINE_CHARS:
            continue                                   # 超长行不逐正则（记不可判定在文件层）
        out.extend(_pii_findings(line, lineno, file, allowlisted))
        out.extend(_path_findings(line, lineno, file, allowlisted))
    out.extend(_credential_findings(text, file, allowlisted))
    out.sort(key=lambda f: (f["line"], f["column"], f["kind"]))
    return out


def is_allowlisted(rel: str) -> bool:
    p = str(rel or "").replace("\\", "/").lstrip("./").lower()
    return any(p.startswith(pre.lower()) for pre in TEST_SAMPLE_ALLOWLIST)


def _norm_rel(target: str) -> str:
    p = str(target or "").replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p or "."


def _rel(root: str, path: str) -> str:
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    except ValueError:
        return os.path.basename(path)
    return rel.replace("\\", "/")


def _read_text(path: str) -> Tuple[Optional[str], str]:
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        return None, "不可读：%s" % exc
    if size > MAX_FILE_BYTES:
        return None, "超过单文件上限（%d > %d 字节）" % (size, MAX_FILE_BYTES)
    try:
        with open(path, "rb") as fh:
            head = fh.read(8192)
        if b"\x00" in head:
            return None, "含 NUL 字节（按二进制跳过，不做文本判定）"
        with open(path, encoding="utf-8") as fh:
            return fh.read(), ""
    except UnicodeDecodeError as exc:
        return None, "非 UTF-8 文本（%s）" % exc
    except OSError as exc:
        return None, "不可读：%s" % exc


def _iter_files(root: str, rel: str) -> List[str]:
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


def scan(paths: Optional[Sequence[str]] = None, root: str = ".") -> Dict[str, Any]:
    """内容面扫描 → 结构化报告（`kind=privacy-scan`）。

    白名单：默认扫描**不扫但登记**（含白名单前缀下实存件）；显式传参时仍逐条报出
    （`allowlisted: true`）但不计入退出码。
    """
    root = os.path.abspath(root)
    raw_targets = [str(p) for p in (paths or DEFAULT_PATHS)]
    display = [_norm_rel(_rel(root, t) if os.path.isabs(t) else t) for t in raw_targets]
    findings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    n_files = n_bytes = 0
    for target in raw_targets:
        rel_t = _norm_rel(_rel(root, target) if os.path.isabs(target) else target)
        explicit = bool(paths)
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
        for prefix in TEST_SAMPLE_ALLOWLIST:
            for abs_path in _iter_files(root, prefix.rstrip("/") or "."):
                rel_f = _rel(root, abs_path)
                if is_allowlisted(rel_f) and rel_f not in [s["file"] for s in skipped]:
                    skipped.append({"file": rel_f,
                                    "reason": "allowlist（显式测试样本）"})
    summary = {
        # critical 只计**不计入退出码之外**的件：白名单测试样本命中也逐条报出，但不算红。
        "critical": sum(1 for f in findings
                        if f["severity"] == "critical" and not f["allowlisted"]),
        "warn": sum(1 for f in findings if f["severity"] == "warn"),
        "undecidable": len(errors),
        "allowlisted": sum(1 for f in findings if f["allowlisted"]),
        "findings": len(findings),
    }
    code = 2 if summary["undecidable"] else (1 if summary["critical"] else 0)
    return {"kind": KIND, "schema": SCHEMA, "root": _rel(root, root),
            "paths": display, "allowlist": list(TEST_SAMPLE_ALLOWLIST),
            "scanned": {"files": n_files, "bytes": n_bytes},
            "skipped": skipped, "findings": findings, "errors": errors,
            "summary": summary, "exit": code, "ok": code == 0}


# ------------------------------------------------------------------ 网络面静态审计
def _network_module(name: str) -> bool:
    mod = str(name or "").strip()
    if not mod:
        return False
    if mod in NETWORK_MODULES:
        return True
    for net in NETWORK_MODULES:
        if mod.startswith(net + "."):
            return True
    return False


def _call_name(node: ast.Call) -> str:
    fn = node.func
    return fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")


def _string_args(node: ast.Call) -> List[str]:
    """调用的字符串字面量参数（含 list/tuple 元素）——只认字面量，不认变量/注释。"""
    out: List[str] = []
    for arg in list(node.args) + [kw.value for kw in node.keywords]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            out.append(arg.value)
        elif isinstance(arg, (ast.List, ast.Tuple)):
            for elt in arg.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    out.append(elt.value)
    return out


def _network_findings(rel: str, tree: ast.AST,
                      allowlisted: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _network_module(alias.name):
                    out.append(_finding(rel, node.lineno, "network_site", "critical",
                                        "import", _snippet(alias.name), allowlisted=allowlisted))
        elif isinstance(node, ast.ImportFrom):
            mod = str(node.module or "")
            if _network_module(mod):
                out.append(_finding(rel, node.lineno, "network_site", "critical",
                                    "from_import", _snippet(mod), allowlisted=allowlisted))
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name in DYNAMIC_IMPORT_CALLS:
                for value in _string_args(node):
                    if _network_module(value):
                        out.append(_finding(rel, node.lineno, "network_site", "critical",
                                            "dynamic_import", _snippet(value),
                                            allowlisted=allowlisted))
            elif name in ("run", "Popen", "call", "check_call", "check_output",
                          "system", "popen"):
                for value in _string_args(node):
                    low = (" " + value.lower() + " ")
                    hit = next((t for t in SHELL_NET_TOKENS if " " + t in low
                                or t in low), "")
                    if hit:
                        out.append(_finding(rel, node.lineno, "network_site", "critical",
                                            "shell_fetch", _snippet(value, 40),
                                            allowlisted=allowlisted))
    return out


def _parse_file(path: str) -> Tuple[Optional[ast.AST], str]:
    try:
        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read()), ""
    except (OSError, UnicodeDecodeError) as exc:
        return None, "不可读：%s" % exc
    except SyntaxError as exc:
        return None, "语法错误，无法静态解析：%s" % exc


def audit_network(root: str = ".", dirs: Sequence[str] = AUDIT_DIRS) -> Dict[str, Any]:
    """AST 静态审计 `core/` 与 `scripts/` 的网络站点 → 报告（`kind=privacy-check`）。

    白名单站点仍**逐条列出**（`allowlisted: true` + `reason`），但不计入 critical；
    白名单条目若无命中（文件删除/调用移除）→ `stale_whitelist` critical（名单不得变黑洞）。
    """
    root = os.path.abspath(root)
    raw = [_norm_rel(t) for t in dirs]
    findings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    files: Dict[str, int] = {}
    for rel_dir in raw:
        abs_dir = os.path.join(root, rel_dir)
        if not os.path.isdir(abs_dir):
            errors.append({"file": rel_dir, "reason": "审计目录不存在",
                           "kind": "undecidable"})
            continue
        for base, dirs_, names in os.walk(abs_dir):
            dirs_[:] = sorted(d for d in dirs_ if d not in SKIP_DIRS)
            for name in sorted(names):
                if not name.endswith(".py"):
                    continue
                abs_path = os.path.join(base, name)
                rel_f = _rel(root, abs_path)
                tree, reason = _parse_file(abs_path)
                if tree is None:
                    errors.append({"file": rel_f, "reason": reason,
                                   "kind": "undecidable"})
                    continue
                found = _network_findings(rel_f, tree, is_allowlisted(rel_f))
                if found:
                    files[rel_f] = len(found)
                findings.extend(found)
    hits_by_file = {f["file"] for f in findings}
    for f in findings:
        reason = NETWORK_ALLOWLIST.get(f["file"])
        if reason and f["kind"] == "network_site":
            f["allowlisted"] = True
            f["reason"] = reason
    for rel_f in sorted(NETWORK_ALLOWLIST):
        if rel_f not in hits_by_file:
            findings.append(_finding(rel_f, 0, "stale_whitelist", "critical", "stale",
                                     "白名单条目无命中", allowlisted=False))
    critical = sum(1 for f in findings
                   if f["severity"] == "critical" and not f["allowlisted"])
    summary = {"critical": critical,
               "allowlisted": sum(1 for f in findings if f["allowlisted"]),
               "stale": sum(1 for f in findings if f["kind"] == "stale_whitelist"),
               "undecidable": len(errors), "findings": len(findings)}
    code = 2 if summary["undecidable"] else (1 if critical else 0)
    return {"kind": CHECK_KIND, "schema": SCHEMA, "root": _rel(root, root),
            "dirs": raw, "files_with_network": sorted(files),
            "allowlist": [{"file": k, "reason": v} for k, v in sorted(NETWORK_ALLOWLIST.items())],
            "excluded": [{"dir": k, "reason": v} for k, v in sorted(EXCLUDED_SURFACES.items())],
            "findings": findings, "errors": errors, "summary": summary,
            "exit": code, "ok": code == 0}


# ------------------------------------------------------------------ 报告渲染
def _render_findings(report: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for f in report.get("findings") or []:
        tag = "WHITELIST" if f.get("allowlisted") else (
            "CRITICAL" if f["severity"] == "critical" else "WARN")
        reason = "（理由：%s）" % f["reason"] if f.get("reason") else ""
        lines.append("  [%s] %s:%d %s — %s%s"
                     % (tag, f["file"], f["line"], f["kind"],
                        f["masked_evidence"], reason))
        if not f.get("allowlisted") or f["kind"] == "stale_whitelist":
            lines.append("        修复：%s" % f["fix"])
    for item in report.get("errors") or []:
        lines.append("  [不可判定] %s — %s" % (item.get("file"), item.get("reason")))
    return lines


def render_scan_text(report: Dict[str, Any]) -> str:
    s = report.get("summary") or {}
    lines = ["== 隐私扫描（内容面：PII / 本机路径 / 凭据）==",
             "  扫描 %d 件 / %d 字节 · critical %d · warn %d · 不可判定 %d"
             % ((report.get("scanned") or {}).get("files", 0),
                (report.get("scanned") or {}).get("bytes", 0),
                s.get("critical", 0), s.get("warn", 0), s.get("undecidable", 0)),
             "  路径：%s（根：%s）"
             % ("、".join(report.get("paths") or []), report.get("root") or ".")]
    for item in report.get("skipped") or []:
        lines.append("  [白名单] %s — %s（不计入判定）"
                     % (item.get("file"), item.get("reason")))
    lines.extend(_render_findings(report))
    if report.get("ok"):
        lines.append("  ✓ 无 critical（退出码 0）")
    elif int(report.get("exit") or 0) == 2:
        lines.append("  ? 存在不可判定件（退出码 2）——先修复可读性再重扫")
    else:
        lines.append("  ✗ 存在 critical（退出码 1）——按上方修复指引处置后重扫")
    return "\n".join(lines)


def render_check_text(report: Dict[str, Any]) -> str:
    s = report.get("summary") or {}
    lines = ["== air-gap 静态审计（代码面：core/ 与 scripts/ 的网络站点）==",
             "  审计 %s · 含网络站点文件 %d · critical %d · 白名单 %d · 陈旧 %d · 不可判定 %d"
             % ("、".join(report.get("dirs") or []), len(report.get("files_with_network") or []),
                s.get("critical", 0), s.get("allowlisted", 0), s.get("stale", 0),
                s.get("undecidable", 0))]
    lines.extend(_render_findings(report))
    lines.append("  白名单（逐条理由）：")
    for row in report.get("allowlist") or []:
        lines.append("    · %s — %s" % (row["file"], row["reason"]))
    lines.append("  不在审计面（边界如实声明）：")
    for row in report.get("excluded") or []:
        lines.append("    · %s — %s" % (row["dir"], row["reason"]))
    if report.get("ok"):
        lines.append("  ✓ 无未登记网络站点（退出码 0）")
    elif int(report.get("exit") or 0) == 2:
        lines.append("  ? 存在不可判定件（退出码 2）——先修复可读性再重跑")
    else:
        lines.append("  ✗ 存在未登记网络站点或陈旧白名单（退出码 1）")
    return "\n".join(lines)
