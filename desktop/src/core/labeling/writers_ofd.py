"""OFD 标识写入（GB/T 33190 OFD 容器；TC260 指南「CustomDatas/CustomData」）。

载体
----
OFD 是 zip 容器。本写入器落两个位置：
1. **新增** `CustomDatas/AIGC.xml`（UTF-8）：
   `<CustomData xmlns="http://www.ofdspec.org/2016" Name="AIGC"
    Version="1.0"><Content>JSON(XML 转义)</Content></CustomData>`
2. **仅在 `OFD.xml` 已存在 `<CustomDatas>` 节时**，在该节内登记
   `<CustomData Name="AIGC" Location="CustomDatas/AIGC.xml"/>`；
   没有该节则**不改 OFD.xml 一个字节**（只加 zip entry）。

纪律
----
- 其它 zip entry 的**解压后字节与顺序**一律不变（含目录 entry）；
- 幂等：同一 `json_text` 二次写 → 不重复登记、`CustomDatas/AIGC.xml`
  原位替换为相同内容，zip 逐字节稳定；
- 坏 zip / 缺 `OFD.xml` / `OFD.xml` 非 UTF-8 / `<CustomDatas>` 未闭合 →
  `ValueError`（带说明），不静默写坏包；
- 写盘走「同目录临时件 + os.replace」原子替换（保留权限位）。

已知边界（诚实标注）
--------------------
- **引用登记位置待官方件复核**：GB/T 33190 与 TC260 指南对
  `CustomDatas` 节的登记位置/必填属性未逐字核；本实现按指南
  「`CustomDatas/CustomData`」表述落，并在 `OFD.xml` 已有该节时登记引用；
  没有该节时选择「不改 OFD.xml」，只留可被扫描的 `CustomDatas/AIGC.xml`；
- 不解压/不改写 `Doc_0/**` 内容；不做签名（OFD 签章面属另外机制）；
- 不校验 `OFD.xml` 的 schema 合法性（只做文本层节定位与最小转义；
  XML 注释/CDATA 内的同名文本不特殊处理——正常 OFD 不会把该节写进注释；
  出现多个 `<CustomDatas>` 节时只处理第一个，其余原样保留）；
- 加密 entry 不支持（读取即 `ValueError`）；不处理 zip 注释以外的
  平台特有 extra 字段语义（但会原样保留）。
"""

from __future__ import annotations

import html
import json
import os
import re
import tempfile
import zipfile

#: OFD 2016 命名空间。
OFD_NS = "http://www.ofdspec.org/2016"
#: 自定义数据目录 / 文件名 / 登记名。
CUSTOM_DIR = "CustomDatas"
CUSTOM_ENTRY = "CustomDatas/AIGC.xml"
CUSTOM_NAME = "AIGC"
#: `<CustomDatas ...>` / `<CustomDatas .../>` 开标签（允许命名空间前缀）。
_OPEN_RE = re.compile(
    r"<(?P<p>[A-Za-z_][\w.-]*:)?CustomDatas\b"
    r"(?P<attrs>[^>]*?)(?P<sc>/>|>)")
#: 节内已有的 AIGC 登记（避免重复追加）。
_HAS_AIGC_RE = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?CustomData\b[^>]*?"
    r"\bName\s*=\s*[\"']AIGC[\"']")


def _validate_json(json_text: str) -> None:
    if not isinstance(json_text, str):
        raise ValueError("json_text 必须是 str（收到 %r）" % type(json_text))
    if not json_text.strip():
        raise ValueError("json_text 为空")
    try:
        json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)


def _custom_xml(json_text: str) -> bytes:
    """`CustomDatas/AIGC.xml` 的字节（Content 内为 XML 转义后的 JSON）。"""
    escaped = html.escape(json_text, quote=False)
    text = (
        '<CustomData xmlns="%s" Name="%s" Version="1.0">'
        "<Content>%s</Content></CustomData>"
        % (OFD_NS, CUSTOM_NAME, escaped)
    )
    return text.encode("utf-8")


def _child_tag(prefix: str) -> str:
    """登记子元素（前缀随 OFD.xml 的 CustomDatas 前缀走）。"""
    return ('<%sCustomData Name="%s" Location="%s"/>'
            % (prefix, CUSTOM_NAME, CUSTOM_ENTRY))


def _register(ofd_bytes: bytes) -> bytes:
    """在 OFD.xml 的 `<CustomDatas>` 节内登记引用；无节/已登记则原样返回。"""
    try:
        text = ofd_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("OFD.xml 不是 UTF-8：%s" % exc)
    m = _OPEN_RE.search(text)
    if m is None:
        return ofd_bytes                      # 无 CustomDatas 节：不改
    prefix = m.group("p") or ""
    if m.group("sc") == "/>":                 # 空节：展开成开/闭标签再登记
        opened = "<%sCustomDatas%s>" % (prefix, m.group("attrs"))
        block = opened + _child_tag(prefix) + "</%sCustomDatas>" % prefix
        return (text[:m.start()] + block + text[m.end():]).encode("utf-8")
    close = "</%sCustomDatas>" % prefix
    close_at = text.find(close, m.end())
    if close_at < 0:
        raise ValueError("OFD.xml 的 <CustomDatas> 未闭合，拒绝写入")
    inner = text[m.end():close_at]
    if _HAS_AIGC_RE.search(inner):
        return ofd_bytes                      # 已有登记：幂等，不动字节
    insert = _child_tag(prefix)
    return (text[:close_at] + insert + text[close_at:]).encode("utf-8")


def _read_zip(path: str):
    """读取 zip → (entries[(ZipInfo, bytes)], comment)；坏 zip → ValueError。"""
    try:
        zf = zipfile.ZipFile(path, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("不是合法 OFD（zip 打开失败）：%s" % exc)
    with zf:
        infos = zf.infolist()
        entries = []
        for info in infos:
            try:
                entries.append((info, zf.read(info)))
            except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
                raise ValueError(
                    "OFD entry 读取失败：%s（%s；加密/损坏 entry 不支持）"
                    % (info.filename, exc))
        return entries, zf.comment


def _write_zip(path: str, entries, comment: bytes) -> None:
    """原子重写 zip：entry 顺序/原始数据按 entries 给，权限位保留。"""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        mode = os.stat(path).st_mode & 0o7777
    except OSError:
        mode = None
    fd, tmp = tempfile.mkstemp(prefix=".nf-ofd-", suffix=".tmp",
                               dir=directory)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w") as zf:
            if comment:
                zf.comment = comment
            for info, data in entries:
                zf.writestr(info, data)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _new_info() -> zipfile.ZipInfo:
    """新 entry 的固定元数据（保证二次写入 zip 字节稳定）。"""
    info = zipfile.ZipInfo(CUSTOM_ENTRY, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


def inject_ofd(path: str, json_text: str) -> None:
    """把标识 JSON 写进 OFD：`CustomDatas/AIGC.xml`（+ 有节时登记引用）。

    - 其它 entry 解压后字节与顺序不变；
    - 幂等（同 JSON 二次写逐字节稳定；换 JSON 原位替换 Content）；
    - 坏 zip / 缺 OFD.xml / OFD.xml 非 UTF-8 / CustomDatas 未闭合 →
      ValueError；成功返回 None。
    """
    _validate_json(json_text)
    custom = _custom_xml(json_text)
    entries, comment = _read_zip(path)
    names = [info.filename for info, _data in entries]
    if names.count("OFD.xml") == 0:
        raise ValueError("OFD 包缺 OFD.xml，无法确认容器类型")
    if names.count("OFD.xml") > 1:
        raise ValueError("OFD 包存在多个 OFD.xml，无法确定写入目标")
    out = []
    seen_custom = False
    ofd_bytes = None
    for info, data in entries:
        if info.filename == "OFD.xml":
            ofd_bytes = data
        elif info.filename == CUSTOM_ENTRY:
            seen_custom = True
    if ofd_bytes is None:
        raise ValueError("OFD 包缺 OFD.xml，无法确认容器类型")
    new_ofd = _register(ofd_bytes)
    for info, data in entries:
        name = info.filename
        if name == "OFD.xml":
            out.append((info, new_ofd))
        elif name == CUSTOM_ENTRY:
            if out and any(i.filename == CUSTOM_ENTRY for i, _d in out):
                continue                      # 重复 entry：只保留第一份
            out.append((info, custom))
        else:
            out.append((info, data))
    if not seen_custom:
        out.append((_new_info(), custom))
    _write_zip(path, out, comment)


__all__ = [
    "OFD_NS",
    "CUSTOM_DIR",
    "CUSTOM_ENTRY",
    "CUSTOM_NAME",
    "inject_ofd",
]
