"""额外容器的 DFT 内容口径（TC260-PG-202511A 附录 A.2）。

`CntSel` 只有三个取值：JPEG（SOS..EOI 前）、PNG（IDAT 数据拼接）、
DFT（除隐式标识外的全部字节，默认方案）。所以 MOV/PPTX 等容器不是"没有口径"，
而是走 DFT：扣除承载标识的字节区间后，按原文件顺序拼接剩余字节。

本模块只做"取字节 + 补丁"两件事，供 `extra_integration` 薄层调用；
单独拆出是为了让 `extra_integration` 保持在 code_metrics 冻结行数内。
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from . import metadata, metadata_extra

#: 这些容器由 metadata_extra 读取，主 metadata.sniff 不认。
EXTRA_CONTAINER_LABEL = {
    "mov": "QuickTime/MOV 视频", "mkv": "Matroska 视频",
    "avi": "AVI 视频", "pptx": "PowerPoint 演示",
    "xlsx": "Excel 工作簿", "svg": "SVG 矢量图",
    "rtf": "RTF 文档",
}


def container_label(name):
    return EXTRA_CONTAINER_LABEL.get(name, name)


def dft_bytes(path, entries):
    """按 DFT 口径取内容字节 → (content, ranges)。

    只扣除**明文可定位**的标识文本（UTF-8 字节在文件中原样出现）；
    压缩/编码后的标识块定位不到就不扣，返回 ranges=[]，由报告说明，不伪造。
    """
    data = Path(path).read_bytes()
    ranges = []
    for entry in entries:
        text = entry.get("text") or ""
        if not text:
            continue
        pos = data.find(text.encode("utf-8"))
        if pos >= 0:
            ranges.append((pos, pos + len(text.encode("utf-8"))))
    if not ranges:
        return data, []
    ranges.sort()
    merged = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    out = []
    cursor = 0
    for start, end in merged:
        out.append(data[cursor:start])
        cursor = end
    out.append(data[cursor:])
    return b"".join(out), merged


@contextmanager
def patched_metadata(path):
    """临时让主 checker 认得额外容器与 DFT 口径；退出即恢复。"""
    entries = metadata_extra.extract_extra(path)
    content, ranges = dft_bytes(path, entries)
    original = (metadata.sniff, metadata.extract,
                metadata.extract_json_candidates, metadata.content_bytes_for)

    def sniff(p):
        found = original[0](p)
        if found != "unknown":
            return found
        return metadata_extra.sniff_extra(p) or "unknown"

    def extract(p):
        return original[1](p) or metadata_extra.extract_extra(p)

    def extract_json_candidates(p):
        return original[2](p)

    def content_bytes_for(p, container):
        if container in EXTRA_CONTAINER_LABEL:
            return "DFT", content
        return original[3](p, container)

    metadata.sniff = sniff
    metadata.extract = extract
    metadata.extract_json_candidates = extract_json_candidates
    metadata.content_bytes_for = content_bytes_for
    try:
        yield {"entries": len(entries), "excluded": len(ranges)}
    finally:
        (metadata.sniff, metadata.extract, metadata.extract_json_candidates,
         metadata.content_bytes_for) = original


def mark_note(rep, container, excluded):
    """把 DFT 口径与扣除情况写进 D 段说明，便于复核。"""
    items = (rep["sections"].get("D") or {}).get("items") or []
    for item in items:
        if item.get("id") == "D1":
            item["detail"] += (
                "（容器 %s 按 TC260-PG-202511A 附录 A.2 采用 CntSel=DFT，"
                "扣除标识区间 %d 处）" % (container, excluded))
            item.setdefault("evidence", {})["cntsel"] = "DFT"
            item["evidence"]["excluded_ranges"] = excluded


def recount(rep):
    counts = {"items": 0, "PASS": 0, "WARN": 0, "FAIL": 0, "NA": 0}
    for sec in rep["sections"].values():
        for item in sec.get("items") or []:
            status = item.get("status")
            if status in counts:
                counts[status] += 1
                counts["items"] += 1
    return counts


def sniff_extra(path):
    return metadata_extra.sniff_extra(path)


def selfcheck():
    """自检：DFT 扣除、补丁生效/恢复、容器标签。"""
    import tempfile
    out = []
    with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as fh:
        fh.write(b"AAA" + b'{"AIGC":{}}' + b"BBB")
        tmp = fh.name
    try:
        original = metadata.sniff
        with patched_metadata(tmp):
            out.append(("补丁生效", metadata.sniff is not original,
                        "sniff 已替换"))
        out.append(("补丁恢复", metadata.sniff is original, "退出后还原"))
        content, ranges = dft_bytes(tmp, [{"text": '{"AIGC":{}}'}])
        out.append(("DFT 扣除", content == b"AAABBB" and len(ranges) == 1,
                    "扣除明文标识区间"))
    finally:
        Path(tmp).unlink()
    out.append(("容器标签", container_label("pptx") != "pptx", "有中文标签"))
    return out
