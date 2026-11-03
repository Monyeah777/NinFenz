"""五段判定引擎：显式标识 / 隐式字段 / 安全防护 / 内容绑定 / 备案材料。

依据 GB 45438—2025 与 TC260-PG-202511A（细节见 docs/spec-notes.md）。
输出：可机读判定报告（dict），供 CLI 渲染与证据包归档。
"""

from __future__ import annotations

import json
import os
import re

from . import metadata, security_data as sdmod, sm

MARKERS = (
    "AI生成", "AI 生成", "人工智能生成", "由AI生成", "由 AI 生成",
    "生成合成", "AIGC", "AI-Generated", "AI generated",
)

CODE27 = re.compile(r"^[0-9A-Z]{27}$")
# GB 45438 值字符集：GB18030 码位 0x21、0x23–0x5B、0x5D–0x7E
VALUE_CHARS = re.compile(r"^[\x21\x23-\x5b\x5d-\x7e]+$")

STATUS_ORDER = {"PASS": 0, "WARN": 1, "NA": 2, "FAIL": 3}


def _item(i, status, detail, evidence=None):
    return {"id": i, "status": status, "detail": detail,
            "evidence": evidence or {}}


def _agg(items):
    """聚合：NA 不参与；全 NA 记为 NA；否则取最差 PASS/WARN/FAIL。"""
    seen = [it["status"] for it in items if it["status"] != "NA"]
    if not seen:
        return "NA"
    return max(seen, key=lambda x: STATUS_ORDER[x])


def _find_meta(candidates):
    """从候选 JSON 中找标识元数据；支持 {"AIGC": {...}} 包裹。"""
    for c in candidates:
        obj = c.get("obj")
        if not isinstance(obj, dict):
            continue
        for key in ("AIGC", "aigc", "_aigc"):
            if isinstance(obj.get(key), dict):
                return obj[key], c
        if "Label" in obj:
            return obj, c
    return None, None


def _count_meta_candidates(candidates):
    n = 0
    for c in candidates:
        obj = c.get("obj")
        if isinstance(obj, dict):
            if any(isinstance(obj.get(k), dict) for k in ("AIGC", "aigc", "_aigc")):
                n += 1
            elif "Label" in obj:
                n += 1
    return n


# ---------------------------------------------------------------- A 显式

def _explicit_section(container, raw_text):
    items = []
    if container in ("text", "markdown"):
        text = raw_text or ""
        hit = [m for m in MARKERS if m in text]
        head, tail = text[:300], text[-300:]
        near = [m for m in hit if m in head or m in tail]
        if hit:
            items.append(_item("A1", "PASS",
                               "正文存在显式标识字样：" + "、".join(hit[:3]),
                               {"markers": hit}))
            if not near:
                items.append(_item("A2", "WARN",
                                   "标识字样不在起始/末尾 300 字内，位置可能不符合"
                                   "「起始/末尾/中间显著提示」习惯"))
        else:
            items.append(_item("A1", "FAIL",
                               "未发现显式标识字样（文本应在起始/末尾/中间或界面"
                               "显著提示）"))
    else:
        items.append(_item("A1", "NA",
                           "显式标识位于像素/画面/音轨，本工具不做视觉判定；"
                           "请人工或 OCR/抽帧复核"))
    return {"id": "A", "title": "显式标识", "items": items,
            "status": _agg(items)}


# ---------------------------------------------------------------- B 隐式

def _implicit_section(meta, count):
    if meta is None:
        return {"id": "B", "title": "隐式标识字段", "status": "FAIL",
                "items": [_item("B0", "FAIL", "未找到隐式标识元数据（七字段 JSON）")]}
    items = []
    present = [k for k in sdmod.FIELDS if k in meta]
    missing = [k for k in sdmod.FIELDS if k not in meta]
    required = ["Label", "ContentProducer", "ProduceID"]
    missing_req = [k for k in required if k not in meta]
    if missing_req:
        items.append(_item("B1", "FAIL",
                           "必需字段缺失：" + "、".join(missing_req),
                           {"present": present, "missing": missing}))
    else:
        items.append(_item("B1", "PASS",
                           f"七字段在场 {len(present)}/7：" + "、".join(present),
                           {"present": present, "missing": missing}))
    if count > 1:
        items.append(_item("B2", "FAIL",
                           f"发现 {count} 份隐式标识；GB 45438 6.1 c) 要求"
                           "一个文件只保留一份"))
    if "ReservedCode1" not in meta:
        items.append(_item("B3", "WARN", "缺 ReservedCode1（生成方安全防护信息）"))
    label = meta.get("Label")
    if str(label) in {str(k) for k in sdmod.LABEL_VALUES}:
        items.append(_item("B4", "PASS",
                           f"Label={label}（{sdmod.describe_field('Label')}）"))
    else:
        items.append(_item("B5", "FAIL", f"Label 取值非法：{label!r}（应为 1/2/3）"))
    prod = str(meta.get("ContentProducer") or "")
    if CODE27.match(prod):
        items.append(_item("B6", "PASS",
                           "ContentProducer 为 27 位编码（2 位格式码+20 位主体"
                           "标识码+5 位扩展码）"))
    elif prod:
        items.append(_item("B6", "WARN",
                           "ContentProducer 不是 27 位编码（国标允许名称或编码；"
                           "填编码时按 TC260-PG-20252A 自赋）",
                           {"value": prod}))
    else:
        items.append(_item("B6", "FAIL", "ContentProducer 为空"))
    pid = str(meta.get("ProduceID") or "")
    if pid and len(pid) <= 128:
        items.append(_item("B7", "PASS", "ProduceID 在场"))
    else:
        items.append(_item("B7", "FAIL", "ProduceID 为空或过长"))
    bad_chars = []
    for key in ("Label", "ContentProducer", "ProduceID"):
        val = str(meta.get(key, ""))
        if val and not VALUE_CHARS.match(val):
            bad_chars.append(key)
    if bad_chars:
        items.append(_item("B8", "WARN",
                           "字段值超出 GB 45438 字符集（ASCII 可见字符）："
                           + "、".join(bad_chars)))
    prop = meta.get("ContentPropagator")
    if prop:
        ok = bool(CODE27.match(str(prop)))
        items.append(_item("B9", "PASS" if ok else "WARN",
                           "传播平台字段在场" + ("" if ok else "（非 27 位编码）")))
    elif str(label) in ("2", "3"):
        items.append(_item("B9", "WARN",
                           "Label=2/3（声明/疑似）时传播平台应补传播要素"))
    else:
        items.append(_item("B9", "NA", "未到传播环节，传播要素由平台写入（正常）"))
    return {"id": "B", "title": "隐式标识字段", "status": _agg(items),
            "items": items}


# ---------------------------------------------------------------- C 安全防护

def _security_section(meta, raw_text, selector, pub_hex, roots=None,
                      when=None):
    if meta is None:
        return {"id": "C", "title": "安全防护信息", "status": "NA",
                "items": [_item("C0", "NA", "无隐式标识元数据，跳过")]}
    box = meta.get("ReservedCode1")
    if box is None:
        return {"id": "C", "title": "安全防护信息", "status": "WARN",
                "items": [_item("C0", "WARN", "无 ReservedCode1，无法校验签名")]}
    if isinstance(box, str):
        try:
            box = json.loads(box)
        except Exception:
            return {"id": "C", "title": "安全防护信息", "status": "FAIL",
                    "items": [_item("C0", "FAIL", "ReservedCode1 不是合法 JSON")]}
    items = []
    issues = sdmod.structure_issues(box)
    items.append(_item("C1", "FAIL" if issues else "PASS",
                       ("结构问题：" + "；".join(issues)) if issues
                       else "SecurityData 结构合格", {"issues": issues}))
    sd = box.get("SecurityData") if isinstance(box, dict) else None
    if not isinstance(sd, dict):
        return {"id": "C", "title": "安全防护信息", "status": "FAIL",
                "items": items}
    bindings = sd.get("Bindings") or []
    content = selector(sd)
    if content is not None:
        ok, bissues, got = sdmod.check_binding(sd, content)
        items.append(_item("C2", "PASS" if ok else "FAIL",
                           "杂凑绑定与内容一致" if ok else "；".join(bissues),
                           {"content_hash": got}))
    else:
        items.append(_item("C2", "WARN", "无法取得内容字节，跳过杂凑绑定"))
    ok, sissues = sdmod.verify_signatures(sd, meta, raw_text, bindings,
                                          content, pub_hex)
    items.append(_item("C3", "PASS" if ok else "FAIL",
                       "SM3withSM2 签名可验" if ok else "；".join(sissues),
                       {"pub_keys": list(sdmod.public_keys(sd))}))
    cok, cissues, cdetail = sdmod.verify_cert_chain(sd, roots, when)
    if "PubSD 中没有 Certificate" in "；".join(cissues):
        items.append(_item("C4", "NA", "未提供证书（原型签名为裸公钥模式）"))
    elif roots is None:
        items.append(_item("C4", "WARN",
                           "有证书但未提供信任根（--trust-store），未验链",
                           cdetail))
    else:
        items.append(_item("C4", "PASS" if cok else "FAIL",
                           "证书链到信任根" if cok else "；".join(cissues),
                           cdetail))
    ds_list = [p for p in (sd.get("PubSD") or [])
               if isinstance(p, dict) and p.get("Type") == "DS"]
    tok_ok = False
    if ds_list:
        for i, ds_item in enumerate(ds_list):
            if ds_item.get("Time") is None:
                items.append(_item(f"C5.{i}", "NA", "未附可信时间戳（可选）"))
                continue
            tok_ok, t_issues, t_detail = sdmod.verify_time(ds_item, roots, when)
            items.append(_item(f"C5.{i}", "PASS" if tok_ok else "FAIL",
                               "可信时间戳可验" if tok_ok else "；".join(t_issues),
                               t_detail))
    return {"id": "C", "title": "安全防护信息", "status": _agg(items),
            "items": items}


# ---------------------------------------------------------------- D 内容绑定

def select_content(path, container):
    """按容器给默认 CntSel 并返回 (cntsel, content)。"""
    return metadata.content_bytes_for(path, container)


def _content_selector(path, container, entries):
    def _for_cntsel(sd):
        try:
            _label, content = metadata.content_bytes_for(path, container)
            return content
        except ValueError:
            return None
    return _for_cntsel


# ---------------------------------------------------------------- E 材料

def _materials_section(sec):
    a, b, c = sec["A"], sec["B"], sec["C"]
    b_items = {it["id"]: it["status"] for it in b["items"]}
    c_items = {it["id"]: it["status"] for it in c["items"]}
    have = {
        "隐式标识元数据样本": b["status"] != "FAIL",
        "证书链与时间戳（可选）": any(it["id"] == "C4" and it["status"] == "PASS"
                                    for it in c["items"]),
        "内容摘要与绑定记录": c_items.get("C2") == "PASS",
        "SM3withSM2 签名与公钥": c_items.get("C3") == "PASS",
        "显式标识样例": a["status"] != "FAIL",
        "服务提供者编码（27 位）": b_items.get("B6") == "PASS",
        "标识方法说明（协议/界面）": False,
        "日志留存说明（≥6 个月）": False,
    }
    items = [_item(f"E{i}", "PASS" if ok else "WARN",
                   f"{'已有' if ok else '待补'}：{name}")
             for i, (name, ok) in enumerate(have.items(), 1)]
    done, total = sum(have.values()), len(have)
    items.append(_item("E9", "PASS" if done == total else "WARN",
                       f"备案/评估可用材料 {done}/{total}"))
    return {"id": "E", "title": "备案材料", "status": _agg(items),
            "items": items, "materials": have}


# ---------------------------------------------------------------- 入口

def _binding_section(path, container, entries):
    items = []
    try:
        cntsel, content = metadata.content_bytes_for(path, container)
        items.append(_item("D1", "PASS",
                           f"内容字节选取 CntSel={cntsel}，共 {len(content)} 字节",
                           {"cntsel": cntsel, "bytes": len(content)}))
        items.append(_item("D2", "PASS", "SM3 摘要可复算",
                           {"sm3": sm.sm3_hex(content)}))
    except ValueError as exc:
        items.append(_item("D1", "FAIL", f"内容字节选取失败：{exc}"))
    items.append(_item("D3", "NA", "绑定关系由 C2/C3 综合判定"))
    return {"id": "D", "title": "内容绑定", "status": _agg(items),
            "items": items}


def check_file(path, pub_hex=None, stamp=False, trust_store=None, when=None):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    roots = None
    if trust_store:
        from . import x509
        roots = x509.load_trust_store(trust_store)
    container = metadata.sniff(path)
    raw_text = None
    if container in ("text", "markdown"):
        try:
            with open(path, "rb") as fh:
                raw_text = fh.read().decode("utf-8", "replace")
        except OSError:
            raw_text = ""
    candidates = metadata.extract_json_candidates(path)
    meta, found_at = _find_meta(candidates)
    count = _count_meta_candidates(candidates)
    report = {
        "tool": "nf-labelcheck/0.1",
        "file": os.path.basename(path),
        "container": container,
        "meta_found_at": (found_at or {}).get("container"),
        "meta_raw": (found_at or {}).get("raw", "") if meta else "",
        "sections": {},
    }
    report["sections"]["A"] = _explicit_section(container, raw_text)
    report["sections"]["B"] = _implicit_section(meta, count)
    entries = metadata.extract(path)
    selector = _content_selector(path, container, entries)
    report["sections"]["D"] = _binding_section(path, container, entries)
    report["sections"]["C"] = _security_section(
        meta, report["meta_raw"], selector, pub_hex, roots, when)
    report["sections"]["E"] = _materials_section(report["sections"])
    verdicts = [report["sections"][k]["status"] for k in ("A", "B", "C", "D")]
    if "FAIL" in verdicts:
        report["verdict"] = "FAIL"
    elif "WARN" in verdicts:
        report["verdict"] = "WARN"
    else:
        report["verdict"] = "PASS"
    report["exit_code"] = {"PASS": 0, "WARN": 0, "FAIL": 1}[report["verdict"]]
    return report


def build_evidence(report, path):
    """生成备案/评估可用的证据包（字典，不含时间戳以保证可复算）。"""
    sec = report["sections"]
    return {
        "schema": "nf-labelcheck/evidence/1",
        "file": report["file"],
        "container": report["container"],
        "verdict": report["verdict"],
        "meta_found_at": report["meta_found_at"],
        "sections": {k: {"status": v["status"],
                         "items": [{"id": it["id"], "status": it["status"]}
                                   for it in v["items"]]}
                     for k, v in sec.items()},
        "materials": sec["E"].get("materials", {}),
        "hashes": {
            "sm3": next((it["evidence"].get("content_hash")
                         for it in sec["C"]["items"] if it["id"] == "C2"), None),
        },
    }


def render_evidence_md(ev):
    lines = [
        "# 标识合规证据包（草稿）", "",
        f"- 文件：{ev['file']}",
        f"- 容器：{ev['container']}",
        f"- 结论：{ev['verdict']}",
        f"- 标识位置：{ev['meta_found_at']}", "",
        "## 五段判定", "",
    ]
    for k, v in ev["sections"].items():
        lines.append(f"- {k}：{v['status']}")
    lines += ["", "## 备案材料清单", ""]
    for name, ok in ev["materials"].items():
        lines.append(f"- [{'x' if ok else ' '}] {name}")
    lines += ["", "## 复核方法", "",
              "1. 用本工具对同一文件重跑 `check --json`，结论应逐字节一致；",
              "2. 用 `verify --pub <公钥>` 独立验签；",
              "3. 内容摘要按 CntSel 规则重算 SM3。", ""]
    return "\n".join(lines)


def render_text(report):
    lines = [
        f"== nf-labelcheck（{report['tool']}）==",
        f"文件：{report['file']}  容器：{report['container']}"
        f"  标识位置：{report['meta_found_at']}",
        f"结论：{report['verdict']}（exit {report['exit_code']}）", "",
    ]
    for key in ("A", "B", "C", "D", "E"):
        sec = report["sections"][key]
        lines.append(f"[{sec['id']}] {sec['title']} —— {sec['status']}")
        for it in sec["items"]:
            lines.append(f"  - {it['id']} {it['status']}  {it['detail']}")
        lines.append("")
    return "\n".join(lines)
