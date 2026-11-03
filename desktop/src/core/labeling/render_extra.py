"""一份数据多种渲染：`nf-label-report/1` 报告的分享卡 / 终端 / CSV / JSONL。

输入统一是 `report.build_report()` 产出的报告字典，输出只依赖该字典本身：
- `to_svg_card()`：1200×630 分享卡 SVG（结论徽章、文件、五段、整改数、
  报告编号、免责一行）；中文用 SVG 文本，由客户端字体渲染，不引用外部资源；
- `to_console()`：终端一屏摘要（≤20 行），适合 `nf labeling report` 后直接看；
- `to_csv_row()` + `csv_header()`：单行 CSV，便于汇总到表格；
- `to_jsonl()`：紧凑 JSONL 一行，便于日志/数据管道逐行摄入；
- `selfcheck()`：对内置样例跑四个渲染器，返回 `[(检查名, 是否通过, 说明)]`。

纪律：
- 纯标准库；不联网、不落盘、不读输入文件（只认报告字典）；
- 不做业务判定，只做呈现——判定真源仍是 `checker.check_file()`；
- 错误消息带「修复指引」，调用方不用翻源码就知道怎么补齐输入；
- 输出不含 `<script>` 与外部 URL（SVG 的 `xmlns` 命名空间标识符除外）。

用法：
  from core.labeling import report, render_extra
  rep = report.build_report("样例.png")
  print(render_extra.to_console(rep))
"""

from __future__ import annotations

import copy
import csv
import html
import io
import json

from . import report as base

#: 分享卡画布（1200×630 是公众号/社媒横图的通用尺寸）
SVG_WIDTH = 1200
SVG_HEIGHT = 630
#: SVG 命名空间是**标识符**，不是待抓取的外部资源；测试/自检会先把它剔除再查外链。
SVG_NS = "http://www.w3.org/2000/svg"
CONTENT_X = 64
CONTENT_W = SVG_WIDTH - CONTENT_X * 2
CARD_GAP = 16
FONT = "'PingFang SC','Microsoft YaHei','Noto Sans CJK SC',sans-serif"

SECTION_TITLES = {
    "A": "显式标识",
    "B": "隐式标识字段",
    "C": "安全防护信息",
    "D": "内容绑定",
    "E": "备案材料",
}
STATUS_COLORS = {
    "PASS": "#22c55e",
    "WARN": "#f59e0b",
    "FAIL": "#ef4444",
    "NA": "#64748b",
}
VERDICT_LABELS = {"PASS": "通过", "WARN": "需关注", "FAIL": "不通过", "NA": "未判定"}
REQUIRED_KEYS = ("verdict", "report_id", "file", "summary", "counts",
                 "actions", "disclaimer")

#: CSV 列顺序是稳定契约：表头与数据行都按这里生成，列数天然一致。
CSV_FIELDS = (
    "report_id", "generated_at", "verdict", "exit_code",
    "container", "container_label",
    "file_name", "file_size", "file_sha256",
    "section_a", "section_b", "section_c", "section_d", "section_e",
    "items", "pass", "warn", "fail", "na", "actions",
    "meta_found_at", "tool", "version", "schema",
)


def _require(report):
    """校验报告字典的最小字段面；缺字段即抛带修复指引的 ValueError。"""
    if not isinstance(report, dict):
        raise ValueError(
            "报告必须是 dict（修复指引：用 report.build_report(path) 生成 "
            "nf-label-report/1 报告字典）")
    missing = [key for key in REQUIRED_KEYS if key not in report]
    if missing:
        raise ValueError(
            "报告缺少字段 %s（修复指引：用 report.build_report(path) 重新生成，"
            "或补齐 nf-label-report/1 必需字段）" % "、".join(missing))
    if not isinstance(report.get("file"), dict) or "name" not in report["file"]:
        raise ValueError(
            "报告 file 字段缺少 name（修复指引：用 report.build_report(path) "
            "重新生成报告）")
    if not isinstance(report.get("summary"), dict):
        raise ValueError(
            "报告 summary 必须是 A–E 状态字典（修复指引：用 "
            "report.build_report(path) 重新生成报告）")
    return report


def _file_of(report):
    return report.get("file") or {}


def _verdict_of(report):
    return str(report.get("verdict") or "NA")


def _status_color(status):
    return STATUS_COLORS.get(str(status), STATUS_COLORS["NA"])


def _xesc(value):
    """XML 文本转义：`<script>`、`&`、引号都会变成纯文本。"""
    return html.escape(str(value), quote=True)


def _clip(text, limit):
    """压成单行并截断；用于 SVG/终端里不允许换行的位置。"""
    flat = " ".join(str(text or "").split())
    if len(flat) <= limit:
        return flat
    if limit <= 1:
        return "…"
    return flat[: limit - 1] + "…"


def _size_text(size):
    try:
        n = int(size)
    except (TypeError, ValueError):
        return "大小未知"
    if n < 1024:
        return "%d 字节" % n
    if n < 1024 * 1024:
        return "%.1f KiB" % (n / 1024.0)
    return "%.1f MiB" % (n / (1024.0 * 1024.0))


def _external_refs(text):
    """返回文本里像「脚本/外部资源引用」的命中片段；SVG 命名空间先剔除。"""
    body = text.replace(SVG_NS, "")
    low = body.lower()
    hits = []
    for token in ("<script", "href=\"http", "href='http", "src=\"http",
                  "src='http", "url(http", "@import", "<image"):
        if token in low:
            hits.append(token)
    return hits


def _svg_badge(verdict):
    """右上角结论徽章：颜色由结论决定，文字仍是 SVG 文本。"""
    color = _status_color(verdict)
    label = VERDICT_LABELS.get(verdict, "未判定")
    return (
        '<g><rect x="920" y="50" width="216" height="64" rx="32" '
        'fill="%s" fill-opacity="0.16" stroke="%s" stroke-width="2"/>'
        '<text x="1028" y="91" text-anchor="middle" font-size="26" '
        'font-weight="700" fill="%s">%s · %s</text></g>'
        % (color, color, color, _xesc(verdict), _xesc(label)))


def _svg_header(report):
    """页眉：品牌、标题、文件信息、分隔线与结论徽章。"""
    title = _clip(report.get("title") or "标识体检报告", 20)
    f = _file_of(report)
    name = _clip(f.get("name") or "—", 28)
    container = _clip(report.get("container_label")
                      or report.get("container") or "未知容器", 12)
    file_line = "%s · %s · %s" % (name, container, _size_text(f.get("size")))
    verdict = _verdict_of(report)
    return "\n".join([
        '<text x="64" y="64" font-size="20" letter-spacing="3" '
        'fill="#7c93b5">%s</text>' % _xesc("NF · NINFENZ · 标识体检报告"),
        '<text x="64" y="114" font-size="40" font-weight="700" '
        'fill="#f8fafc">%s</text>' % _xesc(title),
        '<text x="64" y="152" font-size="20" fill="#a9bdd8">%s</text>'
        % _xesc(file_line),
        '<text x="1136" y="152" text-anchor="end" font-size="14" '
        'fill="#7f96b4">报告编号 %s</text>'
        % _xesc(report.get("report_id") or "—"),
        '<line x1="64" y1="184" x2="1136" y2="184" stroke="#2a405f" '
        'stroke-width="1"/>',
        _svg_badge(verdict),
    ])


def _svg_sections(report):
    """五段判定卡片：段号、判据、状态与项数。"""
    summary = report.get("summary") or {}
    sections = report.get("sections") or {}
    width = (CONTENT_W - CARD_GAP * 4) / 5.0
    parts = ['<g font-family="%s">' % _xesc(FONT)]
    for index, key in enumerate(("A", "B", "C", "D", "E")):
        status = str(summary.get(key) or "NA")
        color = _status_color(status)
        sec = sections.get(key) or {}
        items = sec.get("items") or []
        nfail = sum(1 for item in items if item.get("status") == "FAIL")
        nwarn = sum(1 for item in items if item.get("status") == "WARN")
        x = CONTENT_X + index * (width + CARD_GAP)
        parts.extend([
            '<rect x="%.1f" y="204" width="%.1f" height="168" rx="14" '
            'fill="#12233b" stroke="#2a405f"/>' % (x, width),
            '<text x="%.1f" y="238" font-size="18" fill="#9fb3cf">%s · %s'
            '</text>' % (x + 16, key, _xesc(SECTION_TITLES[key])),
            '<text x="%.1f" y="296" font-size="30" font-weight="700" '
            'fill="%s">%s</text>' % (x + 16, color, _xesc(status)),
            '<text x="%.1f" y="336" font-size="14" fill="#7f96b4">'
            '%d 项 · FAIL %d / WARN %d</text>'
            % (x + 16, len(items), nfail, nwarn),
        ])
    parts.append("</g>")
    return "\n".join(parts)


def _svg_actions(report):
    """左下整改清单：最多列 3 条，剩余条数用一行提示收口。"""
    actions = report.get("actions") or []
    parts = [
        '<text x="64" y="408" font-size="20" font-weight="700" '
        'fill="#e2e8f0">整改清单</text>',
        '<text x="160" y="408" font-size="14" fill="#7f96b4">'
        '共 %d 项（FAIL 优先）</text>' % len(actions),
    ]
    if not actions:
        parts.append('<text x="64" y="442" font-size="16" fill="#8fa6c4">'
                     '无整改项：五段判定未见 FAIL/WARN。</text>')
        return "\n".join(parts)
    for index, item in enumerate(actions[:3], 1):
        status = str(item.get("status") or "")
        parts.append(
            '<text x="64" y="%d" font-size="16" fill="#c9d7ea">%d. '
            '<tspan fill="%s">[%s]</tspan> %s.%s %s</text>'
            % (442 + (index - 1) * 30, index, _status_color(status),
               _xesc(status), _xesc(item.get("section") or "?"),
               _xesc(item.get("id") or "?"),
               _xesc(_clip(item.get("detail") or "", 30))))
    rest = len(actions) - 3
    if rest > 0:
        parts.append('<text x="64" y="532" font-size="14" fill="#7f96b4">'
                     '另有 %d 项，见 HTML/Markdown 完整报告。</text>' % rest)
    return "\n".join(parts)


def _svg_stats(report):
    """右下统计块：整改数（大字）、判定项计数与生成时间。"""
    actions = report.get("actions") or []
    counts = report.get("counts") or {}
    accent = "#f59e0b" if actions else "#22c55e"
    generated = _clip(report.get("generated_at") or "—", 26)
    return "\n".join([
        '<rect x="744" y="376" width="392" height="158" rx="16" '
        'fill="#12233b" stroke="#2a405f"/>',
        '<text x="768" y="412" font-size="16" fill="#9fb3cf">整改项 · '
        'FAIL %d / WARN %d</text>'
        % (int(counts.get("FAIL") or 0), int(counts.get("WARN") or 0)),
        '<text x="768" y="478" font-size="56" font-weight="700" fill="%s">'
        '%d</text>' % (accent, len(actions)),
        '<text x="850" y="448" font-size="14" fill="#8fa6c4">判定项 %d</text>'
        % int(counts.get("items") or 0),
        '<text x="850" y="474" font-size="14" fill="#8fa6c4">PASS %d / '
        'WARN %d</text>' % (int(counts.get("PASS") or 0),
                             int(counts.get("WARN") or 0)),
        '<text x="850" y="500" font-size="14" fill="#8fa6c4">FAIL %d / '
        'NA %d</text>' % (int(counts.get("FAIL") or 0),
                           int(counts.get("NA") or 0)),
        '<text x="768" y="522" font-size="12" fill="#7f96b4">生成 %s</text>'
        % _xesc(generated),
    ])


def to_svg_card(report):
    """报告字典 → 1200×630 分享卡 SVG 字符串（不引用外部资源）。"""
    rep = _require(report)
    title = _clip(rep.get("title") or "标识体检报告", 20)
    name = _clip(_file_of(rep).get("name") or "—", 28)
    verdict = _verdict_of(rep)
    aria = "NF 标识体检：%s · %s · 结论 %s" % (title, name, verdict)
    disclaimer = _clip(rep.get("disclaimer") or "", 74)
    schema = rep.get("schema") or base.SCHEMA
    tool = rep.get("tool") or base.TOOL
    version = rep.get("version") or base.VERSION
    parts = [
        '<svg xmlns="%s" width="%d" height="%d" viewBox="0 0 %d %d" '
        'role="img" aria-label="%s">'
        % (SVG_NS, SVG_WIDTH, SVG_HEIGHT, SVG_WIDTH, SVG_HEIGHT, _xesc(aria)),
        '<title>%s</title>' % _xesc(aria),
        '<desc>%s</desc>' % _xesc(
            "NF 标识体检分享卡；结论与五段判定来自本地自查报告。"),
        '<defs><linearGradient id="nf-bg" x1="0" y1="0" x2="1" y2="1">',
        '<stop offset="0" stop-color="#0b1220"/>',
        '<stop offset="1" stop-color="#152a44"/>',
        "</linearGradient></defs>",
        '<rect width="1200" height="630" fill="url(#nf-bg)"/>',
        '<circle cx="1080" cy="52" r="190" fill="%s" fill-opacity="0.07"/>'
        % _status_color(verdict),
        '<g font-family="%s">' % _xesc(FONT),
    ]
    parts.extend([_svg_header(rep), _svg_sections(rep), _svg_actions(rep),
                  _svg_stats(rep)])
    parts.extend([
        '<text x="64" y="574" font-size="13" fill="#8fa6c4">免责声明：%s'
        '</text>' % _xesc(disclaimer),
        '<text x="64" y="606" font-size="12" fill="#64748b">%s · %s/%s · '
        '报告编号为内容 SHA-256 前 16 位</text>'
        % (_xesc(schema), _xesc(tool), _xesc(version)),
        "</g>",
        "</svg>",
    ])
    return "\n".join(parts)


def to_console(report):
    """报告字典 → 终端一屏摘要（固定 ≤20 行）。"""
    rep = _require(report)
    f = _file_of(rep)
    counts = rep.get("counts") or {}
    summary = rep.get("summary") or {}
    actions = rep.get("actions") or []
    verdict = _verdict_of(rep)
    sections = " · ".join(
        "%s %s" % (key, summary.get(key, "NA")) for key in ("A", "B", "C", "D", "E"))
    reproduce = rep.get("reproduce") or []
    lines = [
        "NF · NINFENZ · 标识体检摘要",
        "标题：%s" % _clip(rep.get("title") or "标识体检报告", 24),
        "文件：%s · %s · %s" % (
            _clip(f.get("name") or "—", 22),
            _clip(rep.get("container_label") or rep.get("container") or "未知容器",
                  10),
            _size_text(f.get("size"))),
        "结论：%s（exit %s） · %s 项 · PASS %d / WARN %d / FAIL %d / NA %d"
        % (verdict, rep.get("exit_code"), counts.get("items", 0),
           counts.get("PASS", 0), counts.get("WARN", 0),
           counts.get("FAIL", 0), counts.get("NA", 0)),
        "五段：%s" % sections,
        "报告编号：%s · 生成：%s"
        % (rep.get("report_id"), _clip(rep.get("generated_at") or "—", 30)),
        "整改：%d 项（FAIL %d / WARN %d）"
        % (len(actions), counts.get("FAIL", 0), counts.get("WARN", 0)),
    ]
    shown = actions[:6]
    if shown:
        for index, item in enumerate(shown, 1):
            lines.append("  %d. [%s] %s.%s %s" % (
                index, item.get("status"), item.get("section"),
                item.get("id"), _clip(item.get("detail") or "", 28)))
        if len(actions) > len(shown):
            lines.append("  …另有 %d 项，见完整报告。"
                         % (len(actions) - len(shown)))
    else:
        lines.append("  无整改项：五段判定未见 FAIL/WARN。")
    lines.append("免责：%s" % _clip(rep.get("disclaimer") or "", 30))
    lines.append("复算：%s" % _clip(reproduce[0] if reproduce else "—", 52))
    lines.append("提示：完整证据见 HTML/Markdown 报告；本摘要不替代官方认定。")
    return "\n".join(lines[:20])


def csv_header():
    """CSV 表头（与 `to_csv_row()` 的字段顺序严格一致）。"""
    return ",".join(CSV_FIELDS)


def _csv_values(report):
    """按 CSV_FIELDS 顺序摊平报告字段；缺失值用空串/0，保持列数稳定。"""
    f = _file_of(report)
    counts = report.get("counts") or {}
    summary = report.get("summary") or {}
    return [
        report.get("report_id") or "",
        report.get("generated_at") or "",
        _verdict_of(report),
        report.get("exit_code"),
        report.get("container") or "",
        report.get("container_label") or "",
        f.get("name") or "",
        f.get("size"),
        f.get("sha256") or "",
        summary.get("A", "NA"),
        summary.get("B", "NA"),
        summary.get("C", "NA"),
        summary.get("D", "NA"),
        summary.get("E", "NA"),
        counts.get("items", 0),
        counts.get("PASS", 0),
        counts.get("WARN", 0),
        counts.get("FAIL", 0),
        counts.get("NA", 0),
        len(report.get("actions") or []),
        report.get("meta_found_at") or "",
        report.get("tool") or base.TOOL,
        report.get("version") or base.VERSION,
        report.get("schema") or base.SCHEMA,
    ]


def _csv_line(values):
    """csv 模块负责逗号/引号/换行的转义；去掉行尾换行，保持「单行」。"""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL).writerow(values)
    return buf.getvalue().rstrip("\r\n")


def to_csv_row(report):
    """报告字典 → 单行 CSV（字段顺序见 `csv_header()`）。"""
    return _csv_line(_csv_values(_require(report)))


def to_jsonl(report):
    """报告字典 → 紧凑 JSONL 一行（无空格分隔，便于逐行摄入）。"""
    rep = _require(report)
    f = _file_of(rep)
    counts = rep.get("counts") or {}
    summary = rep.get("summary") or {}
    record = {
        "schema": rep.get("schema") or base.SCHEMA,
        "tool": rep.get("tool") or base.TOOL,
        "version": rep.get("version") or base.VERSION,
        "generated_at": rep.get("generated_at") or "",
        "report_id": rep.get("report_id") or "",
        "file": {
            "name": f.get("name") or "",
            "size": f.get("size"),
            "sha256": f.get("sha256") or "",
        },
        "container": rep.get("container") or "",
        "container_label": rep.get("container_label") or "",
        "verdict": _verdict_of(rep),
        "exit_code": rep.get("exit_code"),
        "summary": {key: summary.get(key, "NA")
                    for key in ("A", "B", "C", "D", "E")},
        "counts": {key: counts.get(key, 0)
                   for key in ("items", "PASS", "WARN", "FAIL", "NA")},
        "actions": rep.get("actions") or [],
        "meta_found_at": rep.get("meta_found_at"),
    }
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def _sample_sections():
    """内置样例的五段结构：每段一个判定项，状态与 summary 对齐。"""
    status_map = {"A": "NA", "B": "WARN", "C": "PASS", "D": "PASS",
                  "E": "WARN"}
    sections = {}
    for key, status in status_map.items():
        sections[key] = {
            "id": key,
            "title": SECTION_TITLES[key],
            "status": status,
            "items": [{
                "id": key + "1",
                "status": status,
                "detail": "样例判定项（selfcheck 内置数据）",
                "evidence": {},
            }],
        }
    return sections


#: selfcheck 用的内置样例：字段面与 `report.build_report()` 一致（不读文件）。
_SAMPLE_REPORT = {
    "schema": base.SCHEMA,
    "tool": base.TOOL,
    "version": base.VERSION,
    "title": "GB 45438 标识体检报告（内置样例）",
    "generated_at": "2026-11-02T20:00:00+0800",
    "report_id": "0123456789abcdef",
    "file": {
        "name": "示例-图片.png",
        "path": "/tmp/示例-图片.png",
        "size": 4096,
        "sha256": "0" * 64,
    },
    "container": "png",
    "container_label": "PNG 图片",
    "meta_found_at": "tEXt:AIGC",
    "meta_raw": '{"Label":"1"}',
    "verdict": "WARN",
    "exit_code": 0,
    "summary": {"A": "NA", "B": "WARN", "C": "PASS", "D": "PASS",
                "E": "WARN"},
    "counts": {"items": 5, "PASS": 2, "WARN": 2, "FAIL": 0, "NA": 1},
    "actions": [
        {"section": "B", "id": "B1", "status": "WARN",
         "detail": "隐式标识字段不完整，建议补齐 ProduceID", "evidence": {}},
        {"section": "E", "id": "E1", "status": "WARN",
         "detail": "备案材料未随文件提供，建议随附材料清单", "evidence": {}},
    ],
    "sections": _sample_sections(),
    "preflight": {"container": "png", "size": 4096, "sha256": "0" * 64,
                  "warnings": [], "readable": True},
    "support": [],
    "reproduce": [
        "python3 scripts/nf_labeling.py check 示例-图片.png --json",
        "python3 scripts/nf_label_report.py report 示例-图片.png",
        "python3 scripts/nf_labeling.py selfcheck",
    ],
    "disclaimer": base.DISCLAIMER,
}


def sample_report():
    """返回内置样例的深拷贝，调用方可随意改动而不污染模块常量。"""
    return copy.deepcopy(_SAMPLE_REPORT)


def _safe_render(fn, report):
    """渲染器外壳：把异常转成 (空串, 说明)，让 selfcheck 能逐项报 FAIL。"""
    try:
        return fn(report), ""
    except Exception as exc:  # noqa: BLE001 —— 自检要收集失败而不是中断
        return "", "%s: %s（修复指引：核对报告字段完整性后重试）" % (
            type(exc).__name__, exc)


def _selfcheck_svg(rep):
    """SVG 三项检查：能渲染、关键字段在场、无脚本/外链。"""
    svg, err = _safe_render(to_svg_card, rep)
    rows = [("svg_card 渲染不抛错", not err,
             err or "已生成 %d 字符 SVG（%d×%d）"
             % (len(svg), SVG_WIDTH, SVG_HEIGHT))]
    fields = (str(rep.get("verdict")), str(rep.get("report_id")), "显式标识",
              "内容绑定", "整改", "免责声明")
    missing = [item for item in fields if item not in svg]
    rows.append(("svg_card 关键字段在场", bool(svg) and not missing,
                 "缺失：%s（修复指引：检查对应字段是否有值）"
                 % "、".join(missing) if missing else "结论/编号/五段/整改/免责均在"))
    hits = _external_refs(svg) if svg else ["<无 SVG>"]
    rows.append(("svg_card 无脚本与外部资源", bool(svg) and not hits,
                 "命中：%s" % "、".join(hits) if hits else "无 <script>/外链/外图"))
    return rows


def _selfcheck_text(rep):
    """控制台/CSV/JSONL 三项检查。"""
    console, err = _safe_render(to_console, rep)
    lines = console.splitlines() if console else []
    rows = [("console 一屏摘要", not err and 0 < len(lines) <= 20
             and "结论" in console and str(rep.get("report_id")) in console,
             err or "行数 %d/20，含结论与报告编号" % len(lines))]
    row_text, csv_err = _safe_render(to_csv_row, rep)
    header = csv_header().split(",")
    parsed = next(csv.reader(io.StringIO(row_text)), []) if row_text else []
    rows.append(("csv_row 与表头同宽", not csv_err and len(parsed) == len(header)
                 and parsed and parsed[0] == str(rep.get("report_id")),
                 csv_err or "列数 %d/%d，首列=报告编号" % (len(parsed), len(header))))
    line, jsonl_err = _safe_render(to_jsonl, rep)
    try:
        doc = json.loads(line) if line else {}
    except ValueError as exc:
        doc = {}
        jsonl_err = "JSON 解析失败：%s（修复指引：检查字段是否可序列化）" % exc
    if not isinstance(doc, dict):
        doc = {}
        jsonl_err = "JSONL 行顶层不是对象（修复指引：报告须序列化为对象）"
    rows.append(("jsonl 单行可解析", not jsonl_err and "\n" not in line
                 and doc.get("schema") == (rep.get("schema") or base.SCHEMA),
                 jsonl_err or "1 行 %d 字符，schema=%s"
                 % (len(line), doc.get("schema"))))
    return rows


def selfcheck():
    """对内置样例跑四个渲染器 → [(检查名, 是否通过, 说明)]。"""
    rep = sample_report()
    return _selfcheck_svg(rep) + _selfcheck_text(rep)


if __name__ == "__main__":
    for name, ok, detail in selfcheck():
        print("  %s  %s：%s" % ("PASS" if ok else "FAIL", name, detail))
