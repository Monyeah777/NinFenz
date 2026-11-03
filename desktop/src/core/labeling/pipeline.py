"""标识体检价值链集大成：一次调用串起报告、平台规则、复测、交叉认证与渲染。

设计纪律：
- **纯标准库**，不 import 第三方；不联网；只读输入文件（`save_outputs` 除外）；
- 可选子系统**全部惰性导入**（`_load`），缺件时按子系统降级并给出修复指引，
  绝不因并行未落盘而让基础体检中断；`selfcheck()` 逐项报缺口；
- 失败消息统一带「修复指引」，方便调用方直接把错误转给用户；
- 结果 schema 固定为 `nf-label-pipeline/1`，顶层恒有
  `report / platform_eval / recheck / xcheck / renders` 五键。

约定接口（并行会话产出，按需 import）：
- `report.build_report(path, title=None, generated_at=None) -> dict`
- `render_extra.to_console(report)` / `to_svg_card(report)` / `to_csv_row(report)` /
  `csv_header()`
- `recheck.build_record(before, after)` / `history_append(history, record)`
- `platform_rules.platforms()` / `evaluate(report, platform)`
- `xcheck.verify(path, report)`
- `metadata_extra.sniff_extra(path)` / `extract_extra(path)`
"""

from __future__ import annotations

import csv
import html
import importlib
import io
import json
import os
import tempfile
import time

SCHEMA = "nf-label-pipeline/1"
SELFCHECK_SCHEMA = "nf-label-selfcheck/1"
TOOL = "nf-labelcheck"
VERSION = "0.1.0"

#: 子系统 → 约定接口（selfcheck / 契约核对共用；只列**非 report** 的也必须可降级）。
SUBSYSTEMS = {
    "report": ("build_report", "render_html"),
    "render_extra": ("to_console", "to_svg_card", "to_csv_row", "csv_header"),
    "recheck": ("build_record", "history_append"),
    "platform_rules": ("platforms", "evaluate"),
    "xcheck": ("verify",),
    "metadata_extra": ("sniff_extra", "extract_extra"),
}
CSV_HEADER = ("report_id,file_name,container,verdict,A,B,C,D,E,count_pass,count_warn,count_fail")


def _now(): return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _api_text(name): return "、".join(SUBSYSTEMS.get(name, ()))


def _missing_hint(name, exc):
    """统一的缺件消息：点名模块、接口与修复动作（R4 风格的「错误即微型文档」）。"""
    return (
        "缺少子系统 %s（%s）。修复指引：确认 desktop/src/core/labeling/%s.py 已落盘，"
        "导出接口 %s，并以 PYTHONPATH=desktop/src 运行；可调用 "
        "core.labeling.pipeline.selfcheck() 逐项核对缺口。"
        % (name, exc, name, _api_text(name))
    )


def _load(name):
    """惰性导入子系统；失败统一抛带修复指引的 ImportError。"""
    try:
        return importlib.import_module("%s.%s" % (__package__, name))
    except Exception as exc:  # noqa: BLE001 —— 导入期错误也要转成可读缺件
        raise ImportError(_missing_hint(name, exc)) from exc


def _try_load(name):
    """→ (module, error_text)：可选子系统缺失时返回 (None, 修复指引)。"""
    try:
        return _load(name), None
    except ImportError as exc:
        return None, str(exc)


def _contract_missing(name, module):
    """列出模块里缺失/不可调用的约定接口。"""
    return [fn for fn in SUBSYSTEMS.get(name, ())
            if not callable(getattr(module, fn, None))]


def selfcheck():
    """验证各子系统可导入、约定接口在场；缺哪个报哪条（含修复指引）。"""
    checks = []
    for name in SUBSYSTEMS:
        module, err = _try_load(name)
        if module is None:
            checks.append({"name": name, "module": "core.labeling." + name,
                           "ok": False, "missing": list(SUBSYSTEMS[name]),
                           "hint": err})
            continue
        missing = _contract_missing(name, module)
        hint = ""
        if missing:
            hint = ("子系统 %s 接口不全，缺 %s。修复指引：补齐导出接口 %s，"
                    "或先按降级路径运行。" % (name, "、".join(missing),
                                             _api_text(name)))
        checks.append({"name": name, "module": "core.labeling." + name,
                       "ok": not missing, "missing": missing, "hint": hint})
    missing_names = [c["name"] for c in checks if not c["ok"]]
    return {
        "schema": SELFCHECK_SCHEMA,
        "tool": TOOL,
        "version": VERSION,
        "generated_at": _now(),
        "status": "PASS" if not missing_names else "FAIL",
        "ok": not missing_names,
        "checks": checks,
        "missing": missing_names,
    }


# ---- 渲染层：render_extra 在场用其产物，缺件用内置纯标准库兜底 ----

def _fallback_svg_card(report):
    """兜底 SVG 卡（自包含、无外部资源；字段全部转义）。"""
    verdict = str(report.get("verdict") or "UNKNOWN")
    color = {"PASS": "#2e7d32", "WARN": "#ef6c00",
             "FAIL": "#c62828"}.get(verdict, "#455a64")
    counts = report.get("counts") or {}
    summary = report.get("summary") or {}
    name = html.escape(str((report.get("file") or {}).get("name") or "未命名"))
    title = html.escape(str(report.get("title") or "标识体检卡"))
    bars = []
    for idx, key in enumerate(("A", "B", "C", "D", "E")):
        status = html.escape(str(summary.get(key) or "NA"))
        y = 150 + idx * 26
        bars.append('<text x="40" y="%d" font-size="14">%s</text>'
                    '<text x="90" y="%d" font-size="14" fill="#37474f">%s</text>'
                    % (y, key, y, status))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="420" '
        'viewBox="0 0 720 420" role="img" aria-label="标识体检卡">'
        '<rect width="720" height="420" fill="#ffffff"/>'
        '<rect x="0" y="0" width="720" height="8" fill="%s"/>'
        '<text x="40" y="56" font-size="24" font-weight="bold">%s</text>'
        '<text x="40" y="86" font-size="14" fill="#546e7a">%s</text>'
        '<text x="40" y="122" font-size="20" font-weight="bold" fill="%s">'
        '结论：%s</text>%s'
        '<text x="40" y="330" font-size="13" fill="#607d8b">'
        '通过 %s · 警告 %s · 失败 %s · 不适用 %s</text>'
        '<text x="40" y="360" font-size="12" fill="#90a4ae">'
        '报告编号 %s · 由 %s 生成</text>'
        '</svg>'
        % (color, title, name, color, html.escape(verdict), "".join(bars),
           counts.get("PASS", 0), counts.get("WARN", 0), counts.get("FAIL", 0),
           counts.get("NA", 0), html.escape(str(report.get("report_id") or "")),
           html.escape(TOOL))
    )


def _fallback_console(report):
    """兜底人读摘要：结论 + 五段 + 整改前三条。"""
    lines = [
        "== %s ==" % report.get("title", "标识体检"),
        "文件：%s" % (report.get("file") or {}).get("name", ""),
        "结论：%s（exit %s）" % (report.get("verdict"), report.get("exit_code")),
    ]
    summary = report.get("summary") or {}
    for key in ("A", "B", "C", "D", "E"):
        lines.append("  [%s] %s" % (key, summary.get(key, "NA")))
    actions = report.get("actions") or []
    if actions:
        lines.append("整改（前 3 条）：")
        for item in actions[:3]:
            lines.append("  - %s/%s %s" % (item.get("section"), item.get("id"),
                                           item.get("status")))
    counts = report.get("counts") or {}
    lines.append("计数：PASS %s / WARN %s / FAIL %s / NA %s"
                 % (counts.get("PASS", 0), counts.get("WARN", 0),
                    counts.get("FAIL", 0), counts.get("NA", 0)))
    return "\n".join(lines)


def _csv_text(values):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(values)
    return buf.getvalue()


def _fallback_csv_row(report):
    """兜底 CSV 行：列与 `CSV_HEADER` 一一对应。"""
    summary = report.get("summary") or {}
    counts = report.get("counts") or {}
    return _csv_text([
        report.get("report_id", ""),
        (report.get("file") or {}).get("name", ""),
        report.get("container", ""),
        report.get("verdict", ""),
        summary.get("A", ""), summary.get("B", ""), summary.get("C", ""),
        summary.get("D", ""), summary.get("E", ""),
        counts.get("PASS", 0), counts.get("WARN", 0), counts.get("FAIL", 0),
    ])


def _join_csv(header, row):
    return header.rstrip("\r\n") + "\n" + row.rstrip("\r\n") + "\n"


def _render_all(report, degraded, missing):
    """→ renders 字典；render_extra 缺件/单函数异常时按项降级。"""
    module, err = _try_load("render_extra")
    fallbacks = {
        "console": _fallback_console,
        "svg": _fallback_svg_card,
        "csv_row": _fallback_csv_row,
        "csv_header": lambda _r: CSV_HEADER,
    }
    if module is None:
        missing.add("render_extra")
        degraded.append({"module": "render_extra", "api": "*",
                         "error": err, "fallback": "内置 SVG/文本/CSV 渲染"})
        out = {key: fn(report) for key, fn in fallbacks.items()}
        out["csv"] = _join_csv(out["csv_header"], out["csv_row"])
        return out

    out = {}
    apis = {"console": "to_console", "svg": "to_svg_card",
            "csv_row": "to_csv_row", "csv_header": "csv_header"}
    for key, fn_name in apis.items():
        fn = getattr(module, fn_name, None)
        if not callable(fn):
            out[key] = fallbacks[key](report)
            missing.add("render_extra")
            degraded.append({"module": "render_extra", "api": fn_name,
                             "error": "接口不在场",
                             "fallback": "内置渲染"})
            continue
        try:
            value = fn() if key == "csv_header" else fn(report)
            out[key] = value if isinstance(value, str) else str(value)
        except Exception as exc:  # noqa: BLE001 —— 渲染失败不应毁掉体检结论
            out[key] = fallbacks[key](report)
            degraded.append({"module": "render_extra", "api": fn_name,
                             "error": str(exc), "fallback": "内置渲染"})
    out["csv"] = _join_csv(out["csv_header"], out["csv_row"])
    return out


# ---- 历史文件：JSON，兼容 list / {"entries": [...]} / report.json ----

def _entries_of(doc):
    """把历史文档规范成 list；坏件抛带修复指引的 ValueError。"""
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        entries = doc.get("entries")
        if isinstance(entries, list):
            return entries
        if doc.get("schema") == "nf-label-report/1":
            return [doc]
    raise ValueError(
        "历史文件格式不支持（修复指引：应为 JSON 数组，或含 entries 数组的对象，"
        "例如 {\"schema\": \"nf-label-history/1\", \"entries\": []}）")


def load_history(history):
    """读取历史：路径（不存在视为空）或 list；返回可追加的 list。"""
    if isinstance(history, (str, bytes, os.PathLike)):
        path = os.fspath(history)
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError) as exc:
            raise ValueError(
                "历史文件读取失败：%s：%s（修复指引：确认路径可读、内容为合法 JSON；"
                "损坏时先备份再重建）" % (path, exc)) from exc
        return _entries_of(doc)
    if isinstance(history, list):
        return history
    if isinstance(history, dict):
        return _entries_of(history)
    raise TypeError(
        "history 参数类型不支持：%r（修复指引：传 JSON 文件路径或 list）"
        % type(history).__name__)


def save_history(path, entries):
    """把历史原子写入 JSON（临时文件 + os.replace，读者不会看到半截）。"""
    path = os.fspath(path)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    # 写成纯数组：与 recheck.load_history / save_history 的格式互通。
    text = json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".nf-history-", dir=parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise OSError(
            "历史文件写入失败：%s：%s（修复指引：确认目录可写、磁盘空间充足）"
            % (path, exc)) from exc
    return path


def _entry_report(entry):
    """从历史条目里取出报告快照（兼容裸 report / {report} / {after}）。"""
    if not isinstance(entry, dict):
        return None
    if entry.get("schema") == "nf-label-report/1":
        return entry
    for key in ("report", "after"):
        value = entry.get(key)
        if isinstance(value, dict) and value.get("schema") == "nf-label-report/1":
            return value
    return None


def _same_file(report, entry, candidate):
    """同文件判据：sha256 优先，缺失时退回绝对路径。"""
    want = (report.get("file") or {}).get("sha256")
    have = ((entry.get("file") or {}).get("sha256")
            or (candidate.get("file") or {}).get("sha256"))
    if want and have:
        return want == have
    want_path = (report.get("file") or {}).get("path")
    have_path = ((entry.get("file") or {}).get("path")
                 or (candidate.get("file") or {}).get("path"))
    return bool(want_path and have_path
                and os.path.abspath(want_path) == os.path.abspath(have_path))


def _find_previous(entries, report):
    """→ (上一份同文件报告, 对应条目)；没有则 (None, None)。"""
    for entry in reversed(entries):
        candidate = _entry_report(entry)
        if candidate is None:
            continue
        if _same_file(report, entry, candidate):
            return candidate, entry
    return None, None


def _brief(report):
    return {"report_id": report.get("report_id"), "generated_at": report.get("generated_at"),
            "verdict": report.get("verdict"), "sha256": (report.get("file") or {}).get("sha256")}


def _diff(before, after):
    before_counts = before.get("counts") or {}
    after_counts = after.get("counts") or {}
    return {
        "sha256_same": _brief(before)["sha256"] == _brief(after)["sha256"],
        "verdict_before": before.get("verdict"),
        "verdict_after": after.get("verdict"),
        "verdict_changed": before.get("verdict") != after.get("verdict"),
        "counts_delta": {key: int(after_counts.get(key, 0))
                         - int(before_counts.get(key, 0))
                         for key in ("PASS", "WARN", "FAIL", "NA")},
    }


def _record_entry(record, report, previous):
    """把复测记录包成历史条目：附带报告快照，下一轮才找得到「上一份」。"""
    entry = dict(record) if isinstance(record, dict) else {"record": record}
    entry.setdefault("schema", "nf-label-recheck-entry/1")
    entry["file"] = {"path": (report.get("file") or {}).get("path"),
                     "name": (report.get("file") or {}).get("name"),
                     "sha256": (report.get("file") or {}).get("sha256")}
    entry["report"] = report
    entry["at"] = entry.get("at") or _now()
    if previous is not None:
        entry["previous_report_id"] = previous.get("report_id")
    return entry


def _append_record(entries, entry, module, degraded):
    """优先走 recheck.history_append；异常时退回 list.append（并记录降级）。"""
    fn = getattr(module, "history_append", None) if module is not None else None
    if callable(fn):
        try:
            returned = fn(entries, entry)
            if isinstance(returned, list) and returned is not entries:
                entries[:] = returned
            return
        except Exception as exc:  # noqa: BLE001 —— 追加失败退回本地 list
            degraded.append({"module": "recheck", "api": "history_append",
                             "error": str(exc), "fallback": "list.append"})
    entries.append(entry)


def _recheck(report, history, degraded, missing):
    """历史给定时：找同文件上一份 → build_record → 追加；缺件则降级记录。"""
    if history is None:
        return None, None
    is_path = isinstance(history, (str, bytes, os.PathLike))
    entries = load_history(history)
    module, err = _try_load("recheck")
    if module is None:
        missing.add("recheck")
    else:
        absent = _contract_missing("recheck", module)
        if absent:
            missing.add("recheck")
            err = ("子系统 recheck 接口不全，缺 %s。修复指引：补齐 %s 后重跑；"
                   "当前按降级记录继续。" % ("、".join(absent),
                                          _api_text("recheck")))
            module = None
    previous, _entry = _find_previous(entries, report)
    before_len = len(entries)
    if previous is None:
        # 首次见到该文件：把「当前报告」作为基线写入历史，下一轮才有上一份可比。
        baseline = {"schema": "nf-label-recheck/1",
                    "recheck_id": "base-" + str(report.get("report_id") or ""),
                    "status": "FIRST", "available": module is not None,
                    "previous": None}
        entry = _record_entry(baseline, report, None)
        _append_record(entries, entry, module, degraded)
        result = {
            "schema": "nf-label-recheck/1", "available": module is not None,
            "status": "FIRST", "previous": None, "record": None,
            "entry": entry, "history_appended": True,
            "hint": "历史中无同文件上一份报告（修复指引：已写入基线，"
                    "下次同文件体检即可生成复测对比）。",
        }
        if err:
            result["hint"] += " " + err
    else:
        record = None
        if module is not None:
            try:
                record = module.build_record(previous, report)
            except Exception as exc:  # noqa: BLE001 —— 单次复测失败不毁体检
                degraded.append({"module": "recheck", "api": "build_record",
                                 "error": str(exc), "fallback": "内置 verdict 对比"})
                module = None
                err = ("recheck.build_record 失败：%s（修复指引：检查两份报告是否"
                       "同 schema、字段完整）" % exc)
        if record is None:
            record = {
                "schema": "nf-label-recheck/1", "available": False,
                "recheck_id": "fallback-%s-%s" % (previous.get("report_id"),
                                                  report.get("report_id")),
                "status": "UNAVAILABLE", "previous": _brief(previous),
                "current": _brief(report), "changes": _diff(previous, report),
                "hint": err or "recheck 子系统缺失（修复指引：补齐后可生成完整复测记录）",
            }
        entry = _record_entry(record, report, previous)
        _append_record(entries, entry, module, degraded)
        result = {
            "schema": "nf-label-recheck/1",
            "available": bool(isinstance(record, dict)
                              and record.get("available", True)),
            "status": (record.get("status") if isinstance(record, dict) else None)
                      or ("OK" if module is not None else "UNAVAILABLE"),
            "previous": _brief(previous), "record": record, "entry": entry,
            "history_appended": True,
        }
        if not result["available"]:
            result["hint"] = err
    saved = False
    if is_path and len(entries) != before_len:
        save_history(history, entries)
        saved = True
    info = {"given": True, "source": "file" if is_path else "memory",
            "path": os.fspath(history) if is_path else None,
            "entries": len(entries), "appended": len(entries) != before_len,
            "saved": saved}
    return result, info


# ---- 平台规则 / 交叉认证 / 元数据扩展：全部按需、全部可降级 ----

def _platform_eval(report, platform, degraded, missing):
    module, err = _try_load("platform_rules")
    if module is None:
        missing.add("platform_rules")
        return {"schema": "nf-label-platform/1", "available": False,
                "status": "UNAVAILABLE", "platform": platform,
                "verdict": "UNKNOWN", "hint": err}
    absent = _contract_missing("platform_rules", module)
    if absent:
        missing.add("platform_rules")
        return {"schema": "nf-label-platform/1", "available": False,
                "status": "UNAVAILABLE", "platform": platform,
                "verdict": "UNKNOWN",
                "hint": "平台规则接口不全，缺 %s（修复指引：补齐 %s）"
                        % ("、".join(absent), _api_text("platform_rules"))}
    known = []
    try:
        known = list(module.platforms())
    except Exception as exc:  # noqa: BLE001 —— 平台清单不可读不阻塞判定
        degraded.append({"module": "platform_rules", "api": "platforms",
                         "error": str(exc), "fallback": "空清单"})
    try:
        got = module.evaluate(report, platform)
    except Exception as exc:  # noqa: BLE001 —— 未知平台也不许炸穿管线
        degraded.append({"module": "platform_rules", "api": "evaluate",
                         "error": str(exc), "fallback": "ERROR 状态"})
        return {"schema": "nf-label-platform/1", "available": True,
                "status": "ERROR", "platform": platform, "verdict": "UNKNOWN",
                "known_platforms": known,
                "hint": "平台规则求值失败：%s（修复指引：确认 platform 名称在 "
                        "platforms() 清单内，或检查规则表完整性）" % exc}
    if not isinstance(got, dict):
        got = {"result": got}
    if got.get("overall"):
        got.setdefault("verdict", got["overall"])
        got.setdefault("status", got["overall"])
    got.setdefault("platform", platform)
    if known:
        got.setdefault("known_platforms", known)
    return got


def _xcheck(path, report, degraded, missing):
    module, err = _try_load("xcheck")
    if module is None:
        missing.add("xcheck")
        return {"schema": "nf-label-xcheck/1", "available": False,
                "status": "UNAVAILABLE", "report_id": report.get("report_id"),
                "hint": err}
    absent = _contract_missing("xcheck", module)
    if absent:
        missing.add("xcheck")
        return {"schema": "nf-label-xcheck/1", "available": False,
                "status": "UNAVAILABLE", "report_id": report.get("report_id"),
                "hint": "交叉认证接口不全，缺 %s（修复指引：补齐 verify(path, report)）"
                        % "、".join(absent)}
    try:
        got = module.verify(path, report)
    except Exception as exc:  # noqa: BLE001 —— 交叉认证失败记 ERROR，不中断交付
        degraded.append({"module": "xcheck", "api": "verify",
                         "error": str(exc), "fallback": "ERROR 状态"})
        return {"schema": "nf-label-xcheck/1", "available": False,
                "status": "ERROR", "report_id": report.get("report_id"),
                "hint": "交叉认证失败：%s（修复指引：确认文件与报告来自同一份字节，"
                        "或检查 verify 签名）" % exc}
    if not isinstance(got, dict):
        got = {"result": got}
    got.setdefault("schema", "nf-label-xcheck/1")
    got.setdefault("available", True)
    if not got.get("status"):
        got["status"] = ("CONFLICT" if got.get("conflict")
                         else str(got.get("trust") or "UNKNOWN").upper())
    return got


def _metadata_extra(path, report, degraded, missing):
    module, err = _try_load("metadata_extra")
    if module is None:
        missing.add("metadata_extra")
        return {"available": False, "status": "UNAVAILABLE", "hint": err}
    absent = _contract_missing("metadata_extra", module)
    out = {"available": True, "status": "OK", "sniff": None, "extract": None,
           "errors": []}
    if absent:
        missing.add("metadata_extra")
        out.update({"available": False, "status": "UNAVAILABLE",
                    "hint": "元数据扩展接口不全，缺 %s（修复指引：补齐 %s）"
                            % ("、".join(absent), _api_text("metadata_extra"))})
        return out
    for fn_name, key in (("sniff_extra", "sniff"), ("extract_extra", "extract")):
        try:
            out[key] = getattr(module, fn_name)(path)
        except Exception as exc:  # noqa: BLE001 —— 附加元数据不是交付前提
            out["errors"].append({"api": fn_name, "error": str(exc)})
            degraded.append({"module": "metadata_extra", "api": fn_name,
                             "error": str(exc), "fallback": "字段置 None"})
    if out["errors"]:
        out["status"] = "PARTIAL"
    return out


# ---- 对外主入口 ----

def evaluate(path, platform=None, history=None, title=None):
    """跑完整价值链，返回 `nf-label-pipeline/1` 结果字典（不落盘）。

    - `path`：被测文件；不存在抛 FileNotFoundError（带修复指引）；
    - `platform`：给定时走 platform_rules.evaluate；未知平台由规则层判 UNKNOWN；
    - `history`：JSON 路径或 list；给定时找同文件上一份报告并追加复测记录；
    - `title`：报告标题。

    可选子系统（render_extra/recheck/platform_rules/xcheck/metadata_extra）
    缺失或单次失败时**降级继续**，缺件写入 `missing` / `degraded`——
    基础体检永远可用。返回值顶层恒含 report/platform_eval/recheck/xcheck/renders。
    """
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "输入文件不存在或不是普通文件：%s（修复指引：确认路径拼写与读权限；"
            "支持 PNG/JPEG/PDF/DOCX 等受支持容器）" % path)
    report_module, rep_err = _try_load("report")
    if report_module is None:
        raise ImportError(rep_err)
    report = _load("extra_integration").build_or_main(path, title, report_module)

    degraded = []
    missing = set()
    platform_result = (None if platform is None
                       else _platform_eval(report, platform, degraded, missing))
    recheck_result, history_info = _recheck(report, history, degraded, missing)
    xcheck_result = _xcheck(path, report, degraded, missing)
    metadata = _metadata_extra(path, report, degraded, missing)
    renders = _render_all(report, degraded, missing)
    renders["html"] = report_module.render_html(report)
    return {
        "schema": SCHEMA,
        "tool": TOOL,
        "version": VERSION,
        "generated_at": _now(),
        "input": {"path": path,
                  "name": (report.get("file") or {}).get("name"),
                  "sha256": (report.get("file") or {}).get("sha256")},
        "verdict": report.get("verdict"),
        "exit_code": report.get("exit_code"),
        "report": report,
        "platform_eval": platform_result,
        "recheck": recheck_result,
        "xcheck": xcheck_result,
        "metadata": metadata,
        "renders": renders,
        "history": history_info,
        "missing": sorted(missing),
        "degraded": degraded,
    }


#: save_outputs 的固定文件名（键 → 落盘名）。
OUTPUT_NAMES = {
    "html": "report.html", "json": "report.json", "summary": "summary.txt",
    "svg": "card.svg", "csv": "row.csv", "recheck": "recheck.json",
    "xcheck": "xcheck.json",
}


def _write_text(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")


def save_outputs(result, out_dir):
    """落盘七件套；返回 {键: 绝对路径}。

    report.html / report.json / summary.txt / card.svg / row.csv /
    recheck.json / xcheck.json —— 无论可选子系统是否在场，七件都齐全。
    """
    out_dir = os.fspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    report = result.get("report") or {}
    renders = result.get("renders") or {}
    payloads = {
        "html": renders.get("html") or "",
        "json": json.dumps(report, ensure_ascii=False, indent=2),
        "summary": renders.get("console") or "",
        "svg": renders.get("svg") or "",
        "csv": renders.get("csv") or _join_csv(
            renders.get("csv_header") or CSV_HEADER,
            renders.get("csv_row") or ""),
        "recheck": json.dumps(
            result.get("recheck") or {"schema": "nf-label-recheck/1",
                                      "status": "NONE"},
            ensure_ascii=False, indent=2),
        "xcheck": json.dumps(
            result.get("xcheck") or {"schema": "nf-label-xcheck/1",
                                     "status": "NONE"},
            ensure_ascii=False, indent=2),
    }
    paths = {}
    for key, name in OUTPUT_NAMES.items():
        target = os.path.join(out_dir, name)
        _write_text(target, payloads[key])
        paths[key] = target
    return paths


def summary_text(result):
    """给 CLI 的人读摘要：渲染摘要 + 平台/复测/交叉认证/缺件状态。"""
    lines = [(result.get("renders") or {}).get("console") or ""]
    if result.get("platform_eval") is not None:
        pe = result["platform_eval"]
        lines.append("平台：%s → %s" % (pe.get("platform"),
                                       pe.get("verdict") or pe.get("status")))
    if result.get("recheck") is not None:
        rc = result["recheck"]
        lines.append("复测：%s（追加 %s）" % (rc.get("status"),
                                          rc.get("history_appended")))
    xc = result.get("xcheck") or {}
    lines.append("交叉认证：%s" % (xc.get("status") or xc.get("verdict")
                                or "UNKNOWN"))
    if result.get("missing"):
        lines.append("降级模块：%s（修复指引：跑 pipeline.selfcheck() 看逐项缺口）"
                     % "、".join(result["missing"]))
    return "\n".join(line for line in lines if line)
