"""安全护栏（CONTRACT §3/§6）。

Python 消费面不信任输入：即使 Rust 核心是最终权威，CLI 在解包/解析/分享前也必须
fail-closed。负例见 app/tests/test_security_negative.py。

错误码口径：
- NF-SEC-001 zip slip（绝对路径/../反斜杠/重复条目）
- NF-SEC-002 symlink/junction/硬链
- NF-SEC-003 解包超限（条目数/总量/单文件/压缩比/嵌套层数/加密/不支持压缩算法）
- NF-SEC-004 YAML 别名爆炸 / YAML 深度超限
- NF-IMP-003 JSON 深度/字节超限（limits.json json 段）
- NF-IMP-001 导入文本不是合法 JSON/YAML
- NF-EXP-002 导出/落盘路径越界
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any

from .canonical import JsonParseError, loads_strict
from .errors import AppError
from .paths import limits as _load_limits

# Windows 保留设备名（任一路径段的主名命中即拒）
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")

DEFAULT_LIMITS = {
    "json": {"max_depth": 64, "max_bytes": 67108864},
    "yaml": {"max_alias_expansions": 1000, "max_depth": 64},
    "zip": {
        "max_entries": 5000,
        "max_total_unpacked_bytes": 536870912,
        "max_file_bytes": 67108864,
        "max_compression_ratio": 100,
        "max_nesting": 1,
        "allow_symlink": False,
    },
}


def limits(override: dict | None = None) -> dict:
    """默认上限（limits.json 为准，读不到用内置同名值）+ 显式覆盖（测试/调用方）。"""
    merged = {k: dict(v) for k, v in DEFAULT_LIMITS.items()}
    try:
        on_disk = _load_limits()
    except (OSError, ValueError):
        on_disk = {}
    for section, values in on_disk.items():
        if isinstance(values, dict):
            merged.setdefault(section, {}).update(values)
    for section, values in (override or {}).items():
        if isinstance(values, dict):
            merged.setdefault(section, {}).update(values)
    return merged


# ---------------------------------------------------------------- 路径

def check_rel_path(path: str, *, code: str = "NF-PCK-003") -> str:
    """校验 POSIX 相对路径：禁绝对/盘符/UNC/.././空段/反斜杠/控制字符/保留设备名。"""
    if not isinstance(path, str) or path == "":
        raise AppError(code, message="路径为空或不是字符串", fix="改用包内相对路径")
    if "\x00" in path:
        raise AppError(code, message="路径含 NUL 字节", fix="改用包内相对路径")
    if _CTRL_RE.search(path):
        raise AppError(code, message=f"路径含控制字符: {path!r}", fix="改用可打印相对路径")
    if "\\" in path:
        raise AppError(code, message=f"路径含反斜杠（只允许 POSIX 分隔符）: {path}", fix="改用 / 分隔的相对路径")
    if path.startswith("/") or path.startswith("//"):
        raise AppError(code, message=f"路径是绝对路径: {path}", fix="改用包内相对路径")
    if _DRIVE_RE.match(path):
        raise AppError(code, message=f"路径含盘符: {path}", fix="改用包内相对路径")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise AppError(code, message=f"路径含空段/. /..: {path}", fix="改用规范化相对路径")
    for part in parts:
        stem = part.split(".")[0].upper()
        if stem in _WINDOWS_RESERVED:
            raise AppError(code, message=f"路径含保留设备名: {part}", fix="改名")
    return path


def safe_join(base: Path, rel: str, *, code: str = "NF-EXP-002") -> Path:
    """相对路径拼接并钉死 base（防穿越）；返回 resolve 后的目标。"""
    check_rel_path(rel, code=code)
    root = Path(base).resolve()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise AppError(code, message=f"目标路径越界: {rel}", fix="改用包内相对路径")
    return target


# ---------------------------------------------------------------- zip

def _entry_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == 0o120000


def _check_zip_name(name: str) -> None:
    if "\x00" in name:
        raise AppError("NF-SEC-001", message="zip entry 名含 NUL", fix="拒绝该包")
    if _CTRL_RE.search(name):
        raise AppError("NF-SEC-001", message=f"zip entry 名含控制字符: {name!r}", fix="拒绝该包")
    if "\\" in name:
        raise AppError("NF-SEC-001", message=f"zip slip：反斜杠 entry 名: {name}", fix="拒绝该包")
    stripped = name[:-1] if name.endswith("/") else name
    if not stripped:
        raise AppError("NF-SEC-001", message="zip 存在空 entry 名", fix="拒绝该包")
    if stripped.startswith("/") or stripped.startswith("//"):
        raise AppError("NF-SEC-001", message=f"zip slip：绝对路径 entry: {name}", fix="拒绝该包")
    if _DRIVE_RE.match(stripped):
        raise AppError("NF-SEC-001", message=f"zip slip：盘符 entry: {name}", fix="拒绝该包")
    for part in stripped.split("/"):
        if part in ("..", "."):
            raise AppError("NF-SEC-001", message=f"zip slip：entry 含 ..: {name}", fix="拒绝该包")
        stem = part.split(".")[0].upper()
        if stem in _WINDOWS_RESERVED:
            raise AppError("NF-SEC-001", message=f"zip entry 含保留设备名: {name}", fix="拒绝该包")


def _inspect_zip_obj(zf: zipfile.ZipFile, zlim: dict, *, depth: int, acc: dict) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    for info in zf.infolist():
        name = info.filename
        _check_zip_name(name)
        is_dir = name.endswith("/")
        if not is_dir:
            if name in seen:
                raise AppError("NF-SEC-001", message=f"zip entry 重名: {name}", fix="拒绝该包或去重")
            seen.add(name)
        if _entry_is_symlink(info) and not zlim.get("allow_symlink", False):
            raise AppError("NF-SEC-002", message=f"zip 含符号链接: {name}", fix="重打包为普通文件")
        if info.flag_bits & 0x1:
            raise AppError("NF-SEC-003", message=f"zip 加密条目不支持: {name}", fix="解压后重打包")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise AppError(
                "NF-SEC-003",
                message=f"zip 压缩算法不支持（method={info.compress_type}）: {name}",
                fix="用 store/deflate 重打包",
            )
        if is_dir:
            entries.append({"name": name, "size": 0, "dir": True})
            continue
        size = int(info.file_size)
        comp = int(info.compress_size)
        if size > zlim["max_file_bytes"]:
            raise AppError("NF-SEC-003", message=f"zip 单文件超限: {name} size={size}", fix="拆分或重打包")
        ratio_cap = int(zlim["max_compression_ratio"])
        if size > 0:
            if comp <= 0:
                raise AppError("NF-SEC-003", message=f"zip 压缩比异常（compressed=0）: {name}", fix="拒绝该包")
            if size / comp > ratio_cap:
                raise AppError(
                    "NF-SEC-003",
                    message=f"zip 压缩比超限（{size}/{comp} > {ratio_cap}）: {name}",
                    fix="拒绝该包（疑似 zip bomb）",
                )
        acc["entries"] += 1
        if acc["entries"] > zlim["max_entries"]:
            raise AppError("NF-SEC-003", message="zip 条目数超限", fix="拆分或重打包")
        acc["total"] += size
        if acc["total"] > zlim["max_total_unpacked_bytes"]:
            raise AppError("NF-SEC-003", message="zip 解压总量超限", fix="拆分或重打包")
        entries.append({"name": name, "size": size, "dir": False})

        if name.lower().endswith(".zip") and depth >= zlim["max_nesting"]:
            raise AppError("NF-SEC-003", message=f"zip 嵌套层数超限: {name}", fix="只允许一层嵌套")
        if name.lower().endswith(".zip"):
            try:
                raw = zf.read(info)
            except (zipfile.BadZipFile, OSError) as exc:
                raise AppError("NF-SEC-001", message=f"内层 zip 无法读取: {name}: {exc}", fix="拒绝该包") from exc
            entries.extend(_inspect_zip_bytes(raw, zlim, depth=depth + 1, acc=acc))
    return entries


def _inspect_zip_bytes(data: bytes, lim: dict, *, depth: int, acc: dict) -> list[dict]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return _inspect_zip_obj(zf, lim, depth=depth, acc=acc)
    except zipfile.BadZipFile as exc:
        raise AppError("NF-SEC-001", message=f"坏 zip: {exc}", fix="拒绝该包") from exc


def inspect_zip_entries(source: bytes | str | Path, *, lim: dict | None = None) -> list[dict]:
    """只读中央目录检查 zip（不解包到磁盘）；返回入口清单。"""
    zlim = limits(lim)["zip"]
    acc = {"entries": 0, "total": 0}
    if isinstance(source, (bytes, bytearray)):
        return _inspect_zip_bytes(bytes(source), zlim, depth=0, acc=acc)
    path = Path(source)
    if not path.is_file():
        raise AppError("NF-E-004", message=f"文件不存在: {path}", fix="检查路径")
    try:
        with zipfile.ZipFile(path) as zf:
            return _inspect_zip_obj(zf, zlim, depth=0, acc=acc)
    except zipfile.BadZipFile as exc:
        raise AppError("NF-SEC-001", message=f"坏 zip: {exc}", fix="拒绝该包") from exc


def extract_zip_safe(source: bytes | Path, out_dir: Path, *, lim: dict | None = None) -> list[str]:
    """检查通过后解包到 out_dir（每个目标再走 safe_join，双保险）。"""
    inspect_zip_entries(source, lim=lim)  # 先 fail-closed 检查（返回值仅用于记录）
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    opener = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else Path(source)
    with zipfile.ZipFile(opener) as zf:
        for info in zf.infolist():
            if info.filename.endswith("/"):
                continue
            target = safe_join(out_dir, info.filename, code="NF-SEC-001")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)
            written.append(info.filename)
    return written


# ---------------------------------------------------------------- JSON / YAML

def parse_json_secure(data: bytes | str, *, lim: dict | None = None) -> Any:
    """导入用 JSON：限字节/深度；语法错 → NF-IMP-001，超限 → NF-IMP-003。"""
    jlim = limits(lim)["json"]
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    if len(raw) > int(jlim["max_bytes"]):
        raise AppError("NF-IMP-003", message="JSON 字节数超限", fix="见 app/schema/limits.json json.max_bytes")
    try:
        return loads_strict(raw, max_depth=int(jlim["max_depth"]))
    except JsonParseError as exc:
        text = str(exc)
        code = "NF-IMP-003" if ("深度" in text or "浮点" in text or "NaN" in text or "重复键" in text) else "NF-IMP-001"
        raise AppError(code, message=f"JSON 解析被拒: {text}", fix="换合法 JSON 或提高显式上限并记录") from exc


def loads_yaml_secure(data: bytes | str, *, lim: dict | None = None) -> Any:
    """YAML：别名展开 ≤ 1000、深度 ≤ 64；超限 → NF-SEC-004；语法错 → NF-IMP-001。"""
    import yaml

    ylim = limits(lim)["yaml"]
    max_alias = int(ylim["max_alias_expansions"])
    max_depth = int(ylim["max_depth"])
    text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data)

    class _TooBig(Exception):
        pass

    class _TooDeep(Exception):
        pass

    def children(node: Any):
        if isinstance(node, yaml.SequenceNode):
            return list(node.value)
        if isinstance(node, yaml.MappingNode):
            out = []
            for key, value in node.value:
                out.append(key)
                out.append(value)
            return out
        return []

    def expand(node: Any, depth: int) -> int:
        if depth > max_depth:
            raise _TooDeep()
        total = 1
        for child in children(node):
            total += expand(child, depth + 1)
            if total > max_alias:
                raise _TooBig()
        return total

    loader = yaml.SafeLoader(text)
    try:
        try:
            node = loader.get_single_node()
            if node is None:
                return None
            try:
                expand(node, 1)
            except _TooBig:
                raise AppError(
                    "NF-SEC-004",
                    message=f"YAML 别名展开超过 {max_alias}（疑似 alias bomb）",
                    fix="改用 JSON 或精简 YAML",
                )
            except _TooDeep:
                raise AppError("NF-SEC-004", message=f"YAML 深度超过 {max_depth}", fix="精简 YAML 层级")
            return loader.construct_document(node)
        except yaml.YAMLError as exc:
            raise AppError("NF-IMP-001", message=f"YAML 解析失败: {exc}", fix="检查 YAML 语法")
        except RecursionError as exc:
            raise AppError("NF-SEC-004", message="YAML 深度/递归超限", fix="精简 YAML") from exc
    finally:
        loader.dispose()


# ---------------------------------------------------------------- 分享脱敏

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_WIN_HOME_RE = re.compile(r"[A-Za-z]:\\+Users\\+[^\\\s\"'<>]+", re.IGNORECASE)
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'<>|]+")
_NIX_HOME_RE = re.compile(r"/(?:home|Users)/[^/\s\"'<>]+")
_NIX_PATH_RE = re.compile(r"(?<![\w:/.~-])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+")

SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]{16,}"),
}


def sanitize_text(text: str, *, repo_paths: tuple[Path, ...] = ()) -> tuple[str, list[dict]]:
    """脱敏：绝对路径/家目录/用户名/邮箱/密钥模式。返回 (文本, 掩码记录)。"""
    masks: list[dict] = []

    def apply(pattern: re.Pattern, replacement: str, kind: str, value: str) -> str:
        new, count = pattern.subn(replacement, value)
        if count:
            masks.append({"kind": kind, "count": count})
        return new

    for repo in repo_paths:
        for raw in {str(repo), str(repo).replace("\\", "/")}:
            if raw and raw in text:
                count = text.count(raw)
                text = text.replace(raw, "<repo>")
                masks.append({"kind": "repo_path", "count": count})

    text = apply(_EMAIL_RE, "<email>", "email", text)
    text = apply(_WIN_HOME_RE, "<home>", "home", text)
    text = apply(_NIX_HOME_RE, "<home>", "home", text)
    text = apply(_WIN_PATH_RE, "<path>", "path", text)
    text = apply(_NIX_PATH_RE, "<path>", "path", text)
    for kind, pattern in SECRET_PATTERNS.items():
        text = apply(pattern, "<secret>", kind, text)
    return text, masks


def find_sensitive(text: str) -> list[str]:
    """脱敏后仍命中的敏感模式（fail-closed 依据）。"""
    hits = []
    if _EMAIL_RE.search(text):
        hits.append("email")
    for kind, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            hits.append(kind)
    return hits


def sanitize_obj(obj: Any, *, repo_paths: tuple[Path, ...] = ()) -> tuple[Any, list[dict]]:
    """递归脱敏 JSON 值（键不改，值改）。"""
    masks: list[dict] = []

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            out, m = sanitize_text(value, repo_paths=repo_paths)
            masks.extend(m)
            return out
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        return value

    return walk(obj), masks


def assert_share_safe(text: str) -> None:
    hits = find_sensitive(text)
    if hits:
        raise AppError(
            "NF-E-002",
            message=f"分享文本仍含敏感模式（{', '.join(sorted(set(hits)))}），fail-closed",
            fix="手动删除路径/邮箱/密钥后再分享；或改用 nf-app share 生成的脱敏文本",
        )
