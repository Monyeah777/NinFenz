"""xmind / posm / posf / UOF 标识写入（zip 容器类载体）。

作者：impl（DSH agent）· 2026-11-02
依据：`/tmp/zipformats-spec.md`（A–D 节 + 公共要求）。

载体约定（写入侧）：
- xmind：zip 内 `metadata.json`，设 `{"AIGC": "<json_text 字符串>"}`（字符串值，
  保证读回的是**同一字面串**；不存在则创建 `{}` 再写）；
- posm / posf：zip 内 `meta.json`，同样写字符串值；
- UOF：zip 内 `_meta/meta.xml`，插入/替换 `<meta:AIGC>{json_text}</meta:AIGC>`
  （JSON 由 XML 序列化转义；保留其它元素与命名空间）；
- 其它 entry 的解压后字节与相对顺序不变；zip 重打包固定 date_time=(2026,1,1,0,0,0)；
- 原子写（同目录临时件 + os.replace，保留权限位）；坏 zip / 坏 JSON / 缺必要件 → ValueError。

读取面在 metadata.py（Lead 负责），结构与本模块一一对应。
"""

from __future__ import annotations

import io
import json
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

#: zip 重打包的固定时间戳（确定性产物；跨机/跨次写逐字节可比）。
DEFAULT_DATE_TIME = (2026, 1, 1, 0, 0, 0)

#: 三种 JSON 元数据载体的目标 entry。
_META_JSON = {
    "xmind": "metadata.json",
    "posm": "meta.json",
    "posf": "meta.json",
}
#: 各容器「除目标 entry 外」必须存在的完整性件（缺则无法安全改写）。
_REQUIRED = {
    "xmind": ("content.json",),
    "posm": ("content.xml",),
    "posf": ("pages/page_1.xml",),
    "uof": ("document.xml",),
}
_UOF_PART = "_meta/meta.xml"
_UOF_NS = "http://schemas.uof.org/cn/2009/meta"
_XML_DECL = '<?xml version="1.0" encoding="UTF-8"?>\n'
_NS_DECL_RE = re.compile(rb'xmlns:([A-Za-z_][\w.\-]*)="([^"]+)"')


# ---------------------------------------------------------------- 基础
def _check_json_text(json_text) -> object:
    """校验 json_text 是合法 JSON 文本；返回解析后的对象。"""
    if not isinstance(json_text, str) or not json_text.strip():
        raise ValueError("json_text 不得为空（修复指引：传标识 JSON 文本）")
    try:
        return json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)


def _read_zip(path, kind: str):
    """读 zip → (infos, {name: bytes})；坏 zip / 重复 entry / 缺必要件抛 ValueError。"""
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if not infos:
                raise ValueError("zip 为空（不是 %s 容器）" % kind)
            names = [i.filename for i in infos]
            if len(names) != len(set(names)):
                raise ValueError("zip 含重复 entry（修复指引：重建容器）")
            data = {i.filename: zf.read(i) for i in infos}
    except zipfile.BadZipFile as exc:
        raise ValueError("不是合法 %s（zip 解析失败：%s）" % (kind, exc))
    except (OSError, RuntimeError) as exc:
        raise ValueError("无法读取 %s：%s（%s）" % (kind, path, exc))
    for need in _REQUIRED[kind]:
        if need not in data:
            raise ValueError("不是完整 %s（缺 %s）" % (kind, need))
    return infos, data


def _atomic_write(path, data: bytes) -> None:
    """原子写：同目录临时件 + os.replace；保留原文件权限位；失败清理临时件。"""
    p = Path(path)
    try:
        mode = stat.S_IMODE(p.stat().st_mode)
    except OSError as exc:
        raise ValueError("无法读取目标文件状态：%s（%s）" % (path, exc))
    fd, tmp = tempfile.mkstemp(prefix="." + p.name + ".", suffix=".tmp",
                               dir=str(p.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, p)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise ValueError("写入失败：%s（%s）" % (path, exc))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _rewrite_zip(infos, data, replacements) -> bytes:
    """按原顺序重写 zip；固定 date_time；只替换/追加指定 entry。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for info in infos:
            name = info.filename
            payload = replacements.get(name, data[name])
            zi = zipfile.ZipInfo(name, date_time=DEFAULT_DATE_TIME)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zi.comment = info.comment
            zf.writestr(zi, payload)
        for name, payload in replacements.items():
            if name in data:
                continue
            zi = zipfile.ZipInfo(name, date_time=DEFAULT_DATE_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, payload)
    return buf.getvalue()


def _apply(path, kind: str, replacements) -> None:
    """读 zip → 重写（无变化则不动文件）→ 原子落盘。"""
    infos, data = _read_zip(path, kind)
    changed = {n: b for n, b in replacements.items() if data.get(n) != b}
    if not changed:
        return                                  # 幂等：内容一致不重写
    _atomic_write(path, _rewrite_zip(infos, data, changed))


# ---------------------------------------------------------------- JSON 载体
def _inject_json_meta(path, kind: str, json_text) -> None:
    """xmind/posm/posf：在 metadata.json / meta.json 里写 AIGC 字符串值。"""
    _check_json_text(json_text)
    entry = _META_JSON[kind]
    infos, data = _read_zip(path, kind)
    raw = data.get(entry)
    if raw is None:
        doc = {}
    else:
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("%s 不是合法 JSON：%s" % (entry, exc))
        if not isinstance(doc, dict):
            raise ValueError("%s 顶层不是 JSON 对象（修复指引：重建容器）"
                             % entry)
    doc["AIGC"] = json_text                     # 字符串值：读回同一字面串
    new = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    _apply(path, kind, {entry: new})


def inject_xmind(path, json_text) -> None:
    """xmind：写入 zip 内 metadata.json 的 AIGC 字符串键（保留其它键）。"""
    _inject_json_meta(path, "xmind", json_text)


def inject_posm(path, json_text) -> None:
    """posm：写入 zip 内 meta.json 的 AIGC 字符串键（保留其它键）。"""
    _inject_json_meta(path, "posm", json_text)


def inject_posf(path, json_text) -> None:
    """posf：写入 zip 内 meta.json 的 AIGC 字符串键（保留其它键）。"""
    _inject_json_meta(path, "posf", json_text)


# ---------------------------------------------------------------- UOF
def _capture_namespaces(raw: bytes) -> list:
    """从原 XML 里抓 xmlns:PREFIX 声明，序列化时保持原前缀。"""
    return [(m.group(1).decode("ascii"), m.group(2).decode("utf-8"))
            for m in _NS_DECL_RE.finditer(raw)]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _remove_named(root, name: str) -> None:
    """移除所有 local name == name 的子孙元素（保留其它元素）。"""
    parents = {child: parent for parent in root.iter() for child in parent}
    for el in list(root.iter()):
        if el is root or _local(el.tag) != name:
            continue
        parent = parents.get(el)
        if parent is not None:
            parent.remove(el)


def inject_uof(path, json_text) -> None:
    """UOF：在 zip 内 _meta/meta.xml 插入/替换 `<meta:AIGC>{JSON}</meta:AIGC>`。

    - 保留其它子元素与命名空间（含原前缀）；
    - 缺失 _meta/meta.xml 时创建最小 `<meta:Meta xmlns:meta="…"/>`；
    - 缺 document.xml / 坏 zip / 坏 JSON / 坏 meta.xml → ValueError。
    """
    _check_json_text(json_text)
    infos, data = _read_zip(path, "uof")
    raw = data.get(_UOF_PART)
    if raw is None:
        raw = ('%s<meta:Meta xmlns:meta="%s"/>'
               % (_XML_DECL, _UOF_NS)).encode("utf-8")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("%s 不是合法 XML：%s" % (_UOF_PART, exc))
    if _local(root.tag) != "Meta":
        raise ValueError("%s 根元素不是 Meta（修复指引：重建容器）"
                         % _UOF_PART)
    for prefix, uri in _capture_namespaces(raw):
        ET.register_namespace(prefix, uri)
    ET.register_namespace("meta", _UOF_NS)
    _remove_named(root, "AIGC")
    elem = ET.SubElement(root, "{%s}AIGC" % _UOF_NS)
    elem.text = json_text                       # ElementTree 负责 XML 转义
    body = ET.tostring(root, encoding="unicode")
    new = (_XML_DECL + body).encode("utf-8")
    _apply(path, "uof", {_UOF_PART: new})
