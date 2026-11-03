"""标识体检报告生成（HTML / JSON / Markdown，纯标准库、无外部资源）。

用途：把 `checker.check_file()` 的五段判定落成**客户可交付**的体检报告：
- 结论页 + 五段状态矩阵 + 逐项证据 + 整改清单；
- 内容摘要（SM3）与复算命令，便于第三方独立复核；
- 支持矩阵与已知限制（加密 PDF、视觉标识需人工复核等）；
- 免责声明（自查结果，不构成官方认定/法律意见）。

纪律：
- 纯标准库；不联网、不写外部资源（HTML 自包含，可直接打印成 PDF）；
- 只读输入文件；报告编号 = SHA-256(文件内容) 前缀 → 可内容寻址、可复算；
- 报告默认带生成时间（`--generated-at` 可固定，便于逐字节对拍）。

用法（经 `scripts/nf_label_report.py` 或 `nf labeling report` 的兄弟启动器）：
  report <file> [--out DIR] [--title 标题] [--generated-at ISO]
  batch <目录> [--out DIR] [--all]
  matrix
  selfcheck
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time

from . import checker, metadata

SCHEMA = "nf-label-report/1"
TOOL = "nf-labelcheck"
VERSION = "0.1.0"
MAX_PREVIEW = 2000

CONTAINER_LABELS = {
    "png": "PNG 图片", "jpeg": "JPEG 图片", "tiff": "TIFF 图片",
    "gif": "GIF 图片", "webp": "WebP 图片", "pdf": "PDF 文档",
    "mp4": "MP4 视频", "mp3": "MP3 音频", "wav": "WAV 音频",
    "flac": "FLAC 音频", "docx": "DOCX 文档", "ofd": "OFD 文档",
    "markdown": "Markdown 文档", "text": "纯文本",
    "xmind": "XMind 脑图", "posm": "POSM 文件", "posf": "POSF 文件",
    "uof": "UOF 文档", "sidecar": "旁车 JSON", "unknown": "未知容器",
}

#: 支持矩阵：容器 → (标识载体, 读取方式, 备注/限制)
SUPPORT_MATRIX = (
    {"container": "png", "carrier": "tEXt / iTXt / zTXt",
     "read": "标准库 zlib 解压", "limit": "—"},
    {"container": "jpeg", "carrier": "APP1 XMP / EXIF UserComment",
     "read": "标准库分段解析", "limit": "仅读 APP1，不做像素判定"},
    {"container": "tiff", "carrier": "IFD0 0x2BC / XMP",
     "read": "标准库 IFD 遍历", "limit": "多页 TIFF 只读首页"},
    {"container": "gif", "carrier": "XMP DataXMP 扩展块",
     "read": "标准库块遍历", "limit": "—"},
    {"container": "webp", "carrier": "XMP chunk",
     "read": "标准库 RIFF 解析", "limit": "—"},
    {"container": "pdf", "carrier": "Info 字典 / /Metadata XMP",
     "read": "标准库扫描 obj + FlateDecode",
     "limit": "不支持加密 PDF、对象流(ObjStm)、增量更新；"
              "Info 非 ASCII 文本可能乱码"},
    {"container": "mp4", "carrier": "moov.udta.meta keys/ilst / XMP uuid",
     "read": "标准库 box 解析", "limit": "只读元数据，不解码画面"},
    {"container": "mp3", "carrier": "ID3v2 TXXX",
     "read": "标准库帧解析", "limit": "—"},
    {"container": "wav", "carrier": "LIST/INFO 子块",
     "read": "标准库 chunk 解析", "limit": "—"},
    {"container": "flac", "carrier": "VORBIS_COMMENT",
     "read": "标准库块解析", "limit": "—"},
    {"container": "docx", "carrier": "docProps/custom.xml",
     "read": "标准库 zipfile", "limit": "—"},
    {"container": "ofd", "carrier": "CustomDatas/AIGC.xml",
     "read": "标准库 zipfile", "limit": "—"},
    {"container": "markdown", "carrier": "头注释块（AIGC JSON）",
     "read": "标准库文本解析", "limit": "—"},
    {"container": "xmind/posm/posf", "carrier": "metadata.json / meta.json",
     "read": "标准库 zipfile", "limit": "—"},
    {"container": "uof", "carrier": "_meta/meta.xml `<meta:AIGC>`",
     "read": "标准库 zipfile", "limit": "—"},
)

DISCLAIMER = (
    "本报告由本地工具对单个文件做**结构与字段级自查**，结论仅代表该文件在"
    "检查时刻的状态；不构成官方认定、法律意见或备案结论，不保证备案/评估"
    "通过。显式标识若位于像素、画面或音轨，本工具不做视觉判定，需人工或"
    "OCR/抽帧复核。报告中的数据可被第三方按「复算命令」独立复核。"
)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def support_matrix():
    """返回支持矩阵的副本（调用方不得改模块常量）。"""
    return [dict(row) for row in SUPPORT_MATRIX]


def container_label(name):
    return CONTAINER_LABELS.get(name, name)


def preflight(path, raw=None):
    """交付前预检：返回 {container, size, sha256, warnings, readable}。

    `raw` 给定时复用已读字节（build_report 只读一次文件）。
    不因不支持而抛错——把限制写进报告，让客户看到边界。
    """
    out = {"container": "unknown", "size": 0, "sha256": "",
           "warnings": [], "readable": False}
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        out["warnings"].append("文件不可读：%s（修复指引：确认路径与权限）" % exc)
        return out
    out["size"] = size
    if raw is None:
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            out["warnings"].append("文件读取失败：%s（修复指引：确认读权限）"
                                   % exc)
            raw = b""
    out["sha256"] = sha256_hex(raw)
    try:
        container = metadata.sniff(path)
    except Exception as exc:  # noqa: BLE001 —— 嗅探失败不应中断报告
        out["warnings"].append("容器嗅探失败：%s（修复指引：确认文件后缀）" % exc)
        return out
    out["container"] = container
    out["readable"] = True
    if container == "unknown":
        out["warnings"].append(
            "不支持的容器：本工具按扩展名识别；请先确认文件类型（修复指引："
            "导出为 PNG/JPEG/PDF/DOCX/Markdown 等受支持格式）")
        return out
    if size > metadata.MAX_READ:
        out["warnings"].append(
            "文件超过 %d MiB 读取上限，可能只解析到部分内容（修复指引："
            "先裁剪/转码后再送检）" % (metadata.MAX_READ // (1024 * 1024)))
    if container == "pdf":
        head = b""
        try:
            with open(path, "rb") as fh:
                head = fh.read(min(size, 512 * 1024))
        except OSError as exc:
            out["warnings"].append("PDF 头部读取失败：%s" % exc)
        if b"/Encrypt" in head:
            out["warnings"].append(
                "PDF 含 /Encrypt（加密）：元数据可能读不到（修复指引：请提供"
                "未加密原件，或先解除权限保护）")
        if b"/ObjStm" in head:
            out["warnings"].append(
                "PDF 含对象流 /ObjStm：Info 可能位于压缩对象中，本工具不解压，"
                "结论可能不完整（修复指引：提供未压缩/常规结构 PDF）")
    return out


def _actions(report):
    """把 FAIL/WARN 项抽成整改清单（按最严重优先）。"""
    order = {"FAIL": 0, "WARN": 1}
    out = []
    for key in ("A", "B", "C", "D", "E"):
        sec = report["sections"].get(key) or {}
        for item in sec.get("items") or []:
            status = item.get("status")
            if status not in order:
                continue
            out.append({
                "section": key, "id": item.get("id"), "status": status,
                "detail": item.get("detail", ""),
                "evidence": item.get("evidence") or {},
            })
    out.sort(key=lambda x: (order[x["status"]], x["section"], x["id"]))
    return out


def _counts(report):
    counts = {"items": 0, "PASS": 0, "WARN": 0, "FAIL": 0, "NA": 0}
    for sec in report["sections"].values():
        for item in sec.get("items") or []:
            status = item.get("status")
            if status in counts:
                counts[status] += 1
                counts["items"] += 1
    return counts


def build_report(path, title=None, generated_at=None):
    """生成报告字典（不落盘）。输入文件读不到时抛 FileNotFoundError。"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    body = checker.check_file(path)
    pre = preflight(path, raw)
    report = {
        "schema": SCHEMA,
        "tool": TOOL,
        "version": VERSION,
        "title": title or "GB 45438 标识体检报告",
        "generated_at": generated_at or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "report_id": sha256_hex(raw)[:16],
        "file": {
            "name": os.path.basename(path),
            "path": path,
            "size": len(raw),
            "sha256": sha256_hex(raw),
        },
        "container": body.get("container"),
        "container_label": container_label(body.get("container")),
        "meta_found_at": body.get("meta_found_at"),
        "meta_raw": (body.get("meta_raw") or "")[:MAX_PREVIEW],
        "verdict": body.get("verdict"),
        "exit_code": body.get("exit_code"),
        "summary": {k: (body["sections"][k]["status"])
                    for k in ("A", "B", "C", "D", "E")},
        "counts": _counts(body),
        "actions": _actions(body),
        "sections": body["sections"],
        "preflight": pre,
        "support": support_matrix(),
        "reproduce": [
            "python3 scripts/nf_labeling.py check %s --json" % path,
            "python3 scripts/nf_label_report.py report %s" % path,
            "python3 scripts/nf_labeling.py selfcheck",
        ],
        "disclaimer": DISCLAIMER,
    }
    return report


def _esc(value):
    return html.escape(str(value), quote=True)


def _badge(status):
    cls = {"PASS": "ok", "WARN": "warn", "FAIL": "bad"}.get(status, "na")
    return '<span class="badge %s">%s</span>' % (cls, _esc(status))


def _section_titles():
    return {"A": "显式标识", "B": "隐式标识字段", "C": "安全防护信息",
            "D": "内容绑定", "E": "备案材料"}


def _html_actions(actions):
    if not actions:
        return '<p class="muted">无整改项：五段判定未见 FAIL/WARN。</p>'
    rows = []
    for item in actions:
        rows.append(
            '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                _esc(item["section"]), _esc(item["id"]),
                _badge(item["status"]), _esc(item["detail"])))
    return ('<table><thead><tr><th>段</th><th>项</th><th>状态</th>'
            '<th>整改说明</th></tr></thead><tbody>%s</tbody></table>'
            % "".join(rows))


def _html_sections(sections):
    parts = []
    for key in ("A", "B", "C", "D", "E"):
        sec = sections.get(key) or {}
        rows = []
        for item in sec.get("items") or []:
            ev = item.get("evidence") or {}
            ev_html = ""
            if ev:
                ev_html = ('<details><summary>证据</summary><pre>%s</pre>'
                           '</details>' % _esc(
                               json.dumps(ev, ensure_ascii=False, indent=2)))
            rows.append(
                '<tr><td class="mono">%s</td><td>%s</td>'
                '<td>%s%s</td></tr>' % (
                    _esc(item.get("id")), _badge(item.get("status")),
                    _esc(item.get("detail", "")), ev_html))
        parts.append(
            '<section class="seg"><h3>%s · %s %s</h3>'
            '<table><thead><tr><th>项</th><th>状态</th><th>说明</th></tr>'
            '</thead><tbody>%s</tbody></table></section>' % (
                _esc(key), _esc(_section_titles()[key]),
                _badge(sec.get("status", "NA")), "".join(rows)))
    return "".join(parts)


def _html_matrix(rows):
    body = []
    for row in rows:
        body.append('<tr><td class="mono">%s</td><td>%s</td><td>%s</td>'
                    '<td>%s</td></tr>' % (
                        _esc(row["container"]), _esc(row["carrier"]),
                        _esc(row["read"]), _esc(row["limit"])))
    return ('<table><thead><tr><th>容器</th><th>标识载体</th><th>读取方式</th>'
            '<th>限制</th></tr></thead><tbody>%s</tbody></table>'
            % "".join(body))


CSS = """
:root{--ink:#1f2328;--muted:#667085;--line:#d0d7de;--ok:#1a7f37;
--warn:#9a6700;--bad:#cf222e;--na:#6e7781;--bg:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:900px;margin:0 auto;padding:32px 24px 56px}
.brand{color:var(--muted);font-size:12px;letter-spacing:.08em}
h1{font-size:24px;margin:6px 0 4px}
h2{font-size:17px;margin:28px 0 10px;padding-top:8px;
border-top:1px solid var(--line)}
h3{font-size:15px;margin:18px 0 8px}
.muted{color:var(--muted)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
font-size:12px;word-break:break-all}
table{width:100%;border-collapse:collapse;margin:8px 0 4px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;
vertical-align:top}
th{background:#f6f8fa;font-size:12px;color:var(--muted)}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;
font-size:12px;border:1px solid currentColor}
.badge.ok{color:var(--ok)}.badge.warn{color:var(--warn)}
.badge.bad{color:var(--bad)}.badge.na{color:var(--na)}
.verdict{font-size:22px;font-weight:600;margin:6px 0 2px}
.kv{display:grid;grid-template-columns:120px 1fr;gap:4px 12px;
margin:10px 0;font-size:13px}
.kv div:nth-child(odd){color:var(--muted)}
pre{background:#f6f8fa;border:1px solid var(--line);padding:8px;
overflow:auto;font-size:12px;white-space:pre-wrap}
details{margin:4px 0}
footer{margin-top:32px;font-size:12px;color:var(--muted);
border-top:1px solid var(--line);padding-top:10px}
@media print{
body{font-size:11pt}main{max-width:none;padding:0}
h2{page-break-after:avoid}table{page-break-inside:auto}
tr{page-break-inside:avoid}.noprint{display:none}
}
"""


def render_html(report):
    """报告字典 → 自包含 HTML（可直接 Ctrl+P 打印成 PDF）。"""
    f = report["file"]
    verdict = report["verdict"]
    summary_rows = []
    for key in ("A", "B", "C", "D", "E"):
        summary_rows.append(
            '<tr><td class="mono">%s</td><td>%s</td><td>%s</td></tr>' % (
                _esc(key), _esc(_section_titles()[key]),
                _badge(report["summary"][key])))
    pre = report["preflight"]
    warn_html = ""
    if pre.get("warnings"):
        warn_html = ('<section class="seg"><h3>预检提示</h3><ul>%s</ul>'
                     '</section>' % "".join(
                         "<li>%s</li>" % _esc(w) for w in pre["warnings"]))
    meta_html = ""
    if report.get("meta_raw"):
        meta_html = ('<details><summary>标识原文（截断至 %d 字符）</summary>'
                     '<pre>%s</pre></details>' % (
                         MAX_PREVIEW, _esc(report["meta_raw"])))
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s · %(fname)s</title>
<style>%(css)s</style></head><body><main>
<div class="brand">NF · NINFENZ · 标识体检报告</div>
<h1>%(title)s</h1>
<div class="muted">%(fname)s · %(container)s</div>
<p class="verdict">结论：%(badge)s</p>
<div class="kv">
<div>报告编号</div><div class="mono">%(rid)s</div>
<div>生成时间</div><div class="mono">%(when)s</div>
<div>文件大小</div><div class="mono">%(size)s 字节</div>
<div>文件 SHA-256</div><div class="mono">%(sha)s</div>
<div>标识位置</div><div class="mono">%(loc)s</div>
<div>判定项</div><div>%(items)s 项（FAIL %(nfail)s / WARN %(nwarn)s）</div>
</div>
<h2>五段判定</h2>
<table><thead><tr><th>段</th><th>判据</th><th>状态</th></tr></thead>
<tbody>%(summary)s</tbody></table>
<h2>整改清单</h2>
%(actions)s
%(prewarn)s
<h2>逐项明细</h2>
%(sections)s
<h2>内容绑定与复算</h2>
<p class="muted">报告可被第三方独立复核：按下列命令重跑，结论与摘要应一致。</p>
<pre>%(repro)s</pre>
%(meta)s
<h2>支持矩阵与已知限制</h2>
%(matrix)s
<h2>免责声明</h2>
<p class="muted">%(disclaimer)s</p>
<footer>%(tool)s/%(version)s · schema %(schema)s · 报告可打印为 PDF
（浏览器 Ctrl+P → 另存为 PDF）</footer>
</main></body></html>""" % {
        "title": _esc(report["title"]), "fname": _esc(f["name"]),
        "container": _esc(report["container_label"]),
        "badge": _badge(verdict), "rid": _esc(report["report_id"]),
        "when": _esc(report["generated_at"]),
        "size": _esc(f["size"]), "sha": _esc(f["sha256"]),
        "loc": _esc(report.get("meta_found_at") or "—"),
        "items": report["counts"]["items"], "nfail": report["counts"]["FAIL"],
        "nwarn": report["counts"]["WARN"],
        "summary": "".join(summary_rows),
        "actions": _html_actions(report["actions"]),
        "prewarn": warn_html, "sections": _html_sections(report["sections"]),
        "repro": _esc("\n".join(report["reproduce"])),
        "meta": meta_html, "matrix": _html_matrix(report["support"]),
        "disclaimer": _esc(report["disclaimer"]),
        "tool": _esc(TOOL), "version": _esc(VERSION),
        "schema": _esc(SCHEMA), "css": CSS,
    }


def render_markdown(report):
    """报告字典 → 纯文本 Markdown（贴微信/邮件用）。"""
    lines = [
        "# %s" % report["title"],
        "",
        "- 文件：%s（%s）" % (report["file"]["name"],
                            report["container_label"]),
        "- 报告编号：%s" % report["report_id"],
        "- 生成时间：%s" % report["generated_at"],
        "- 结论：%s" % report["verdict"],
        "",
        "## 五段判定", "",
    ]
    for key in ("A", "B", "C", "D", "E"):
        lines.append("- %s %s：%s" % (key, _section_titles()[key],
                                      report["summary"][key]))
    lines += ["", "## 整改清单", ""]
    if not report["actions"]:
        lines.append("无整改项。")
    for item in report["actions"]:
        lines.append("- [%s] %s.%s %s" % (item["status"], item["section"],
                                          item["id"], item["detail"]))
    lines += ["", "## 复算命令", "", "```", *report["reproduce"], "```", "",
              "---", report["disclaimer"], ""]
    return "\n".join(lines)


def _slug(name, report_id):
    base = re.sub(r"[^0-9A-Za-z_.-]+", "_", name)[:48].strip("_") or "file"
    return "%s-%s" % (base, report_id[:8])


def write_report(report, out_dir):
    """落盘 report.html / report.json / report.md；返回路径字典。"""
    os.makedirs(out_dir, exist_ok=True)
    stem = _slug(report["file"]["name"], report["report_id"])
    paths = {
        "html": os.path.join(out_dir, stem + ".html"),
        "json": os.path.join(out_dir, stem + ".json"),
        "md": os.path.join(out_dir, stem + ".md"),
    }
    with open(paths["html"], "w", encoding="utf-8") as fh:
        fh.write(render_html(report))
    with open(paths["json"], "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(paths["md"], "w", encoding="utf-8") as fh:
        fh.write(render_markdown(report))
    return paths


def _iter_files(root, include_all=False):
    for dirpath, dirnames, names in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(names):
            if name.startswith("."):
                continue
            path = os.path.join(dirpath, name)
            if not os.path.isfile(path):
                continue
            try:
                container = metadata.sniff(path)
            except Exception:  # noqa: BLE001 —— 单个文件嗅探失败不中断批量
                container = "unknown"
            if container == "unknown" and not include_all:
                continue
            if container == "sidecar" and not include_all:
                continue
            yield path, container


def _batch_index(items, title, generated_at):
    rows = []
    for item in items:
        rows.append(
            '<tr><td class="mono">%s</td><td>%s</td><td>%s</td>'
            '<td>%s</td><td><a href="%s">HTML</a> · <a href="%s">JSON</a>'
            '</td></tr>' % (
                _esc(item["file"]["name"]), _esc(item["container_label"]),
                _badge(item["verdict"]), item["counts"]["FAIL"],
                _esc(item["html_rel"]), _esc(item["json_rel"])))
    n = len(items)
    counts = {k: sum(1 for i in items if i["verdict"] == k)
              for k in ("PASS", "WARN", "FAIL")}
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>%(title)s</title><style>%(css)s</style></head><body><main>
<div class="brand">NF · NINFENZ · 批量标识体检</div>
<h1>%(title)s</h1>
<div class="kv"><div>生成时间</div><div class="mono">%(when)s</div>
<div>文件数</div><div>%(n)s</div>
<div>结论</div><div>PASS %(p)s / WARN %(w)s / FAIL %(f)s</div></div>
<table><thead><tr><th>文件</th><th>容器</th><th>结论</th><th>FAIL 项</th>
<th>报告</th></tr></thead><tbody>%(rows)s</tbody></table>
<footer>%(tool)s/%(version)s · schema %(schema)s</footer>
</main></body></html>""" % {
        "title": _esc(title), "css": CSS, "when": _esc(generated_at),
        "n": n, "p": counts["PASS"], "w": counts["WARN"],
        "f": counts["FAIL"], "rows": "".join(rows),
        "tool": _esc(TOOL), "version": _esc(VERSION), "schema": _esc(SCHEMA),
    }


def run_batch(root, out_dir, include_all=False, title=None,
              generated_at=None):
    """批量体检：返回 (items, index_path, summary_path)。"""
    when = generated_at or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    items = []
    errors = []
    os.makedirs(out_dir, exist_ok=True)
    reports_dir = os.path.join(out_dir, "reports")
    for path, container in _iter_files(root, include_all):
        try:
            report = build_report(path, generated_at=when)
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 —— 单文件失败要留痕不中断
            errors.append({"file": path, "error": str(exc)})
            continue
        slug = _slug(report["file"]["name"], report["report_id"])
        os.makedirs(reports_dir, exist_ok=True)
        with open(os.path.join(reports_dir, slug + ".html"), "w",
                  encoding="utf-8") as fh:
            fh.write(render_html(report))
        with open(os.path.join(reports_dir, slug + ".json"), "w",
                  encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        items.append({
            "file": report["file"], "container": report["container"],
            "container_label": report["container_label"],
            "verdict": report["verdict"],
            "counts": report["counts"], "report_id": report["report_id"],
            "html_rel": "reports/%s.html" % slug,
            "json_rel": "reports/%s.json" % slug,
        })
    index = os.path.join(out_dir, "index.html")
    with open(index, "w", encoding="utf-8") as fh:
        fh.write(_batch_index(items, title or "批量标识体检报告", when))
    summary = {
        "schema": SCHEMA + "#batch", "tool": TOOL, "version": VERSION,
        "generated_at": when, "root": root, "total": len(items),
        "counts": {k: sum(1 for i in items if i["verdict"] == k)
                   for k in ("PASS", "WARN", "FAIL")},
        "items": items, "errors": errors,
    }
    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return items, index, summary_path


def render_matrix_text():
    lines = ["容器\t标识载体\t读取方式\t限制"]
    for row in SUPPORT_MATRIX:
        lines.append("%s\t%s\t%s\t%s" % (
            row["container"], row["carrier"], row["read"], row["limit"]))
    return "\n".join(lines)


def cmd_report(args):
    try:
        report = build_report(args.file, title=args.title,
                              generated_at=args.generated_at)
    except FileNotFoundError:
        print("文件不存在：%s（修复指引：确认路径）" % args.file,
              file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report["exit_code"]
    out = args.out or (os.path.splitext(args.file)[0] + "-报告")
    paths = write_report(report, out)
    print("结论：%s（exit %d）" % (report["verdict"], report["exit_code"]))
    print("已写入：%s" % paths["html"])
    print("        %s" % paths["md"])
    print("        %s" % paths["json"])
    return report["exit_code"]


def cmd_batch(args):
    if not os.path.isdir(args.dir):
        print("目录不存在：%s（修复指引：确认路径）" % args.dir,
              file=sys.stderr)
        return 2
    out = args.out or (args.dir.rstrip("/") + "-报告")
    items, index, summary = run_batch(
        args.dir, out, include_all=args.all, title=args.title,
        generated_at=args.generated_at)
    counts = {k: sum(1 for i in items if i["verdict"] == k)
              for k in ("PASS", "WARN", "FAIL")}
    print("批量完成：%d 个文件 · PASS=%d WARN=%d FAIL=%d"
          % (len(items), counts["PASS"], counts["WARN"], counts["FAIL"]))
    print("汇总页：%s" % index)
    print("清单：%s" % summary)
    return 1 if counts["FAIL"] else 0


def cmd_matrix(args):
    print(render_matrix_text())
    return 0


def cmd_selfcheck(args):
    ok = True
    try:
        rows = support_matrix()
        print("  PASS  支持矩阵 %d 行" % len(rows))
        assert all({"container", "carrier", "read", "limit"} <= set(r)
                   for r in rows)
        print("  PASS  支持矩阵字段完整")
    except Exception as exc:  # noqa: BLE001
        print("  FAIL  支持矩阵：%s" % exc)
        ok = False
    print("报告模块自检：%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def build_parser():
    import argparse
    p = argparse.ArgumentParser(
        prog="nf-label-report",
        description="标识体检报告生成（HTML/JSON/Markdown，纯标准库）")
    p.add_argument("--version", action="version",
                   version="nf-label-report %s" % VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report", help="为单个文件生成体检报告")
    r.add_argument("file")
    r.add_argument("--out", help="输出目录（默认 <文件>-报告/）")
    r.add_argument("--title", help="报告标题")
    r.add_argument("--generated-at", help="固定生成时间（ISO 字符串，便于对拍）")
    r.add_argument("--json", action="store_true", help="只打 JSON 到 stdout")
    r.set_defaults(func=cmd_report)
    b = sub.add_parser("batch", help="批量体检一个目录")
    b.add_argument("dir")
    b.add_argument("--out", help="输出目录（默认 <目录>-报告/）")
    b.add_argument("--title", help="汇总页标题")
    b.add_argument("--generated-at", help="固定生成时间（ISO 字符串）")
    b.add_argument("--all", action="store_true",
                   help="含未知容器（默认只处理可识别容器）")
    b.set_defaults(func=cmd_batch)
    sub.add_parser("matrix", help="打印支持矩阵").set_defaults(func=cmd_matrix)
    sub.add_parser("selfcheck", help="报告模块自检").set_defaults(
        func=cmd_selfcheck)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
