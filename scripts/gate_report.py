#!/usr/bin/env python3
"""Render the 42 static verify checks as deterministic JUnit XML."""
from __future__ import annotations

import argparse
import math
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write  # noqa: E402

STANDARD_ID = "junit-xml"
STATUSES = {"PASS", "WARN", "FAIL", "SKIP"}
CHECK_META = (
    ("A", "官方核心目录结构"),
    ("A", "重号 ID 全限定·官方层"),
    ("A", "五条不变式落点"),
    ("A", "可见性边界"),
    ("A", "质检门"),
    ("A", "入口导航"),
    ("B", "社区两包结构完整"),
    ("B", "社区资产行数溯源"),
    ("B", "模块-资产引用可寻址 + 社区 README 重号限定"),
    ("B", "EXT 闭合 + 社区红线落地"),
    ("B", "资产-模块三方对账"),
    ("C", "桌面核心单元测试 + 全量 py_compile 语法抽查"),
    ("C", "协议版本一致性 + 迁移完整性"),
    ("C", "社区协议登记门禁"),
    ("C", "组合引用门禁"),
    ("C", "契约仲裁门禁"),
    ("C", "质量治理门禁"),
    ("C", "导出契约门禁"),
    ("C", "导出产物 schema 合规"),
    ("C", "文档完整性门禁"),
    ("C", "registry 引用图闭合门禁"),
    ("C", "导出物规范体检门禁"),
    ("C", "资产供应链闭合门禁"),
    ("C", "模块生命周期门禁"),
    ("C", "协议知识签名门禁"),
    ("C", "语义矛盾扫描门禁"),
    ("C", "架构纯度体检门禁"),
    ("C", "协议层 IDL schema 门禁"),
    ("C", "Conformance 一致性分级门禁"),
    ("C", "扩展策略 + bump 迁移门禁"),
    ("C", "生成物同仓 golden 门禁"),
    ("C", "质量纵深汇总门禁"),
    ("C", "新面汇总门禁"),
    ("C", "云端图书馆面门禁"),
    ("C", "深化面门禁"),
    ("C", "治理面门禁"),
    ("C", "知识层门禁"),
    ("C", "出口自动化门禁"),
    ("C", "终端与端壳残留门禁"),
    ("C", "数字资产契约门禁"),
    ("D", "构建隔离门禁"),
    ("D", "不可伪造 provenance 门禁"),
)
EXPECTED_CHECKS = len(CHECK_META)
GROUP_NAMES = {
    "A": "官方核心出厂",
    "B": "社区领域包",
    "C": "代码与协议层",
    "D": "供应链面",
}


class GateReportError(ValueError):
    """The structured verify records cannot be represented safely."""


def parse_records(lines: Iterable[str]) -> dict[int, list[tuple[str, str]]]:
    """Parse `check-id<TAB>status<TAB>message` records without accepting drift."""
    records: dict[int, list[tuple[str, str]]] = {}
    for line_no, raw in enumerate(lines, 1):
        line = raw.rstrip("\r\n")
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            raise GateReportError(
                f"记录第 {line_no} 行必须是三列 TSV（修复指引：使用 check-id、status、message）"
            )
        check_raw, status, message = parts
        if not check_raw.isdigit() or not 1 <= int(check_raw) <= EXPECTED_CHECKS:
            raise GateReportError(
                f"记录第 {line_no} 行 check id 非法：{check_raw!r}"
                f"（修复指引：只允许 1-{EXPECTED_CHECKS}）"
            )
        status = status.upper()
        if status not in STATUSES:
            raise GateReportError(
                f"记录第 {line_no} 行状态非法：{status!r}"
                f"（修复指引：只允许 {' / '.join(sorted(STATUSES))}）"
            )
        if not message:
            raise GateReportError(
                f"记录第 {line_no} 行 message 不能为空"
                "（修复指引：保留对应 verify 结果文本）"
            )
        records.setdefault(int(check_raw), []).append((status, message))
    return records


def _status(events: list[tuple[str, str]] | None) -> str:
    if not events:
        return "ERROR"
    statuses = {status for status, _message in events}
    if "FAIL" in statuses:
        return "FAIL"
    if "PASS" not in statuses and ({"SKIP", "WARN"} & statuses):
        return "SKIP"
    return "PASS"


def _add_property(case: ET.Element, name: str, value: str) -> None:
    properties = case.find("properties")
    if properties is None:
        properties = ET.SubElement(case, "properties")
    ET.SubElement(properties, "property", {"name": name, "value": value})


def _render_case(
    suite: ET.Element, check_id: int, group: str, name: str,
    events: list[tuple[str, str]] | None,
) -> str:
    status = _status(events)
    case = ET.SubElement(
        suite,
        "testcase",
        {"classname": f"verify.segment-{group.lower()}", "name": f"check{check_id:02d}: {name}"},
    )
    _add_property(case, "standard_id", STANDARD_ID)
    _add_property(case, "check_id", str(check_id))
    _add_property(case, "segment", group)
    native_status = _raw_status(events)
    _add_property(case, "nf.status", native_status)
    if not events:
        ET.SubElement(
            case,
            "error",
            {"message": "check did not report", "type": "verify-incomplete"},
        )
        return status
    _add_property(case, "event_count", str(len(events)))
    detail = "\n".join(f"[{event_status}] {message}" for event_status, message in events)
    ET.SubElement(case, "system-out").text = detail
    if status == "FAIL":
        failures = [message for event_status, message in events if event_status == "FAIL"]
        ET.SubElement(
            case,
            "failure",
            {"message": failures[0], "type": "verify-failure"},
        ).text = detail
    elif status == "SKIP":
        ET.SubElement(
            case,
            "skipped",
            {"message": "check skipped or reported warnings only"},
        )
    return status


def _raw_status(events: list[tuple[str, str]] | None) -> str:
    if not events:
        return "ERROR"
    statuses = {status for status, _message in events}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    if "SKIP" in statuses:
        return "SKIP"
    return "PASS"


def render_junit(
    records: dict[int, list[tuple[str, str]]], elapsed: float = 0.0
) -> str:
    """Render a 42-case JUnit document; missing checks become explicit errors."""
    if not math.isfinite(elapsed) or elapsed < 0:
        raise GateReportError("elapsed 必须是非负有限数（修复指引：传入 verify 墙钟秒数）")
    root = ET.Element("testsuites", {"name": "NinFenz verify"})
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
    groups: list[tuple[str, list[tuple[int, str, str]]]] = []
    for group in ("A", "B", "C", "D"):
        groups.append(
            (
                group,
                [
                    (check_id, item_group, name)
                    for check_id, (item_group, name) in enumerate(CHECK_META, 1)
                    if item_group == group
                ],
            )
        )
    for group, checks in groups:
        suite = ET.SubElement(
            root,
            "testsuite",
            {"name": f"segment-{group.lower()}: {GROUP_NAMES[group]}"},
        )
        for check_id, item_group, name in checks:
            counts[_render_case(suite, check_id, item_group, name, records.get(check_id))] += 1
        suite.set("tests", str(len(checks)))
        suite.set(
            "failures",
            str(sum(1 for check_id, *_ in checks
                    if _status(records.get(check_id)) == "FAIL")),
        )
        suite.set(
            "errors",
            str(sum(1 for check_id, *_ in checks
                    if _status(records.get(check_id)) == "ERROR")),
        )
        suite.set(
            "skipped",
            str(sum(1 for check_id, *_ in checks
                    if _status(records.get(check_id)) == "SKIP")),
        )
    root.set("tests", str(EXPECTED_CHECKS))
    root.set("failures", str(counts["FAIL"]))
    root.set("errors", str(counts["ERROR"]))
    root.set("skipped", str(counts["SKIP"]))
    root.set("time", f"{elapsed:.3f}")
    root_props = ET.SubElement(root, "properties")
    ET.SubElement(root_props, "property", {"name": "nf.standard", "value": STANDARD_ID})
    warnings = sum(1 for check_id in range(1, EXPECTED_CHECKS + 1)
                   if _raw_status(records.get(check_id)) == "WARN")
    ET.SubElement(root_props, "property", {"name": "nf.warnings", "value": str(warnings)})
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", short_empty_elements=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 verify 结构化记录转换为 JUnit XML")
    parser.add_argument("--records", required=True, help="verify.sh 生成的三列 TSV")
    parser.add_argument("--out", required=True, help="JUnit XML 输出路径")
    parser.add_argument("--elapsed", type=float, default=0.0, help="整次门禁墙钟秒数")
    args = parser.parse_args(argv)
    try:
        lines = Path(args.records).read_text(encoding="utf-8").splitlines()
        records = parse_records(lines)
        xml = render_junit(records, args.elapsed)
        atomic_write.write_text(args.out, xml)
    except (OSError, ValueError) as exc:
        print(f"✗ 无法生成 JUnit：{exc}", file=sys.stderr)
        return 2
    failures = sum(1 for check_id in range(1, EXPECTED_CHECKS + 1)
                   if _status(records.get(check_id)) == "FAIL")
    errors = sum(1 for check_id in range(1, EXPECTED_CHECKS + 1)
                 if _status(records.get(check_id)) == "ERROR")
    warnings = sum(1 for check_id in range(1, EXPECTED_CHECKS + 1)
                   if _raw_status(records.get(check_id)) == "WARN")
    print(f"== JUnit XML ==  checks {EXPECTED_CHECKS} · failures {failures} · "
          f"errors {errors} · warnings {warnings}")
    if errors:
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
