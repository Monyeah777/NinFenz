"""标识交叉认证：用**不经过主 checker** 的独立代码路径再验一遍文件标识。

主链路 `checker.check_file()` → `report.build_report()` 是「体检」真相源；本模块
是第二意见：自己按容器规范读字节、自己挑 JSON、自己算摘要，再与主报告逐项对表，
给出一页可互认回执。独立在哪：
- 不 import `metadata` / `checker` / `security_data`；PNG 的 tEXt/iTXt/zTXt 由本
  文件按 chunk 结构直接解析，JSON 文件只走 `json.loads`；
- 不验 SM2 签名、证书链、可信时间戳（刻意留给主 checker 的 C 段）；
- 只做结构级交叉：文件 SHA-256、容器、AIGC JSON 是否在场、七字段在场数、
  Label 取值、内容字节 SM3。

纪律：纯标准库；只读输入文件，不写文件（selfcheck 用临时目录）；raise 带修复
指引；注释中文。

用法：
  from core.labeling import xcheck
  xc = xcheck.verify("a.png", report_dict)
  receipt = xcheck.to_receipt(xc, subject_sha256)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import struct
import tempfile
import time
import zlib
from pathlib import Path

SCHEMA = "nf-label-xcheck/1"
TOOL = "nf-label-xcheck"
VERSION = "1.0.0"
PNG_SIG = b"\x89PNG\r\n\x1a\n"

#: 七字段顺序与主链路一致；本文件**复制**一份，不从 security_data import。
FIELDS = ("Label", "ContentProducer", "ProduceID", "ReservedCode1",
          "ContentPropagator", "PropagateID", "ReservedCode2")
REQUIRED = ("Label", "ContentProducer", "ProduceID")
LABEL_VALUES = ("1", "2", "3")
CODE27 = re.compile(r"^[0-9A-Z]{27}$")
VALUE_CHARS = re.compile(r"^[\x21\x23-\x5b\x5d-\x7e]+$")
STATUS_ORDER = {"PASS": 0, "WARN": 1, "NA": 2, "FAIL": 3}
AIGC_KEYS = ("AIGC", "aigc", "_aigc")


def _read_file(path):
    """读整文件；不存在/不可读都抛带修复指引的异常。"""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "文件不存在或不是普通文件：%s（修复指引：核对路径与权限后重跑）" % path)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise OSError(
            "文件读取失败：%s：%s（修复指引：确认读权限后重跑）"
            % (path, exc)) from exc


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _sm3(data):
    """现算 SM3；OpenSSL 不带 sm3 时按约定降级（不伪造摘要）。"""
    try:
        h = hashlib.new("sm3")
    except (ValueError, TypeError):
        return {"sm3": None, "reason": "openssl 无 sm3"}
    h.update(data)
    return {"sm3": h.hexdigest()}


def _status_of(statuses):
    """取最差状态；NA 不参与，全 NA/空 → 'NA'。"""
    seen = [s for s in statuses if s in STATUS_ORDER and s != "NA"]
    if not seen:
        return "NA"
    return max(seen, key=lambda s: STATUS_ORDER[s])


# ---------------------------------------------------------------- PNG

def _png_chunks(data):
    """按 PNG 规范遍历 chunk → [(type, payload, crc_ok)]；截断即报错。"""
    if not data.startswith(PNG_SIG):
        raise ValueError(
            "不是 PNG：文件签名不符（修复指引：确认导出格式，或改用 JSON 文件复核）")
    out = []
    pos, size = 8, len(data)
    while pos + 8 <= size:
        length = int.from_bytes(data[pos:pos + 4], "big")
        ctype = data[pos + 4:pos + 8]
        start, end = pos + 8, pos + 8 + length
        if end + 4 > size:
            raise ValueError(
                "PNG chunk 截断：%r（修复指引：重新导出 PNG 后重跑）" % ctype)
        crc = int.from_bytes(data[end:end + 4], "big")
        crc_ok = crc == (zlib.crc32(ctype + data[start:end]) & 0xFFFFFFFF)
        out.append((ctype, data[start:end], crc_ok))
        pos = end + 4
        if ctype == b"IEND":
            break
    if not out:
        raise ValueError("PNG 没有任何 chunk（修复指引：重新导出 PNG 后重跑）")
    return out


def _split_keyword(payload):
    """tEXt/zTXt/iTXt 共用：keyword NUL 之后是正文。"""
    idx = payload.find(b"\x00")
    if idx <= 0 or idx > 79:
        return b"", payload
    return payload[:idx], payload[idx + 1:]


def _png_entries(data):
    """独立解析 PNG 文本块 → [{container,key,text,crc_ok}]。"""
    out = []
    for ctype, payload, crc_ok in _png_chunks(data):
        try:
            if ctype == b"tEXt":
                kw, rest = _split_keyword(payload)
                if not kw:
                    continue
                out.append({"container": "png.tEXt", "key": kw.decode("latin-1"),
                            "text": rest.decode("latin-1"), "crc_ok": crc_ok})
            elif ctype == b"zTXt":
                kw, rest = _split_keyword(payload)
                if not kw or len(rest) < 1 or rest[0] != 0:
                    continue
                out.append({"container": "png.zTXt", "key": kw.decode("latin-1"),
                            "text": zlib.decompress(rest[1:]).decode("latin-1"),
                            "crc_ok": crc_ok})
            elif ctype == b"iTXt":
                kw, rest = _split_keyword(payload)
                if not kw or len(rest) < 2:
                    continue
                comp_flag, body = rest[0], rest[2:]
                # iTXt：语言标签与翻译名各以 NUL 结尾，之后才是正文
                for _ in range(2):
                    cut = body.find(b"\x00")
                    body = b"" if cut < 0 else body[cut + 1:]
                if comp_flag == 1:
                    body = zlib.decompress(body)
                out.append({"container": "png.iTXt", "key": kw.decode("latin-1"),
                            "text": body.decode("utf-8"), "crc_ok": crc_ok})
        except (zlib.error, IndexError, UnicodeDecodeError):
            continue
    return out


def _json_objects(data, source):
    """JSON 文件：只做 json.loads（不嗅探、不剥注释）。"""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "JSON 文件不是 UTF-8：%s（修复指引：另存为 UTF-8 后重跑）" % exc)
    try:
        obj = json.loads(text)
    except ValueError as exc:
        raise ValueError(
            "JSON 解析失败：%s（修复指引：先用 json.tool 校验语法后重跑）" % exc)
    if not isinstance(obj, (dict, list)):
        raise ValueError("JSON 顶层不是对象/数组：%s（修复指引：标识文档须是对象）"
                         % source)
    return [{"container": source, "key": "document", "text": text, "obj": obj}]


def _text_json_objects(entries):
    """从文本块里挑出可解析的 JSON 候选；解析失败静默跳过。"""
    out = []
    for entry in entries:
        text = (entry.get("text") or "").strip()
        if not text or text[0] not in "{[":
            continue
        try:
            obj = json.loads(text)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, (dict, list)):
            out.append({**entry, "obj": obj})
    return out


# ---------------------------------------------------------------- 结构事实

def _find_aigc(objects):
    """找 AIGC 包裹或直接含 Label 的对象 → (meta, source, count)。"""
    meta, source, count = None, None, 0
    for item in objects:
        obj = item.get("obj")
        if not isinstance(obj, dict):
            continue
        hit = next((obj[k] for k in AIGC_KEYS if isinstance(obj.get(k), dict)),
                   None)
        if hit is None and "Label" in obj:
            hit = obj
        if hit is None:
            continue
        count += 1
        if meta is None:
            meta, source = hit, item
    return meta, source, count


def _meta_checks(meta, count, content_ok):
    """按主报告 B/D 段同口径做结构判定（独立实现）→ (verdict, checks)。"""
    checks = []

    def add(i, status, detail):
        checks.append({"id": i, "status": status, "detail": detail})

    if meta is None:
        add("X-B0", "FAIL",
            "未找到 AIGC JSON（修复指引：确认 PNG 文本块或 JSON 文件含 AIGC 对象）")
        return "FAIL", checks
    present = [k for k in FIELDS if k in meta]
    missing_req = [k for k in REQUIRED if k not in meta]
    if missing_req:
        add("X-B1", "FAIL", "必需字段缺失：" + "、".join(missing_req))
    else:
        add("X-B1", "PASS",
            "七字段在场 %d/7：%s" % (len(present), "、".join(present)))
    if count > 1:
        add("X-B2", "FAIL", "发现 %d 份隐式标识（GB 45438 要求只保留一份）" % count)
    if "ReservedCode1" not in meta:
        add("X-B3", "WARN", "缺 ReservedCode1（生成方安全防护信息）")
    label = str(meta.get("Label"))
    if label in LABEL_VALUES:
        add("X-B4", "PASS", "Label=%s（取值合法）" % label)
    else:
        add("X-B5", "FAIL", "Label 取值非法：%r（应为 1/2/3）" % meta.get("Label"))
    prod = str(meta.get("ContentProducer") or "")
    if CODE27.match(prod):
        add("X-B6", "PASS", "ContentProducer 为 27 位编码")
    elif prod:
        add("X-B6", "WARN", "ContentProducer 非 27 位编码（国标允许名称或编码）")
    else:
        add("X-B6", "FAIL", "ContentProducer 为空")
    pid = str(meta.get("ProduceID") or "")
    if pid and len(pid) <= 128:
        add("X-B7", "PASS", "ProduceID 在场")
    else:
        add("X-B7", "FAIL", "ProduceID 为空或过长")
    bad = [k for k in REQUIRED
           if str(meta.get(k) or "") and not VALUE_CHARS.match(str(meta[k]))]
    if bad:
        add("X-B8", "WARN", "字段值超出 GB 45438 字符集：" + "、".join(bad))
    prop = meta.get("ContentPropagator")
    if prop:
        add("X-B9", "PASS" if CODE27.match(str(prop)) else "WARN",
            "传播平台字段在场")
    elif label in ("2", "3"):
        add("X-B9", "WARN", "Label=2/3 时应补传播要素")
    if content_ok:
        add("X-D1", "PASS", "内容字节可独立选取并复算")
    else:
        add("X-D1", "FAIL", "内容字节选取失败（修复指引：确认容器含 IDAT 等内容块）")
    return _status_of([c["status"] for c in checks]), checks


def _content(data, container):
    """内容字节：PNG 取 IDAT 拼接；其他容器退化为整文件 → (cntsel, bytes, ok)。"""
    if container == "png":
        parts = [p for t, p, _ok in _png_chunks(data) if t == b"IDAT"]
        if not parts:
            return "PNG-IDAT", b"", False
        return "PNG-IDAT", b"".join(parts), True
    return "DFT", data, True


def _magic_container(data):
    """按魔数认容器（独立实现，漏识别就归 unknown）。"""
    magic = ((b"\xff\xd8\xff", "jpeg"), (b"%PDF-", "pdf"), (b"GIF87a", "gif"),
             (b"GIF89a", "gif"), (b"fLaC", "flac"), (b"OggS", "ogg"),
             (b"ID3", "mp3"), (b"PK\x03\x04", "zip"))
    for sig, name in magic:
        if data.startswith(sig):
            return name
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "wav"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "mp4"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    return "text"


def _detect(path, data):
    """→ (container, mode)；mode ∈ png/json/unsupported。"""
    if data.startswith(PNG_SIG):
        return "png", "png"
    if Path(path).suffix.lower() == ".json":
        return "text", "json"
    if data.lstrip()[:1] in (b"{", b"["):
        try:
            parsed = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            return "text", "json"
    return _magic_container(data), "unsupported"


# ---------------------------------------------------------------- 与主报告比对

def _section_status(report, key):
    sec = (report.get("sections") or {}).get(key)
    return sec.get("status") if isinstance(sec, dict) else None


def _main_field_count(report):
    items = ((report.get("sections") or {}).get("B") or {}).get("items") or []
    for item in items:
        if item.get("id") == "B0":
            return 0
        if item.get("id") == "B1":
            present = (item.get("evidence") or {}).get("present")
            if isinstance(present, list):
                return len(present)
            m = re.search(r"七字段在场\s*(\d+)/7", str(item.get("detail") or ""))
            if m:
                return int(m.group(1))
    return None


def _main_label(report):
    items = ((report.get("sections") or {}).get("B") or {}).get("items") or []
    for item in items:
        detail = str(item.get("detail") or "")
        if item.get("id") == "B4":
            m = re.search(r"Label=([^（\s]+)", detail)
            if m:
                return m.group(1)
        elif item.get("id") == "B5":
            m = re.search(r"Label 取值非法：(.+?)（应为", detail)
            if m:
                return m.group(1).strip("'\"")
    return None


def _main_sm3(report):
    for key in ("D", "C"):
        items = ((report.get("sections") or {}).get(key) or {}).get("items") or []
        for item in items:
            if item.get("id") in ("D2", "C2"):
                ev = item.get("evidence") or {}
                value = ev.get("sm3") or ev.get("content_hash")
                if value:
                    return str(value)
    return None


def _comparison(name, main, independent, agree):
    return {"name": name, "main": main, "independent": independent,
            "agree": agree}


def _verify_agreement(report, independent_verdict):
    """verdict 比对：主报告总分含 C/E；结构段只到 A/B/D。"""
    main = report.get("verdict")
    sections = [_section_status(report, k) for k in ("A", "B", "C", "D")]
    expected = _status_of(sections) if all(sections) else None
    consistent = expected is None or main == expected
    main_struct = _status_of([s for s in
                              (_section_status(report, k) for k in ("A", "B", "D"))
                              if s])
    if independent_verdict is None:
        return main, None, None, "独立路径不支持该容器的结构判定"
    if not consistent:
        return main, independent_verdict, False, "主报告 verdict 与自身分节不一致"
    agree = main == independent_verdict or main_struct == independent_verdict
    note = ""
    if agree and main != independent_verdict:
        note = "主报告总分含 C/E 段；A/B/D 结构段与独立结论一致"
    return main, independent_verdict, agree, note


def _compare(report, xc):
    """逐项对表 → {comparisons, agree_count, conflict, trust, notes}。"""
    ind = xc["independent"]
    unsupported = xc["mode"] == "unsupported"
    items = [
        _comparison("container", report.get("container"), xc["container"],
                    report.get("container") == xc["container"]),
        _comparison("report_id", report.get("report_id"), xc["report_id"],
                    report.get("report_id") == xc["report_id"]),
        _comparison("file_sha256", (report.get("file") or {}).get("sha256"),
                    xc["file"]["sha256"],
                    (report.get("file") or {}).get("sha256")
                    == xc["file"]["sha256"]),
    ]
    main_v, ind_v, v_agree, v_note = _verify_agreement(
        report, None if unsupported else ind["verdict"])
    verdict_item = _comparison("verdict", main_v, ind_v, v_agree)
    if v_note:
        verdict_item["note"] = v_note
    items.append(verdict_item)
    if unsupported:
        items += [_comparison(name, None, None, None)
                  for name in ("fields_present", "label", "sm3")]
    else:
        main_fields = _main_field_count(report)
        items.append(_comparison("fields_present", main_fields,
                                 ind["field_count"], main_fields == ind["field_count"]))
        main_label = None if _main_label(report) is None else str(_main_label(report))
        items.append(_comparison("label", main_label, ind["label"],
                                 main_label == ind["label"]))
        main_sm3 = _main_sm3(report)
        ind_sm3 = ind["sm3"].get("sm3")
        if ind_sm3 is None:
            items.append(_comparison("sm3", main_sm3, None, None))
        else:
            items.append(_comparison(
                "sm3", main_sm3.lower() if main_sm3 else None, ind_sm3.lower(),
                bool(main_sm3) and main_sm3.lower() == ind_sm3.lower()))
    agree_count = sum(1 for item in items if item["agree"] is True)
    conflict = [item["name"] for item in items if item["agree"] is False]
    notes = []
    if conflict:
        trust = "conflict"
        notes.append("左右不一致：「%s」须先核对再互认（修复指引：重跑主报告并"
                     "逐项对照本回执）" % "、".join(conflict))
    elif any(item["agree"] is None for item in items):
        trust = "partial"
        notes.append("存在不可比对项（SM3 不可用或容器超出独立路径覆盖范围）"
                     "（修复指引：安装支持 SM3 的 OpenSSL，或改验 PNG/JSON）")
    else:
        trust = "agree"
    return {"comparisons": items, "agree_count": agree_count,
            "conflict": conflict, "trust": trust, "notes": notes}


# ---------------------------------------------------------------- 入口

def verify(path, report=None):
    """独立复核一个文件；给了主报告就逐项对表。

    返回 schema `nf-label-xcheck/1` 的字典；文件不存在抛 FileNotFoundError，
    report 不是字典抛 ValueError（均带修复指引）。
    """
    if report is not None and not isinstance(report, dict):
        raise ValueError(
            "report 必须是 dict（修复指引：传入 report.build_report() 的返回值）")
    data = _read_file(path)
    sha = _sha256(data)
    container, mode = _detect(path, data)
    if mode == "png":
        objects = _text_json_objects(_png_entries(data))
    elif mode == "json":
        objects = _json_objects(data, "json")
    else:
        objects = []
    meta, source, count = _find_aigc(objects)
    label = None if meta is None else meta.get("Label")
    present = [] if meta is None else [k for k in FIELDS if k in meta]
    cntsel, content, content_ok = _content(data, container)
    sm3 = _sm3(content)
    if mode == "unsupported":
        verdict, checks = None, [{"id": "X0", "status": "NA",
                                  "detail": "独立路径只覆盖 PNG 文本块与 JSON 文档"}]
    else:
        verdict, checks = _meta_checks(meta, count, content_ok)
    xc = {
        "schema": SCHEMA, "tool": TOOL, "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "file": {"name": os.path.basename(path), "path": path,
                 "size": len(data), "sha256": sha},
        "report_id": sha[:16], "container": container, "mode": mode,
        "independent": {
            "aigc_found": meta is not None, "aigc_count": count,
            "aigc_source": (source or {}).get("container"),
            "fields_present": present, "field_count": len(present),
            "fields_missing": [k for k in FIELDS if k not in present],
            "label": None if label is None else str(label),
            "label_valid": label is not None and str(label) in LABEL_VALUES,
            "content": {"cntsel": cntsel, "bytes": len(content), "ok": content_ok},
            "sm3": sm3, "verdict": verdict, "checks": checks,
        },
        "comparisons": [], "agree_count": 0, "conflict": [],
        "trust": "partial", "notes": [], "main": None,
    }
    if report is None:
        xc["notes"].append(
            "未提供主报告，只做独立结构核验，无法判定互认一致性"
            "（修复指引：生成 report.json 后加 --report 重跑）")
    else:
        xc.update(_compare(report, xc))
        xc["main"] = {"report_id": report.get("report_id"),
                      "verdict": report.get("verdict"),
                      "container": report.get("container")}
    if mode == "unsupported":
        xc["notes"].append(
            "容器 %s 超出独立路径覆盖范围（仅 PNG/JSON 做结构交叉）"
            "（修复指引：导出 PNG/JSON 后重跑）" % container)
    if sm3.get("sm3") is None:
        xc["notes"].append(
            "本机 OpenSSL 无 SM3，内容摘要记为不可比对"
            "（修复指引：安装支持 SM3 的 OpenSSL 后重跑）")
    return xc


def to_receipt(xc, subject_sha256):
    """生成可贴进邮件/报告的一页回执（字典，可直接 json.dumps）。"""
    if not isinstance(subject_sha256, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", subject_sha256):
        raise ValueError(
            "subject_sha256 须为 64 位十六进制（修复指引：用 sha256sum <file> "
            "复算后传入）")
    files = xc.get("file") or {}
    path_q = shlex.quote(str(files.get("path") or ""))
    return {
        "schema": "nf-label-xcheck-receipt/1",
        "title": "AI 生成合成内容标识 · 独立交叉验证回执",
        "issued_at": xc.get("generated_at"),
        "tool": {"name": TOOL, "version": VERSION},
        "subject": {
            "name": files.get("name"), "path": files.get("path"),
            "size": files.get("size"), "sha256": subject_sha256.lower(),
            "recomputed_sha256": files.get("sha256"),
            "subject_match": subject_sha256.lower() == files.get("sha256"),
        },
        "container": xc.get("container"),
        "independent": xc["independent"],
        "crosscheck": {"trust": xc.get("trust"),
                       "agree_count": xc.get("agree_count"),
                       "conflict": xc.get("conflict"),
                       "items": xc.get("comparisons")},
        "method": [
            "自行按 PNG 规范遍历 chunk 解析 tEXt/iTXt/zTXt；JSON 仅用 json.loads。"
            "不 import 主 checker 的 metadata/checker 模块。",
            "只做结构级交叉：文件 SHA-256、容器、AIGC JSON 是否在场、七字段在场数、"
            "Label 取值、内容字节 SM3；不验签名/证书/时间戳。",
            "内容字节：PNG 取全部 IDAT 拼接，其他容器退化为整文件；SM3 由 "
            "hashlib.new('sm3') 现算，缺算法时明确记为不可用。",
            "与主报告逐项比对 report_id/容器/文件 SHA-256/verdict/七字段数/"
            "Label/SM3，全部一致才给 agree。",
        ],
        "limitations": [
            "独立路径不验证 SM2 签名、证书链与可信时间戳（由主 checker 的 C 段负责）。",
            "不判定像素/画面/音轨中的显式标识，需人工或 OCR/抽帧复核。",
            "回执只证明两侧在同一时刻对同一文件的结构事实一致，不构成官方认定"
            "或法律意见。",
        ],
        "recompute": [
            "python3 scripts/nf_label_xcheck.py verify %s --json" % path_q,
            "sha256sum %s" % path_q,
            "python3 scripts/nf_label_xcheck.py verify %s --report report.json "
            "--json" % path_q,
        ],
        "disclaimer": "本回执为本地工具的自查结果，可被第三方按复算命令独立复核。",
    }


def render_text(xc):
    """人读面（CLI 默认输出）。"""
    ind = xc["independent"]
    mark = {True: "一致", False: "冲突", None: "跳过"}
    lines = [
        "== nf-label-xcheck（独立交叉认证）==",
        "文件：%s  容器：%s  模式：%s" % (xc["file"]["name"],
                                          xc["container"], xc["mode"]),
        "SHA-256：%s" % xc["file"]["sha256"],
        "独立结构：AIGC=%s  七字段=%d/7  Label=%s  SM3=%s"
        % ("在场" if ind["aigc_found"] else "缺失", ind["field_count"],
           ind["label"], ind["sm3"].get("sm3") or "不可用"),
        "交叉结论：%s（一致 %d 项，冲突 %d 项）"
        % (xc["trust"], xc["agree_count"], len(xc["conflict"])),
    ]
    for item in xc["comparisons"]:
        lines.append("  - %-14s %s（主 %r / 独立 %r）"
                     % (item["name"], mark.get(item["agree"], item["agree"]),
                        item["main"], item["independent"]))
    lines += ["  ! %s" % note for note in xc["notes"]]
    return "\n".join(lines)


# ---------------------------------------------------------------- 自检

def _png_chunk(ctype, payload):
    """自检用最小 PNG chunk（长度 + 类型 + 数据 + CRC32）。"""
    return (struct.pack(">I", len(payload)) + ctype + payload
            + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF))


def _selfcheck_png():
    """自检夹具：8×8 真彩 PNG，AIGC 放在 tEXt 里。"""
    rows = b"".join(b"\x00" + b"\x11\x22\x33" * 8 for _ in range(8))
    ihdr = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    text = json.dumps({"AIGC": {"Label": 1, "ContentProducer": "1" * 27,
                                "ProduceID": "XCHECK-SELFCHECK"}},
                      ensure_ascii=False).encode("latin-1")
    return (PNG_SIG + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"tEXt", b"AIGC\x00" + text)
            + _png_chunk(b"IDAT", zlib.compress(rows))
            + _png_chunk(b"IEND", b""))


def _fake_report(xc):
    """按独立事实造一份等价主报告，用来验证对表语义。"""
    ind = xc["independent"]
    return {
        "schema": "nf-label-report/1", "report_id": xc["report_id"],
        "container": xc["container"], "verdict": "WARN",
        "file": {"sha256": xc["file"]["sha256"]},
        "sections": {
            "A": {"status": "NA", "items": []},
            "B": {"status": "WARN", "items": [
                {"id": "B1", "status": "PASS", "detail": "七字段在场 3/7",
                 "evidence": {"present": ind["fields_present"],
                              "missing": ind["fields_missing"]}},
                {"id": "B4", "status": "PASS",
                 "detail": "Label=%s（合法）" % ind["label"]}]},
            "C": {"status": "WARN", "items": []},
            "D": {"status": "PASS", "items": [
                {"id": "D2", "status": "PASS",
                 "evidence": {"sm3": ind["sm3"].get("sm3")}}]},
        },
    }


def selfcheck():
    """返回 [(名称, ok, detail)]，供 CLI / 测试复用。"""
    out = []

    def run(name, fn):
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 —— 自检必须报告而不是崩溃
            ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
        out.append((name, bool(ok), str(detail)))

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "selfcheck.png")
        with open(path, "wb") as fh:
            fh.write(_selfcheck_png())
        xc = verify(path)

        def case_parse():
            ind = xc["independent"]
            return (xc["mode"] == "png" and ind["aigc_found"]
                    and ind["field_count"] == 3 and ind["label"] == "1",
                    "AIGC=%s 字段=%d Label=%s" % (
                        ind["aigc_found"], ind["field_count"], ind["label"]))

        def case_hash():
            want = _sha256(_read_file(path))
            return (xc["file"]["sha256"] == want
                    and xc["report_id"] == want[:16], "SHA-256/report_id 可复算")

        def case_agree():
            got = verify(path, _fake_report(xc))
            want = "agree" if xc["independent"]["sm3"].get("sm3") else "partial"
            ok = got["trust"] == want
            if want == "agree":
                ok = ok and got["agree_count"] == 7
            return ok, got["trust"]

        def case_tamper():
            bad = _fake_report(xc)
            bad["file"]["sha256"] = "0" * 64
            got = verify(path, bad)
            return (got["trust"] == "conflict"
                    and "file_sha256" in got["conflict"], got["conflict"])

        def case_receipt():
            rec = to_receipt(xc, xc["file"]["sha256"])
            return (rec["schema"] == "nf-label-xcheck-receipt/1"
                    and rec["subject"]["subject_match"]
                    and "nf_label_xcheck.py verify" in rec["recompute"][0],
                    "回执字段与复算命令完整")

        run("PNG chunk 解析", case_parse)
        run("文件摘要可复算", case_hash)
        run("与主报告对表（自造标本）", case_agree)
        run("篡改 hash 必须判冲突", case_tamper)
        run("回执字段完整", case_receipt)
    return out


if __name__ == "__main__":
    import sys

    ok = True
    for name, good, detail in selfcheck():
        print(("PASS" if good else "FAIL"), name, detail)
        ok &= good
    sys.exit(0 if ok else 1)
