"""检测→建议→复测闭环：复测指纹、记录、历史与摘要（纯标准库）。

作者：impl（DSH agent）· 2026-11-02

用途：
- fingerprint()：固化一次送检文件的可复算身份（整文件 SHA-256 / 大小 /
  容器 / CntSel），用于证明「复测的是同一份内容」。
- build_record()：对齐两次 checker.check_file / report.build_report 结果，
  产出 nf-label-recheck/1 记录（逐项状态迁移 + 修复/遗留/回退清单）。
- history_append() / load_history() / save_history()：沉淀复测历史；
  同 recheck_id 覆盖（幂等）。
- summary()：一句话人读摘要。

状态语义（transitions 的 state 字段）：
- fixed：严重度下降（FAIL→WARN/PASS 或 WARN→PASS）；
- regressed：严重度上升（PASS→WARN/FAIL 或 WARN→FAIL）；
- unchanged：状态相同，或 NA 参与迁移（NA 表示判据未适用，不判方向）；
- new / removed：该 id 只出现在 after / before。
fixed / remaining / regressed 三个清单只收「逐项 id」（不含 A–E 段汇总）：
fixed = 已达标（after PASS 且此前为 FAIL/WARN），remaining = after 仍为
FAIL/WARN，regressed = 本次变差。遗留与回退可能重叠（回退项仍未达标）。

纪律：纯标准库；不 import 第三方；错误消息带修复指引；代码 ≤80 列。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import metadata

SCHEMA = "nf-label-recheck/1"

#: 五段判定的固定顺序（与 checker 输出一致）。
SECTION_KEYS = ("A", "B", "C", "D", "E")

#: 严重度秩：越大越差；NA / 未知不参与方向判定。
STATUS_RANK = {"PASS": 0, "WARN": 1, "FAIL": 2}

#: 历史记录里可识别的时间字段（ISO-8601 字符串，按字典序即时间序）。
TIME_KEYS = ("created_at", "generated_at", "saved_at")


# ---------------------------------------------------------------- 指纹
def _read_bytes(path):
    """读整文件（带大小上限）；失败给带修复指引的 ValueError。"""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise ValueError(
            "无法读取文件：%s（%s）（修复指引：确认路径存在且当前用户可读）"
            % (path, exc)
        )
    if size > metadata.MAX_READ:
        raise ValueError(
            "文件过大（%d 字节 > %d）：%s（修复指引：先裁剪或转码后再复测）"
            % (size, metadata.MAX_READ, path)
        )
    try:
        return p.read_bytes()
    except OSError as exc:
        raise ValueError(
            "无法读取文件：%s（%s）（修复指引：确认读权限或文件未被占用）"
            % (path, exc)
        )


def fingerprint(path) -> dict:
    """返回 ``{"sha256","size","container","cntsel"}``。

    container 用 metadata.sniff；cntsel 取 metadata.content_bytes_for 的
    第一个元素（取不到就 None，不影响整文件指纹）。
    """
    data = _read_bytes(path)
    try:
        container = metadata.sniff(path)
    except (ValueError, OSError) as exc:
        raise ValueError(
            "容器嗅探失败：%s（%s）（修复指引：确认文件格式完整后重试）"
            % (path, exc)
        )
    cntsel = None
    try:
        cntsel = metadata.content_bytes_for(path, container)[0]
    except Exception:  # noqa: BLE001 —— 取不到内容字节只记 None
        cntsel = None
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "container": container,
        "cntsel": cntsel,
    }


# ---------------------------------------------------------------- 记录
def _canonical_id(report: dict) -> str:
    """报告没有 report_id 时，用规范化 JSON 的 SHA-256 前 16 位兜底。"""
    text = json.dumps(report, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _snapshot(report, side: str) -> dict:
    """从判定报告抽 {report_id, file_sha256, verdict}（兼容两种报告形状）。

    支持：
    - report.build_report：report_id + file.sha256；
    - checker.check_file：无 id/sha，report_id 用报告内容哈希兜底，
      file_sha256 记 None（调用方若已有 fingerprint 可自行补上）。
    """
    if not isinstance(report, dict):
        raise ValueError(
            "%s 应为判定报告 dict，实际 %s（修复指引：传 checker.check_file "
            "或 report.build_report 的返回值）" % (side, type(report).__name__)
        )
    verdict = report.get("verdict")
    if not isinstance(verdict, str) or not verdict.strip():
        raise ValueError(
            "%s 缺少 verdict（修复指引：传完整判定报告，不要传摘要）" % side
        )
    report_id = str(report.get("report_id") or "").strip()
    file_sha = str(report.get("file_sha256") or "").strip()
    file_obj = report.get("file")
    if isinstance(file_obj, dict):
        file_sha = file_sha or str(file_obj.get("sha256") or "").strip()
        report_id = report_id or file_sha[:16]
    if not report_id:
        report_id = _canonical_id(report)
    return {
        "report_id": report_id,
        "file_sha256": file_sha or None,
        "verdict": verdict.strip(),
    }


def _status(value) -> str:
    """状态归一：None → 空串，其余转大写字符串。"""
    return str(value or "").strip().upper()


def _rows(report: dict) -> dict:
    """按 A–E 段 + 逐项 id 抽 ``{id: {status, section}}``，保持原顺序。"""
    sections = report.get("sections")
    if not isinstance(sections, dict):
        raise ValueError(
            "判定报告缺少 sections 字典（修复指引：传 checker.check_file "
            "的完整报告，不要传人工摘要）"
        )
    rows = {}
    for key in SECTION_KEYS:
        section = sections.get(key)
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("id") or key)
        rows[section_id] = {
            "status": _status(section.get("status")),
            "section": True,
        }
        for item in section.get("items") or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id") or "")
            if not item_id:
                continue
            rows[item_id] = {
                "status": _status(item.get("status")),
                "section": False,
            }
    return rows


def _state(before, after) -> str:
    """给出状态迁移标签（见模块 docstring 的语义）。"""
    if before is None:
        return "new"
    if after is None:
        return "removed"
    if before == after:
        return "unchanged"
    before_rank = STATUS_RANK.get(before)
    after_rank = STATUS_RANK.get(after)
    if before_rank is None or after_rank is None:
        return "unchanged"
    if after_rank < before_rank:
        return "fixed"
    if after_rank > before_rank:
        return "regressed"
    return "unchanged"


def _verdict_delta(before: str, after: str) -> dict:
    """总体结论变化：改善 / 变差 / 持平。"""
    before_rank = STATUS_RANK.get(before)
    after_rank = STATUS_RANK.get(after)
    if before_rank is None or after_rank is None:
        direction = "unchanged"
    elif after_rank < before_rank:
        direction = "improved"
    elif after_rank > before_rank:
        direction = "worsened"
    else:
        direction = "unchanged"
    return {
        "before": before,
        "after": after,
        "direction": direction,
        "changed": before != after,
    }


def build_record(before: dict, after: dict) -> dict:
    """对齐两次判定，返回 nf-label-recheck/1 记录。

    recheck_id = sha256(before.report_id + after.report_id) 前 16 位。
    """
    before_snap = _snapshot(before, "before")
    after_snap = _snapshot(after, "after")
    before_rows = _rows(before)
    after_rows = _rows(after)
    if not before_rows and not after_rows:
        raise ValueError(
            "两次报告都没有 A–E 判定项（修复指引：确认送检的是受支持容器，"
            "并传 checker.check_file 的完整结果）"
        )
    order = list(before_rows)
    order += [key for key in after_rows if key not in before_rows]
    transitions = []
    fixed = []
    remaining = []
    regressed = []
    for row_id in order:
        before_row = before_rows.get(row_id)
        after_row = after_rows.get(row_id)
        before_status = before_row["status"] if before_row else None
        after_status = after_row["status"] if after_row else None
        state = _state(before_status, after_status)
        is_section = bool((before_row or after_row or {}).get("section"))
        transitions.append({
            "id": row_id,
            "before": before_status,
            "after": after_status,
            "state": state,
        })
        if is_section:
            continue
        if state == "fixed" and after_status == "PASS":
            fixed.append(row_id)
        if after_status in ("FAIL", "WARN"):
            remaining.append(row_id)
        if state == "regressed":
            regressed.append(row_id)
    joined = before_snap["report_id"] + after_snap["report_id"]
    recheck_id = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
    return {
        "schema": SCHEMA,
        "recheck_id": recheck_id,
        "before": before_snap,
        "after": after_snap,
        "verdict_delta": _verdict_delta(
            before_snap["verdict"], after_snap["verdict"]),
        "transitions": transitions,
        "fixed": fixed,
        "remaining": remaining,
        "regressed": regressed,
    }


# ---------------------------------------------------------------- 历史
def _validate_history(history, label: str) -> list:
    """校验历史列表形状；坏件给带修复指引的 ValueError。"""
    if not isinstance(history, list):
        raise ValueError(
            "%s 应为 list，实际 %s（修复指引：用 load_history 读取，或传 []）"
            % (label, type(history).__name__)
        )
    for index, entry in enumerate(history, 1):
        if not isinstance(entry, dict):
            raise ValueError(
                "%s 第 %d 条不是对象（修复指引：删除该条，或用 "
                "build_record 重建）" % (label, index)
            )
        recheck_id = entry.get("recheck_id")
        if not isinstance(recheck_id, str) or not recheck_id:
            raise ValueError(
                "%s 第 %d 条缺少 recheck_id（修复指引：重新跑 build_record "
                "生成记录后写回）" % (label, index)
            )
    return history


def _time_key(record: dict) -> str:
    """取记录时间（ISO-8601 字符串）；没有就返回空串。"""
    for key in TIME_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def history_append(history: list, record: dict) -> list:
    """按时间追加一条记录；同 recheck_id 覆盖（幂等），不修改入参。"""
    items = list(_validate_history(history, "复测历史"))
    if not isinstance(record, dict):
        raise ValueError(
            "record 应为 dict（修复指引：先用 build_record 生成记录）"
        )
    recheck_id = record.get("recheck_id")
    if not isinstance(recheck_id, str) or not recheck_id:
        raise ValueError(
            "record 缺少 recheck_id（修复指引：先用 build_record 生成记录）"
        )
    items = [x for x in items if x.get("recheck_id") != recheck_id]
    items.append(record)
    if all(_time_key(x) for x in items):
        items.sort(key=_time_key)
    return items


def load_history(path) -> list:
    """读复测历史 JSON；文件不存在返回 []，坏件抛 ValueError。"""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise ValueError(
            "无法读取复测历史：%s（%s）（修复指引：确认路径与读权限）"
            % (p, exc)
        )
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "复测历史不是合法 JSON：%s（修复指引：修正 JSON 语法，或备份后"
            "删除 %s 重来）" % (exc, p)
        )
    if not isinstance(data, list):
        raise ValueError(
            "复测历史根节点应为数组，实际 %s（修复指引：改成 [ ... ]，或用 "
            "save_history 重写）" % type(data).__name__
        )
    return _validate_history(data, "复测历史")


def save_history(path, history: list) -> None:
    """把复测历史写成 UTF-8 JSON（缩进 2、键排序、末尾换行）。"""
    data = _validate_history(history, "复测历史")
    p = Path(path)
    text = json.dumps(data, ensure_ascii=False, indent=2,
                      sort_keys=True) + "\n"
    try:
        p.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            "无法写入复测历史：%s（%s）（修复指引：确认目录存在且有写权限）"
            % (p, exc)
        )


# ---------------------------------------------------------------- 摘要
def summary(record: dict) -> str:
    """一句话人读摘要（无换行）。"""
    if not isinstance(record, dict):
        raise ValueError(
            "record 应为 dict（修复指引：先用 build_record 生成记录）"
        )
    delta = record.get("verdict_delta") or {}
    direction = {
        "improved": "改善",
        "worsened": "变差",
        "unchanged": "持平",
    }.get(delta.get("direction"), "未判定")
    return "复测 %s：%s→%s（%s），修复 %d 项、遗留 %d 项、回退 %d 项。" % (
        record.get("recheck_id") or "?",
        delta.get("before", "?"),
        delta.get("after", "?"),
        direction,
        len(record.get("fixed") or []),
        len(record.get("remaining") or []),
        len(record.get("regressed") or []),
    )
