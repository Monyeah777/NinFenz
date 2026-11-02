"""DOCX / Markdown 标识写入（TC260 文本类载体）。

作者：impl（DSH agent）· 2026-11-02
依据：`/tmp/docformats-spec.md` A / C 节。

纪律：
- 不修改 metadata.py / checker.py / cli.py（读取面由 Lead 落地）；
- 纯标准库（zipfile / xml.etree / json / re）；
- 写面失败抛 ValueError（带说明），不裸崩；
- DOCX：只重写三个必须改的 entry（docProps/custom.xml、[Content_Types].xml、
  _rels/.rels），其它 entry 的**解压后字节与相对顺序保持不变**；
- Markdown：文件头 HTML 注释块 `<!-- AIGC:{JSON} -->`，替换旧块、保留正文、UTF-8 无 BOM。

已知边界（详见函数 docstring）：
- DOCX 的「内容字节」在 metadata.content_bytes_for 里按整文件（DFT）取，写后
  整文件变化 ⇒ 若按写前内容算 Binding，C2 会失配（需 Lead 集成时用同口径，
  例如只对「除 custom.xml 外的 entry 拼接」取内容）；
- 不支持带数字签名的 DOCX（改 custom.xml 会使签名失效）、不处理 .docm/vbaProject；
- Markdown 仅支持 UTF-8；JSON 里含 `-->` 会提前关闭注释（拒绝写入）。
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------- 常量
_CUSTOM_PART = "docProps/custom.xml"
_CT_PART = "[Content_Types].xml"
_RELS_PART = "_rels/.rels"
_DOC_PART = "word/document.xml"

_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CUSTOM_NS = ("http://schemas.openxmlformats.org/officeDocument/2006/"
              "custom-properties")
_VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
_FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"
_CUSTOM_CT = ("application/vnd.openxmlformats-officedocument."
              "custom-properties+xml")
_CUSTOM_REL = ("http://schemas.openxmlformats.org/officeDocument/2006/"
               "relationships/custom-properties")
_REL_ID_HEAD = "rIdAigc"
_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'


def _q(ns: str, tag: str) -> str:
    return "{%s}%s" % (ns, tag)


def _serialize(root) -> bytes:
    """序列化为 OOXML 习惯的 XML（声明 + LF，UTF-8）。"""
    body = ET.tostring(root, encoding="unicode")
    return (_XML_DECL + body).encode("utf-8")


def _check_json_text(json_text) -> object:
    """校验 json_text 是合法 JSON 文本；返回解析后的对象。"""
    if not isinstance(json_text, str) or not json_text.strip():
        raise ValueError("json_text 不得为空（修复指引：传标识 JSON 文本）")
    try:
        return json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)


# ---------------------------------------------------------------- DOCX 读
def _read_docx(path):
    """读 zip → (infos, {name: bytes})；坏 zip / 缺必需件抛 ValueError。"""
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            names = [i.filename for i in infos]
            if not infos:
                raise ValueError("zip 为空（不是 DOCX）")
            if len(names) != len(set(names)):
                raise ValueError("zip 含重复 entry（修复指引：重建 DOCX）")
            data = {i.filename: zf.read(i) for i in infos}
    except zipfile.BadZipFile as exc:
        raise ValueError("不是合法 DOCX（zip 解析失败：%s）" % exc)
    except (OSError, RuntimeError) as exc:
        # RuntimeError：加密/不支持的压缩方式等（zipfile 的失败面）
        raise ValueError("无法读取 DOCX：%s（%s）" % (path, exc))
    for need in (_CT_PART, _RELS_PART, _DOC_PART):
        if need not in data:
            raise ValueError("不是完整 DOCX（缺 %s）" % need)
    return infos, data


# ---------------------------------------------------------------- DOCX 改
def _parse_xml(blob: bytes, what: str):
    try:
        return ET.fromstring(blob)
    except ET.ParseError as exc:
        raise ValueError("%s 不是合法 XML（%s）" % (what, exc))


def _build_custom_xml(existing: bytes | None, json_text: str) -> bytes:
    """生成/更新 docProps/custom.xml：保留其它 property，替换/追加 AIGC。"""
    ET.register_namespace("", _CUSTOM_NS)
    ET.register_namespace("vt", _VT_NS)
    if existing is None:
        root = ET.Element(_q(_CUSTOM_NS, "Properties"))
    else:
        root = _parse_xml(existing, _CUSTOM_PART)
        if root.tag != _q(_CUSTOM_NS, "Properties"):
            raise ValueError("docProps/custom.xml 根元素不是 Properties")
    props = [el for el in list(root) if el.tag == _q(_CUSTOM_NS, "property")]
    kept_pids = []
    for prop in props:
        if prop.get("name") == "AIGC":
            root.remove(prop)                 # 旧 AIGC：替换（保留其它 property）
            continue
        pid = str(prop.get("pid") or "")
        if pid.isdigit():
            kept_pids.append(int(pid))
    # 已被替换的 AIGC 的 pid 不参与计算 ⇒ 同 JSON 二次写仍是同一 pid（幂等）
    new_pid = max([1] + kept_pids) + 1
    prop = ET.SubElement(root, _q(_CUSTOM_NS, "property"), {
        "fmtid": _FMTID, "pid": str(new_pid), "name": "AIGC"})
    text_el = ET.SubElement(prop, _q(_VT_NS, "lpwstr"))
    text_el.text = json_text                  # ElementTree 负责 XML 转义
    return _serialize(root)


def _build_content_types(existing: bytes) -> bytes | None:
    """确保 [Content_Types].xml 有 custom.xml 的 Override；未变返回 None。"""
    ET.register_namespace("", _CT_NS)
    root = _parse_xml(existing, _CT_PART)
    if root.tag != _q(_CT_NS, "Types"):
        raise ValueError("[Content_Types].xml 根元素不是 Types")
    target = None
    for el in root:
        if el.tag != _q(_CT_NS, "Override"):
            continue
        if (el.get("PartName") or "").lower() == ("/" + _CUSTOM_PART).lower():
            target = el
            break
    if target is not None:
        if target.get("ContentType") == _CUSTOM_CT:
            return None
        target.set("ContentType", _CUSTOM_CT)
    else:
        ET.SubElement(root, _q(_CT_NS, "Override"), {
            "PartName": "/" + _CUSTOM_PART, "ContentType": _CUSTOM_CT})
    return _serialize(root)


def _build_rels(existing: bytes) -> bytes | None:
    """确保 _rels/.rels 有 custom-properties 关系；未变返回 None。"""
    ET.register_namespace("", _REL_NS)
    root = _parse_xml(existing, _RELS_PART)
    if root.tag != _q(_REL_NS, "Relationships"):
        raise ValueError("_rels/.rels 根元素不是 Relationships")
    used_ids = set()
    for el in root:
        if el.tag != _q(_REL_NS, "Relationship"):
            continue
        used_ids.add(el.get("Id") or "")
        if el.get("Type") == _CUSTOM_REL:
            if el.get("Target") == _CUSTOM_PART:
                return None
            el.set("Target", _CUSTOM_PART)
            return _serialize(root)
    rid = _REL_ID_HEAD + "1"
    n = 1
    while rid in used_ids:
        n += 1
        rid = "%s%d" % (_REL_ID_HEAD, n)
    ET.SubElement(root, _q(_REL_NS, "Relationship"), {
        "Id": rid, "Type": _CUSTOM_REL, "Target": _CUSTOM_PART})
    return _serialize(root)


# ---------------------------------------------------------------- DOCX 写
def _rewrite_zip(infos, data, replacements) -> bytes:
    """按原顺序重写 zip；replacements 覆盖指定 entry，新增项追加到末尾。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for info in infos:
            name = info.filename
            payload = replacements.get(name, data[name])
            zi = zipfile.ZipInfo(name, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zi.comment = info.comment
            zf.writestr(zi, payload)
        for name, payload in replacements.items():
            if name in data:
                continue
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, payload)
    return buf.getvalue()


def inject_docx(path, json_text) -> None:
    """把 json_text 写入 DOCX 的 docProps/custom.xml（custom property AIGC）。

    - 保留其它 entry 的解压后字节与原顺序；只重写 custom.xml / [Content_Types].xml /
      _rels/.rels 三个必须改的 entry；
    - 已有 custom property 保留；同名 AIGC 替换（不重复）；
    - 同 JSON 二次写幂等（三处都不变则**不重写文件**）；坏 zip / 缺必需件 ValueError。
    """
    _check_json_text(json_text)
    infos, data = _read_docx(path)
    repl = {}
    custom = _build_custom_xml(data.get(_CUSTOM_PART), json_text)
    if data.get(_CUSTOM_PART) != custom:
        repl[_CUSTOM_PART] = custom
    ct = _build_content_types(data[_CT_PART])
    if ct is not None:
        repl[_CT_PART] = ct
    rels = _build_rels(data[_RELS_PART])
    if rels is not None:
        repl[_RELS_PART] = rels
    if not repl:
        return                                # 幂等：无变化不重写
    Path(path).write_bytes(_rewrite_zip(infos, data, repl))


# ---------------------------------------------------------------- Markdown
_MD_BLOCK_RE = re.compile(r"\A\s*<!--\s*AIGC:.*?-->\s*(?:\r?\n)?")


def _read_markdown(path) -> str:
    """读 UTF-8 文本（剥 BOM）；非 UTF-8 抛 ValueError。"""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError("无法读取文件：%s（%s）" % (path, exc))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("不是 UTF-8 文本（%s）" % exc)
    return text


def _md_json_line(obj, json_text: str) -> str:
    """HTML 注释必须单行：多行 JSON 压成紧凑形式；`-->` 会提前闭合注释（拒绝）。"""
    if "-->" in json_text:
        raise ValueError("JSON 含 '-->'，无法安全放进 HTML 注释"
                         "（修复指引：转义或改用 sidecar）")
    if "\n" in json_text or "\r" in json_text:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return json_text


def inject_markdown(path, json_text) -> None:
    """在 Markdown 文件头写入/替换 `<!-- AIGC:{JSON} -->`。

    - 块始终是**第一行**；替换已有的 AIGC 注释块，保留正文原文；
    - 幂等（同 JSON 二次写不改文件）；输出 UTF-8 无 BOM；
    - 非 UTF-8 / JSON 非法 / JSON 含 `-->` → ValueError。
    """
    obj = _check_json_text(json_text)
    text = _read_markdown(path)
    body = _MD_BLOCK_RE.sub("", text, count=1)
    block = "<!-- AIGC:%s -->\n" % _md_json_line(obj, json_text)
    new_text = block + body
    if new_text == text:
        return                                # 幂等
    Path(path).write_bytes(new_text.encode("utf-8"))
